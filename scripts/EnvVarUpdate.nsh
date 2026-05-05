; EnvVarUpdate.nsh
;
; Environment variable update. Supports adding and removing
; values to the user or system environment variables.
;
; Usage:
;   ${EnvVarUpdate} "ResultVarName" "EnvVarName" "Action" "RegLoc" "PathStr"
;
; Parameters:
;   ResultVarName - Variable to receive the result (returns error code)
;   EnvVarName    - Environment variable name (e.g., "PATH")
;   Action        - "A" = Add, "R" = Remove
;   RegLoc        - "HKLM" = System, "HKCU" = Current User
;   PathStr       - Path to add or remove
;
; Returns:
;   0 - Success
;   1 - Error opening registry key
;   2 - Error creating/updating registry value
;   3 - Path not found (for remove operation)
;   4 - Invalid action
;   5 - Invalid registry location

!ifndef EnvVarUpdate_nsh
!define EnvVarUpdate_nsh

!include "LogicLib.nsh"
!include "WinMessages.nsh"

; Registry keys
!define ENV_HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
!define ENV_HKCU "Environment"

; Send message to notify environment change
!ifndef WM_SETTINGCHANGE
!define WM_SETTINGCHANGE 0x001A
!endif

!macro EnvVarUpdate ResultVarName EnvVarName Action RegLoc PathStr
    Push `${PathStr}`
    Push `${RegLoc}`
    Push `${Action}`
    Push `${EnvVarName}`
    Call _EnvVarUpdate
    Pop ${ResultVarName}
!macroend

!define EnvVarUpdate "!insertmacro EnvVarUpdate"
!define un.EnvVarUpdate "!insertmacro un.EnvVarUpdate"

Function _EnvVarUpdate
    Exch $R0 ; EnvVarName
    Exch
    Exch $R1 ; Action (A/R)
    Exch
    Exch 2
    Exch $R2 ; RegLoc (HKLM/HKCU)
    Exch 2
    Exch 3
    Exch $R3 ; PathStr
    Exch 3

    Push $0 ; Return code
    Push $1 ; Temp
    Push $2 ; Current PATH value
    Push $3 ; New PATH value
    Push $4 ; Temp variable
    Push $5 ; Path to add/remove
    Push $6 ; Temp path for checking
    Push $7 ; Counter

    StrCpy $0 0 ; Default success

    ; Validate action type early
    ${If} $R1 != "A"
    ${AndIf} $R1 != "R"
        StrCpy $0 4 ; Invalid action
        Goto done
    ${EndIf}

    ; Clean up the path string (remove quotes and trim spaces)
    Push $R3
    Call _EnvVarUpdate_Trim
    Pop $R3

    ; Branch by registry root key
    ${If} $R2 == "HKLM"
        Goto do_hklm
    ${ElseIf} $R2 == "HKCU"
        Goto do_hkcu
    ${Else}
        StrCpy $0 5 ; Invalid registry location
        Goto done
    ${EndIf}

do_hklm:
    SetShellVarContext all
    ClearErrors
    ReadRegStr $2 HKLM "${ENV_HKLM}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        ; Add operation
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            ; Check if path already exists
            Push $2
            Push $R3
            Call _EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                StrCpy $1 "$2;$R3"
            ${Else}
                StrCpy $1 $2
            ${EndIf}
        ${EndIf}
    ${Else}
        ; Remove operation
        StrCpy $1 $2
        StrCpy $5 $1
        StrLen $6 $R3

        ${Do}
            Push $5
            Push $R3
            Call _EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}

            ; Remove the path from the list
            Push $5
            Push $R3
            Call _EnvVarUpdate_RemovePath
            Pop $5
        ${Loop}

        StrCpy $1 $5
    ${EndIf}

    ; Write back to registry
    ${If} $1 == ""
        DeleteRegValue HKLM "${ENV_HKLM}" $R0
    ${Else}
        WriteRegExpandStr HKLM "${ENV_HKLM}" $R0 $1
    ${EndIf}
    IfErrors 0 +2
        StrCpy $0 2 ; Error creating/updating registry value
    Goto broadcast

