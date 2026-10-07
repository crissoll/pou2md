# FB_Blinker

> **POU Type:** FUNCTION_BLOCK  
> **Source:** `FB_Blinker.TcPOU`  
> **Implementation Language:** FBD (Function Block Diagram)

## Declaration

```mermaid
classDiagram
    class FB_Blinker {
        &lt;&lt;FUNCTION_BLOCK&gt;&gt;
        +BOOL bStart
        +TIME tSignalTimerOn
        +TIME tSignalTimerOff
        -BOOL bOut
        TON fbTimerA
        TON fbTimerB
    }
```

## Implementation (FBD) — Network 1

```mermaid
flowchart LR
    %% --- Operands / Variables ---
    bStart(["bStart"])
    fbTimerBQ(["fbTimerB.Q"])
    tSignalTimerOn(["tSignalTimerOn"])
    tSignalTimerOff(["tSignalTimerOff"])
    bOut(["bOut"])

    %% --- Function Blocks & Operators ---
    AND1{{"AND (&)"}}
    TON_A[["TON
    fbTimerA"]]
    TON_B[["TON
    fbTimerB"]]

    %% --- Wiring ---
    bStart --> AND1
    fbTimerBQ -. "○ (negated)" .-> AND1
    AND1 -- "IN" --> TON_A
    tSignalTimerOn -- "PT" --> TON_A
    TON_A -- "Q" --> bOut
    TON_A -- "Q → IN" --> TON_B
    tSignalTimerOff -- "PT" --> TON_B
```

### Logic Description

A self-resetting blinker oscillator:

1. `bStart` AND `NOT fbTimerB.Q` feed into the **AND** gate
2. AND output → `fbTimerA.IN`, `tSignalTimerOn` → `fbTimerA.PT`
3. `fbTimerA.Q` drives `bOut` (the blinking output) **and** feeds forward to `fbTimerB.IN`
4. `tSignalTimerOff` → `fbTimerB.PT`
5. When `fbTimerB` times out, its `.Q` goes HIGH, which negates the AND input → resets `fbTimerA` → cycle restarts
