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
        direction LR
        %% --- Power Rails ---
        N1_L["|"]
        N1_R["|"]

        %% --- Contacts ---
        N1_bCompressor["—┤ ├—<br/>GVL_VAR.bCompressor"]
        N1_tImAlarmThreshold["GVL_Var.tImAlarmThreshold"]

        %% --- Function Blocks ---
        N1_TON[["TON<br/>fbTimer1"]]

        %% --- Bifurcation Junctions ---
        J_N1_TON_Q(( )):::junction

        %% --- Coils / Jumps ---
        N1_bSignal["—( )—<br/>GVL_Var.bSignal"]
        N1_DoorIsOpen["▶ DoorIsOpen"]

        %% --- Continuity ---
        N1_L --- N1_bCompressor
        N1_bCompressor ===|"IN"| N1_TON
        N1_tImAlarmThreshold ===|"PT"| N1_TON
        N1_TON ===|"Q"| J_N1_TON_Q
        J_N1_TON_Q === N1_bSignal
        J_N1_TON_Q === N1_DoorIsOpen
        N1_bSignal === N1_R

        classDef junction fill:#333,stroke:#333,width:6px,height:6px
    end
```

## Implementation (LD) — Network 2

```mermaid
%%{ init: { 'flowchart': { 'curve': 'stepAfter' } } }%%
flowchart LR
    subgraph Network_2 [" Network 2 "]
        direction LR
        %% --- Power Rails ---
        N2_L["|"]
        N2_R["|"]

        %% --- Contacts ---
        N2_bDoorOpen["—┤ ├—<br/>GVL_Var.bDoorOpen"]
        N2_tDoorOpenThreshold["GVL_var.tDoorOpenThreshold"]
        N2_T1s_On["T#1s"]
        N2_T1s_Off["T#1s"]
        N2_fbTimer2Q["—┤ ├—<br/>fbTimer2.Q"]

        %% --- Function Blocks ---
        N2_Blinker[["FB_Blinker<br/>fbBlinker"]]
        N2_TON[["TON<br/>fbTimer2"]]

        %% --- Coils / Jumps ---
        N2_bSignal["—( )—<br/>GVL_Var.bSignal"]

        %% --- Continuity ---
        N2_L --- N2_bDoorOpen
        N2_TON ===|"Q → bStart"| N2_Blinker
        N2_bDoorOpen ===|"IN"| N2_TON
        N2_tDoorOpenThreshold ===|"PT"| N2_TON
        N2_T1s_On ===|"tSignalTimerOn"| N2_Blinker
        N2_T1s_Off ===|"tSignalTimerOff"| N2_Blinker
        N2_Blinker ===|"bOut"| N2_fbTimer2Q
        N2_fbTimer2Q === N2_bSignal
        N2_bSignal === N2_R
    end
```

## Implementation (LD) — Network 3 (Label: DoorIsOpen)

```mermaid
%%{ init: { 'flowchart': { 'curve': 'stepAfter' } } }%%
flowchart LR
    subgraph Network_3 [" Network 3 — Label: DoorIsOpen "]
        direction LR
        %% --- Power Rails ---
        N3_L["|"]
        N3_R["|"]

        %% --- Contacts ---
        N3_bDoorOpen["—┤ ├—<br/>GVL_var.bDoorOpen"]

        %% --- Coils / Jumps ---
        N3_bLamp["—( )—<br/>GVL_Var.bLamp"]

        %% --- Continuity ---
        N3_L --- N3_bDoorOpen
        N3_bDoorOpen === N3_bLamp
        N3_bLamp === N3_R
    end
```