do_hkcu:
    SetShellVarContext current
    ClearErrors
    ReadRegStr $2 HKCU "${ENV_HKCU}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        ; Add operation
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            ; Check if path already exists
            Push $2
            Push $R3
            Call _EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                StrCpy $1 "$2;$R3"
            ${Else}
                StrCpy $1 $2
            ${EndIf}
        ${EndIf}
    ${Else}
        ; Remove operation
        StrCpy $1 $2
        StrCpy $5 $1
        StrLen $6 $R3

        ${Do}
            Push $5
            Push $R3
            Call _EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}

            ; Remove the path from the list
            Push $5
            Push $R3
            Call _EnvVarUpdate_RemovePath
            Pop $5
        ${Loop}

        StrCpy $1 $5
    ${EndIf}

    ; Write back to registry
    ${If} $1 == ""
        DeleteRegValue HKCU "${ENV_HKCU}" $R0
    ${Else}
        WriteRegExpandStr HKCU "${ENV_HKCU}" $R0 $1
    ${EndIf}
    IfErrors 0 +2
        StrCpy $0 2 ; Error creating/updating registry value

broadcast:
    ; Broadcast environment change
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000

done:
    StrCpy $R0 $0
    Pop $7
    Pop $6
    Pop $5
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Pop $0
    Exch $R0
FunctionEnd

; Helper function to trim quotes and spaces
Function _EnvVarUpdate_Trim
    Exch $R0
    Push $R1
    Push $R2

    ; Remove quotes
    StrCpy $R1 $R0 1
    ${If} $R1 == '"'
        StrCpy $R0 $R0 "" 1
        StrLen $R2 $R0
        IntOp $R2 $R2 - 1
        StrCpy $R0 $R0 $R2
    ${EndIf}

    ; Trim leading spaces
    ${Do}
        StrCpy $R1 $R0 1
        ${If} $R1 == " "
            StrCpy $R0 $R0 "" 1
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    ; Trim trailing spaces
    ${Do}
        StrLen $R1 $R0
        IntOp $R2 $R1 - 1
        StrCpy $R1 $R0 1 $R2
        ${If} $R1 == " "
            StrCpy $R0 $R0 $R2
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

; Helper function to check if path exists in the list
Function _EnvVarUpdate_IsPathInList
    Exch $R0 ; Path to find
    Exch
    Exch $R1 ; Path list
    Push $R2
    Push $R3
    Push $R4
    Push $R5

    StrCpy $R2 ""
    StrLen $R3 $R0
    StrLen $R4 $R1
    StrCpy $R5 0

    ${Do}
        ; Extract substring
        StrCpy $R2 $R1 $R3 $R5

        ; Compare case-insensitively
        ${If} $R2 == $R0
            StrCpy $R0 $R2
            ${ExitDo}
        ${EndIf}

        IntOp $R5 $R5 + 1
    ${LoopWhile} $R5 <= $R4 - $R3

    ${If} $R5 > $R4 - $R3
        StrCpy $R0 ""
    ${EndIf}

    Pop $R5
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

; Helper function to remove path from list
Function _EnvVarUpdate_RemovePath
    Exch $R0 ; Path to remove
    Exch
    Exch $R1 ; Path list
    Push $R2
    Push $R3
    Push $R4

    ; Ensure list starts and ends with semicolon for easy processing
    StrCpy $R2 ";$R1;"
    StrCpy $R3 ";$R0;"

    ; Replace the path with semicolon
    Push $R2
    Push $R3
    Push ";"
    Call _EnvVarUpdate_Replace
    Pop $R4

    ; Remove leading and trailing semicolons
    Push $R4
    Call _EnvVarUpdate_StripSemicolons
    Pop $R0

    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

