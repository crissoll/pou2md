from __future__ import annotations


class TcPOUError(Exception):
    """Base class for conversion errors that can be shown without a traceback."""


class TcPOUParseError(TcPOUError):
    def __init__(self, filename: str, error: Exception):
        self.filename = filename
        self.original = error
        position = getattr(error, "position", None)
        location = f" at line {position[0]}, column {position[1]}" if position else ""
        super().__init__(f"failed to parse '{filename}'{location}: {error}")


class TcPOUInputError(TcPOUError):
    """Raised when an input file cannot be read."""


class TcPOUOutputError(TcPOUError):
    """Raised when generated output cannot be written."""
