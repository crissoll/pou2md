# MAIN

> **POU Type:** PROGRAM  
> **Source:** `MAIN.TcPOU`  
> **Implementation Language:** CFC (Continuous Function Chart)

## Declaration

```mermaid
classDiagram
    class MAIN {
        <<PROGRAM>>
        REAL fHysteresis = 1
        SR fbSR
    }
```

## Implementation (CFC)

```mermaid
%%{ init: { 'flowchart': { 'curve': 'step' } } }%%
flowchart LR
    %% --- Input Variables ---
    fTempActual(["GVL_Var.fTempActual"])
    fTempSet(["GVL_Var.fTempSet"])
    fHysteresis(["fHysteresis"])

    %% --- Operators ---
    ADD1["ADD"]
    LT1["LT"]
    SUB1["SUB"]
    GT1["GT"]

    %% --- Function Blocks ---
    SR1[["SR
    fbSR"]]

    %% --- Program Calls ---
    Signals[[" Signals"]]

    %% --- Output Variables ---
    bCompressor(["GVL_Var.bCompressor"])

    %% --- Vertical Rank Alignment ---
    fTempActual ~~~ fTempSet ~~~ fHysteresis
    ADD1 ~~~ SUB1
    GT1 ~~~ LT1

    %% --- Wiring ---
    fTempSet --> ADD1
    fTempSet --> SUB1
    fHysteresis --> ADD1
    fHysteresis --> SUB1
    ADD1 --> GT1
    fTempActual --> GT1
    fTempActual --> LT1
    GT1 -- "SET1" --> SR1
    SUB1 --> LT1
    LT1 -- "RESET" --> SR1
    SR1 -- "Q1" --> bCompressor
```
