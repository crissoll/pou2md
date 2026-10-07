from __future__ import annotations

import fnmatch
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from .converter import TcPOUConverter
from .manifest import load_manifest, manifest_path, save_manifest

LOGGER = logging.getLogger(__name__)


def _status(message: str, quiet: bool) -> None:
    if not quiet:
        LOGGER.info(message)


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is currently active."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class LockGuard:
    """Manages a lockfile to prevent duplicate concurrent watchers targeting the same output."""

    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.acquired = False

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(21):
            try:
                fd = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
                with os.fdopen(fd, "w", encoding="utf-8") as lock_file:
                    lock_file.write(str(os.getpid()))
                self.acquired = True
                return True
            except FileExistsError:
                try:
                    pid = int(self.lock_path.read_text(encoding="utf-8").strip())
                except (ValueError, OSError):
                    pid = 0

                if pid != os.getpid() and is_process_running(pid):
                    LOGGER.error(
                        f"[pou2md] Another watcher is already active for this target (PID {pid}).\n"
                        f"To stop it, press Ctrl+C in that terminal or terminate that process.",
                    )
                    return False

                if not pid and attempt < 20:
                    time.sleep(0.05)
                    continue

                try:
                    self.lock_path.unlink()
                except OSError:
                    pass
            except OSError as e:
                LOGGER.error("[pou2md] Failed to create lock file '%s': %s", self.lock_path, e)
                return False

        LOGGER.error("[pou2md] Failed to acquire lock file '%s'.", self.lock_path)
        return False

    def release(self) -> None:
        if self.acquired:
            try:
                self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            self.acquired = False


def _get_lock_path(input_path: Path, output: str | None) -> Path:
    if output:
        out_p = Path(output)
        if out_p.suffix.lower() == ".md":
            return out_p.parent / f".{out_p.name}.lock"
        return out_p / ".pou2md.lock"
    if input_path.is_dir():
        return input_path / ".pou2md.lock"
    return input_path.parent / f".{input_path.name}.lock"


def _scan_files(
    input_path: Path,
    recursive: bool,
    exclude: tuple[str, ...] = (),
) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    if input_path.is_file():
        if input_path.suffix.lower() == ".tcpou" and input_path.exists():
            try:
                stat = input_path.stat()
                snapshot[input_path] = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                pass
    elif input_path.is_dir():
        try:
            candidates = input_path.rglob("*") if recursive else input_path.iterdir()
            for p in candidates:
                if not p.is_file() or p.suffix.lower() != ".tcpou":
                    continue
                relative = p.relative_to(input_path)
                if any(
                    fnmatch.fnmatch(candidate, pattern)
                    for pattern in exclude
                    for candidate in (p.name, str(relative), relative.as_posix())
                ):
                    continue
                try:
                    stat = p.stat()
                    snapshot[p] = (stat.st_mtime_ns, stat.st_size)
                except OSError:
                    pass
        except OSError:
            # Network shares can temporarily reject directory enumeration.
            pass
    return snapshot


