# Signals

> **POU Type:** PROGRAM  
> **Source:** `Signals.TcPOU`  
> **Implementation Language:** LD (Ladder Diagram) via NWL

## Declaration

```mermaid
classDiagram
    class Signals {
        <<PROGRAM>>
        TON fbTimer1
        TON fbTimer2
        FB_Blinker fbBlinker
    }
```

## Implementation (LD) — Network 1

```mermaid
%%{ init: { 'flowchart': { 'curve': 'stepAfter' } } }%%
flowchart LR
    subgraph Network_1 [" Network 1 "]
        %% --- Contacts (inputs) ---
        N1_bCompressor(["GVL_VAR.bCompressor
        ┤├"])
        N1_tImAlarmThreshold(["GVL_Var.tImAlarmThreshold"])

        %% --- Function Blocks ---
        N1_TON[["TON
        fbTimer1"]]

        %% --- Bifurcation Junctions ---
        J_N1_TON_Q(( )):::junction

        %% --- Coils / Outputs ---
        N1_bSignal(["GVL_Var.bSignal
        ( )"])
        N1_DoorIsOpen(["▶ DoorIsOpen
        (jump label)"])

        %% --- Wiring ---
        N1_bCompressor -- "IN" --> N1_TON
        N1_tImAlarmThreshold -- "PT" --> N1_TON
        N1_TON -- "Q" --> J_N1_TON_Q
        J_N1_TON_Q --> N1_bSignal
        J_N1_TON_Q --> N1_DoorIsOpen

        classDef junction fill:#333,stroke:#333,width:6px,height:6px
    end
```

## Implementation (LD) — Network 2

```mermaid
%%{ init: { 'flowchart': { 'curve': 'stepAfter' } } }%%
flowchart LR
    subgraph Network_2 [" Network 2 "]
        %% --- Contacts (inputs) ---
        N2_bDoorOpen(["GVL_Var.bDoorOpen
        ┤├"])
        N2_tDoorOpenThreshold(["GVL_var.tDoorOpenThreshold"])
        N2_T1s_On(["T#1s"])
        N2_T1s_Off(["T#1s"])
        N2_fbTimer2Q(["fbTimer2.Q
        ┤├"])

        %% --- Function Blocks ---
        N2_AND{{"AND"}}
        N2_Blinker[["FB_Blinker
        fbBlinker"]]
        N2_TON[["TON
        fbTimer2"]]

        %% --- Coils / Outputs ---
        N2_bSignal(["GVL_Var.bSignal
        ( )"])

        %% --- Wiring ---
        N2_Blinker -- "bOut" --> N2_AND
        N2_TON -- "Q → bStart" --> N2_Blinker
        N2_bDoorOpen -- "IN" --> N2_TON
        N2_tDoorOpenThreshold -- "PT" --> N2_TON
        N2_T1s_On -- "tSignalTimerOn" --> N2_Blinker
        N2_T1s_Off -- "tSignalTimerOff" --> N2_Blinker
        N2_fbTimer2Q --> N2_AND
        N2_AND --> N2_bSignal
    end
```

## Implementation (LD) — Network 3 (Label: DoorIsOpen)

```mermaid
%%{ init: { 'flowchart': { 'curve': 'stepAfter' } } }%%
flowchart LR
    subgraph Network_3 [" Network 3 — Label: DoorIsOpen "]
        %% --- Contacts (inputs) ---
        N3_bDoorOpen(["GVL_var.bDoorOpen
        ┤├"])

        %% --- Coils / Outputs ---
        N3_bLamp(["GVL_Var.bLamp
        ( )"])

        %% --- Wiring ---
        N3_bDoorOpen --> N3_bLamp
    end
```