; Helper function to replace substring
Function _EnvVarUpdate_Replace
    Exch $R0 ; Replacement
    Exch
    Exch $R1 ; Search for
    Exch
    Exch 2
    Exch $R2 ; Source string
    Exch 2
    Push $R3
    Push $R4
    Push $R5
    Push $R6

    StrCpy $R3 ""
    StrCpy $R4 ""
    StrLen $R5 $R1
    StrLen $R6 $R2

    ${Do}
        StrCpy $R3 $R2 $R5
        ${If} $R3 == $R1
            StrCpy $R4 "$R4$R0"
            StrCpy $R2 $R2 "" $R5
            StrLen $R6 $R2
        ${Else}
            StrCpy $R3 $R2 1
            StrCpy $R4 "$R4$R3"
            StrCpy $R2 $R2 "" 1
            StrLen $R6 $R2
        ${EndIf}
    ${LoopWhile} $R6 > 0

    StrCpy $R0 $R4

    Pop $R6
    Pop $R5
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

; Helper function to strip leading/trailing semicolons
Function _EnvVarUpdate_StripSemicolons
    Exch $R0
    Push $R1
    Push $R2

    ; Strip leading semicolons
    ${Do}
        StrCpy $R1 $R0 1
        ${If} $R1 == ";"
            StrCpy $R0 $R0 "" 1
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    ; Strip trailing semicolons
    ${Do}
        StrLen $R1 $R0
        IntOp $R2 $R1 - 1
        StrCpy $R1 $R0 1 $R2
        ${If} $R1 == ";"
            StrCpy $R0 $R0 $R2
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

; ---------------------------------------------------------------
; Uninstaller variant
; ---------------------------------------------------------------

!macro un.EnvVarUpdate ResultVarName EnvVarName Action RegLoc PathStr
    Push `${PathStr}`
    Push `${RegLoc}`
    Push `${Action}`
    Push `${EnvVarName}`
    Call un._EnvVarUpdate
    Pop ${ResultVarName}
!macroend

Function un._EnvVarUpdate
    Exch $R0 ; EnvVarName
    Exch
    Exch $R1 ; Action (A/R)
    Exch
    Exch 2
    Exch $R2 ; RegLoc (HKLM/HKCU)
    Exch 2
    Exch 3
    Exch $R3 ; PathStr
    Exch 3

    Push $0 ; Return code
    Push $1 ; Temp
    Push $2 ; Current PATH value
    Push $3 ; New PATH value
    Push $4 ; Temp variable
    Push $5 ; Path to add/remove
    Push $6 ; Temp path for checking
    Push $7 ; Counter

    StrCpy $0 0 ; Default success

    ${If} $R1 != "A"
    ${AndIf} $R1 != "R"
        StrCpy $0 4 ; Invalid action
        Goto un_done
    ${EndIf}

    Push $R3
    Call un._EnvVarUpdate_Trim
    Pop $R3

    ${If} $R2 == "HKLM"
        Goto un_do_hklm
    ${ElseIf} $R2 == "HKCU"
        Goto un_do_hkcu
    ${Else}
        StrCpy $0 5 ; Invalid registry location
        Goto un_done
    ${EndIf}

un_do_hklm:
    SetShellVarContext all
    ClearErrors
    ReadRegStr $2 HKLM "${ENV_HKLM}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            Push $2
            Push $R3
            Call un._EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                StrCpy $1 "$2;$R3"
            ${Else}
                StrCpy $1 $2
            ${EndIf}
        ${EndIf}
    ${Else}
        StrCpy $1 $2
        StrCpy $5 $1
        StrLen $6 $R3

        ${Do}
            Push $5
            Push $R3
            Call un._EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}

            Push $5
            Push $R3
            Call un._EnvVarUpdate_RemovePath
            Pop $5
        ${Loop}

        StrCpy $1 $5
    ${EndIf}

    ${If} $1 == ""
        DeleteRegValue HKLM "${ENV_HKLM}" $R0
    ${Else}
        WriteRegExpandStr HKLM "${ENV_HKLM}" $R0 $1
    ${EndIf}
    IfErrors 0 +2
        StrCpy $0 2
    Goto un_broadcast