def start_watcher(
    input_path: Path,
    converter: TcPOUConverter,
    output: str | None = None,
    recursive: bool = False,
    unified: bool = False,
    single_folder: bool = True,
    copy_folder_structure: bool = False,
    to_stdout: bool = False,
    poll_interval: float = 1.0,
    debounce_delay: float = 0.25,
    retry_count: int = 3,
    retry_delay: float = 0.5,
    exclude: tuple[str, ...] = (),
    quiet: bool = False,
) -> int:
    """
    Watch input file or directory for changes and automatically re-convert.

    Features:
      - Graceful Ctrl+C handling.
      - Lockfile guard to prevent dual watcher collisions on the same target.
      - Debouncing and retry to avoid mid-save Windows file locks.
      - Non-fatal exception handling for invalid XML while editing.
    """
    lock_path = _get_lock_path(input_path, output)
    lock = LockGuard(lock_path)
    if not lock.acquire():
        return 1

    try:
        output_manifest = (
            manifest_path(output)
            if output and not to_stdout and input_path.is_dir()
            else None
        )
        # Initial compilation
        try:
            if input_path.is_file():
                md_text, out_file = converter.convert_file(
                    input_path,
                    output_dir=output if not to_stdout else None,
                )
                if to_stdout:
                    if hasattr(sys.stdout, "reconfigure"):
                        sys.stdout.reconfigure(encoding="utf-8")
                    print(md_text)
                elif out_file:
                    _status(f"[pou2md] Initial build: {out_file}", quiet)
            elif input_path.is_dir():
                written, unified_text = converter.convert_directory(
                    input_dir=input_path,
                    output_dir=output if not to_stdout else None,
                    recursive=recursive,
                    unified=unified,
                    single_folder=single_folder,
                    copy_folder_structure=copy_folder_structure,
                    exclude=exclude,
                )
                if to_stdout and unified_text:
                    if hasattr(sys.stdout, "reconfigure"):
                        sys.stdout.reconfigure(encoding="utf-8")
                    print(unified_text)
                elif unified and written:
                    _status(f"[pou2md] Initial build: Unified into {written[0]}", quiet)
                elif written:
                    _status(
                        f"[pou2md] Initial build: Converted {len(written)} POU file(s) to '{output}'.",
                        quiet,
                    )
                if output_manifest:
                    save_manifest(output_manifest, set(written))
        except Exception as e:
            LOGGER.error(
                f"[pou2md] Initial build failed: {e}. "
                "Waiting for a complete file before retrying.",
            )

        target_desc = str(output) if output else ("stdout" if to_stdout else str(input_path))
        _status(
            f"[pou2md] Watching '{input_path}' (target: {target_desc})... Press Ctrl+C to stop.",
            quiet,
        )

        current_snapshot = _scan_files(input_path, recursive, exclude)

        while True:
            time.sleep(poll_interval)
            new_snapshot = _scan_files(input_path, recursive, exclude)

            changed = [
                p for p, mtime in new_snapshot.items()
                if p in current_snapshot and mtime != current_snapshot[p]
            ]
            added = [p for p in new_snapshot if p not in current_snapshot]
            removed = [p for p in current_snapshot if p not in new_snapshot]

            if not changed and not added and not removed:
                continue

            # Debounce to allow multi-step editor writes to finish
            time.sleep(debounce_delay)
            stabilized_snapshot = _scan_files(input_path, recursive, exclude)
            previous_snapshot = current_snapshot
            current_snapshot = stabilized_snapshot

            now = datetime.now().strftime("%H:%M:%S")

            if unified:
                try:
                    for attempt in range(retry_count):
                        try:
                            written, unified_text = converter.convert_directory(
                                input_dir=input_path,
                                output_dir=output if not to_stdout else None,
                                recursive=recursive,
                                unified=True,
                                single_folder=False,
                                exclude=exclude,
                            )
                            break
                        except Exception:
                            if attempt == retry_count - 1:
                                raise
                            time.sleep(retry_delay)
                    if to_stdout and unified_text:
                        print(unified_text)
                    elif written:
                        _status(f"[{now}] Detected changes -> Updated unified file: {written[0].name}", quiet)
                    if output_manifest:
                        save_manifest(output_manifest, set(written))
                except Exception as e:
                    LOGGER.error("[%s] Error updating unified document: %s", now, e)
                    current_snapshot = previous_snapshot
            if single_folder:
                failed = set()
                for p in changed + added:
                    try:
                        if input_path.is_dir() and recursive and copy_folder_structure:
                            rel = p.relative_to(input_path)
                            custom_filename = str(rel.with_suffix(".md"))
                        elif input_path.is_dir() and recursive:
                            rel = p.relative_to(input_path)
                            if rel.parent.parts:
                                custom_filename = "--".join(list(rel.parent.parts) + [p.stem]) + ".md"
                            else:
                                custom_filename = f"{p.stem}.md"
                        else:
                            custom_filename = f"{p.stem}.md"

                        for attempt in range(retry_count):
                            try:
                                md_text, out_file = converter.convert_file(
                                    p,
                                    output_dir=output if not to_stdout else None,
                                    custom_filename=custom_filename,
                                )
                                break
                            except Exception:
                                if attempt == retry_count - 1:
                                    raise
                                time.sleep(retry_delay)
                        if to_stdout:
                            print(md_text)
                        elif out_file:
                            label = "Added" if p in added else "Updated"
                            _status(f"[{now}] {label} '{p.name}' -> Generated: {out_file.name}", quiet)
                            if output_manifest:
                                current_outputs = load_manifest(output_manifest)
                                current_outputs.add(out_file)
                                save_manifest(output_manifest, current_outputs)
                    except Exception as e:
                        failed.add(p)
                        LOGGER.error(
                            "[%s] Error compiling '%s': %s. Waiting for next change...",
                            now,
                            p.name,
                            e,
                        )

                for p in failed:
                    if p in previous_snapshot:
                        current_snapshot[p] = previous_snapshot[p]
                    else:
                        current_snapshot.pop(p, None)

                if removed and output and not to_stdout:
                    out_dir = Path(output)
                    if out_dir.suffix.lower() == ".md":
                        out_dir = out_dir.parent
                    for p in removed:
                        if input_path.is_dir() and recursive and copy_folder_structure:
                            rel = p.relative_to(input_path)
                            fname = str(rel.with_suffix(".md"))
                        elif input_path.is_dir() and recursive:
                            rel = p.relative_to(input_path)
                            if rel.parent.parts:
                                fname = "--".join(list(rel.parent.parts) + [p.stem]) + ".md"
                            else:
                                fname = f"{p.stem}.md"
                        else:
                            fname = f"{p.stem}.md"
                        target_md = out_dir / fname
                        if target_md.exists():
                            target_md.unlink(missing_ok=True)
                            _status(f"[{now}] Removed '{p.name}' -> Deleted: {target_md.name}", quiet)
                            if output_manifest:
                                current_outputs = load_manifest(output_manifest)
                                current_outputs.discard(target_md)
                                save_manifest(output_manifest, current_outputs)

    except KeyboardInterrupt:
        _status("\n[pou2md] Stopped watching. Bye!", quiet)
        return 0
    except Exception as e:
        LOGGER.exception("[pou2md] Watcher stopped unexpectedly: %s", e)
        return 1
    finally:
        lock.release()

    return 0