un_do_hkcu:
    SetShellVarContext current
    ClearErrors
    ReadRegStr $2 HKCU "${ENV_HKCU}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            Push $2
            Push $R3
            Call un._EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                StrCpy $1 "$2;$R3"
            ${Else}
                StrCpy $1 $2
            ${EndIf}
        ${EndIf}
    ${Else}
        StrCpy $1 $2
        StrCpy $5 $1
        StrLen $6 $R3

        ${Do}
            Push $5
            Push $R3
            Call un._EnvVarUpdate_IsPathInList
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}

            Push $5
            Push $R3
            Call un._EnvVarUpdate_RemovePath
            Pop $5
        ${Loop}

        StrCpy $1 $5
    ${EndIf}

    ${If} $1 == ""
        DeleteRegValue HKCU "${ENV_HKCU}" $R0
    ${Else}
        WriteRegExpandStr HKCU "${ENV_HKCU}" $R0 $1
    ${EndIf}
    IfErrors 0 +2
        StrCpy $0 2

un_broadcast:
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000

un_done:
    StrCpy $R0 $0
    Pop $7
    Pop $6
    Pop $5
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Pop $0
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_Trim
    Exch $R0
    Push $R1
    Push $R2

    StrCpy $R1 $R0 1
    ${If} $R1 == '"'
        StrCpy $R0 $R0 "" 1
        StrLen $R2 $R0
        IntOp $R2 $R2 - 1
        StrCpy $R0 $R0 $R2
    ${EndIf}

    ${Do}
        StrCpy $R1 $R0 1
        ${If} $R1 == " "
            StrCpy $R0 $R0 "" 1
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    ${Do}
        StrLen $R1 $R0
        IntOp $R2 $R1 - 1
        StrCpy $R1 $R0 1 $R2
        ${If} $R1 == " "
            StrCpy $R0 $R0 $R2
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_IsPathInList
    Exch $R0
    Exch
    Exch $R1
    Push $R2
    Push $R3
    Push $R4
    Push $R5

    StrCpy $R2 ""
    StrLen $R3 $R0
    StrLen $R4 $R1
    StrCpy $R5 0

    ${Do}
        StrCpy $R2 $R1 $R3 $R5
        ${If} $R2 == $R0
            StrCpy $R0 $R2
            ${ExitDo}
        ${EndIf}
        IntOp $R5 $R5 + 1
    ${LoopWhile} $R5 <= $R4 - $R3

    ${If} $R5 > $R4 - $R3
        StrCpy $R0 ""
    ${EndIf}

    Pop $R5
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_RemovePath
    Exch $R0
    Exch
    Exch $R1
    Push $R2
    Push $R3
    Push $R4

    StrCpy $R2 ";$R1;"
    StrCpy $R3 ";$R0;"

    Push $R2
    Push $R3
    Push ";"
    Call un._EnvVarUpdate_Replace
    Pop $R4

    Push $R4
    Call un._EnvVarUpdate_StripSemicolons
    Pop $R0

    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_Replace
    Exch $R0
    Exch
    Exch $R1
    Exch
    Exch 2
    Exch $R2
    Exch 2
    Push $R3
    Push $R4
    Push $R5
    Push $R6

    StrCpy $R3 ""
    StrCpy $R4 ""
    StrLen $R5 $R1
    StrLen $R6 $R2

    ${Do}
        StrCpy $R3 $R2 $R5
        ${If} $R3 == $R1
            StrCpy $R4 "$R4$R0"
            StrCpy $R2 $R2 "" $R5
            StrLen $R6 $R2
        ${Else}
            StrCpy $R3 $R2 1
            StrCpy $R4 "$R4$R3"
            StrCpy $R2 $R2 "" 1
            StrLen $R6 $R2
        ${EndIf}
    ${LoopWhile} $R6 > 0

    StrCpy $R0 $R4

    Pop $R6
    Pop $R5
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_StripSemicolons
    Exch $R0
    Push $R1
    Push $R2

    ${Do}
        StrCpy $R1 $R0 1
        ${If} $R1 == ";"
            StrCpy $R0 $R0 "" 1
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    ${Do}
        StrLen $R1 $R0
        IntOp $R2 $R1 - 1
        StrCpy $R1 $R0 1 $R2
        ${If} $R1 == ";"
            StrCpy $R0 $R0 $R2
        ${Else}
            ${ExitDo}
        ${EndIf}
    ${Loop}

    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

!endif ; EnvVarUpdate_nsh