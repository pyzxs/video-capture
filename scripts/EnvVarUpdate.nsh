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
; Example:
;   ${EnvVarUpdate} $0 "PATH" "A" "HKLM" "C:\MyApp\bin"
;
; Returns:
;   0 - Success
;   1 - Error opening registry key
;   2 - Error creating/updating registry value
;   3 - Path not found (for remove operation)

!ifndef EnvVarUpdate_nsh
!define EnvVarUpdate_nsh

!include "LogicLib.nsh"
!include "WinMessages.nsh"

; Registry keys
!define ENV_HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
!define ENV_HKCU "Environment"

; Send message to notify environment change (已由 WinMessages.nsh 定义时跳过)
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

    StrCpy $0 0 ; Default success

    ; Validate action type early
    ${If} $R1 != "A"
    ${AndIf} $R1 != "R"
        StrCpy $0 2 ; Invalid action
        Goto done
    ${EndIf}

    ; Clean up the path string (remove quotes)
    Push $R3
    Call _EnvVarUpdate_Unquote
    Pop $R3

    ; Branch by registry root key (literal required by NSIS ReadRegStr/WriteRegExpandStr)
    ${If} $R2 == "HKLM"
        Goto do_hklm
    ${ElseIf} $R2 == "HKCU"
        Goto do_hkcu
    ${Else}
        StrCpy $0 1 ; Invalid registry location
        Goto done
    ${EndIf}

do_hklm:
    SetShellVarContext all
    ClearErrors
    ReadRegStr $2 HKLM "${ENV_HKLM}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        StrCpy $1 "" ; new value
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            Push ";$2;"
            Push ";$R3;"
            Call _EnvVarUpdate_StrStr
            Pop $4
            ${If} $4 == ""
                StrCpy $1 "$2;$R3"
            ${Else}
                StrCpy $1 $2
            ${EndIf}
        ${EndIf}
    ${Else}  ; R - remove
        StrCpy $1 $2
        StrCpy $5 $1
        StrLen $6 $R3
        ${Do}
            Push $5
            Push "$R3"
            Call _EnvVarUpdate_StrStr
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}
            StrCpy $4 $4 -$6
            StrCpy $5 "$4$5"
            Push $5
            Call _EnvVarUpdate_StripSemicolons
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
        StrCpy $0 3
    Goto broadcast

do_hkcu:
    SetShellVarContext current
    ClearErrors
    ReadRegStr $2 HKCU "${ENV_HKCU}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        StrCpy $1 "" ; new value
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            Push ";$2;"
            Push ";$R3;"
            Call _EnvVarUpdate_StrStr
            Pop $4
            ${If} $4 == ""
                StrCpy $1 "$2;$R3"
            ${Else}
                StrCpy $1 $2
            ${EndIf}
        ${EndIf}
    ${Else}  ; R - remove
        StrCpy $1 $2
        StrCpy $5 $1
        StrLen $6 $R3
        ${Do}
            Push $5
            Push "$R3"
            Call _EnvVarUpdate_StrStr
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}
            StrCpy $4 $4 -$6
            StrCpy $5 "$4$5"
            Push $5
            Call _EnvVarUpdate_StripSemicolons
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
        StrCpy $0 3

broadcast:
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000

done:
    StrCpy $R0 $0
    Pop $6
    Pop $5
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Pop $0
    Exch $R0
FunctionEnd

Function _EnvVarUpdate_Unquote
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

    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function _EnvVarUpdate_StrStr
    Exch $R0 ; Needle
    Exch
    Exch $R1 ; Haystack
    Push $R2
    Push $R3
    Push $R4
    Push $R5

    StrCpy $R2 ""
    StrLen $R3 $R0
    StrLen $R4 $R1
    IntCmp $R4 $R3 0 no_match match
match:
    StrCpy $R5 0
    ${Do}
        StrCpy $R2 $R1 $R3 $R5
        ${If} $R2 == $R0
            StrCpy $R5 1
            ${ExitDo}
        ${EndIf}
        IntOp $R5 $R5 + 1
        IntCmp $R5 $R4 done loop done
loop:
    ${Loop}
done:
    ${If} $R5 == 1
        StrCpy $R0 $R2
    ${Else}
no_match:
        StrCpy $R0 ""
    ${EndIf}

    Pop $R5
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function _EnvVarUpdate_StripSemicolons
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

    StrCpy $0 0 ; Default success

    ${If} $R1 != "A"
    ${AndIf} $R1 != "R"
        StrCpy $0 2 ; Invalid action
        Goto un_done
    ${EndIf}

    Push $R3
    Call un._EnvVarUpdate_Unquote
    Pop $R3

    ${If} $R2 == "HKLM"
        Goto un_do_hklm
    ${ElseIf} $R2 == "HKCU"
        Goto un_do_hkcu
    ${Else}
        StrCpy $0 1
        Goto un_done
    ${EndIf}

un_do_hklm:
    SetShellVarContext all
    ClearErrors
    ReadRegStr $2 HKLM "${ENV_HKLM}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        StrCpy $1 ""
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            Push ";$2;"
            Push ";$R3;"
            Call un._EnvVarUpdate_StrStr
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
            Push "$R3"
            Call un._EnvVarUpdate_StrStr
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}
            StrCpy $4 $4 -$6
            StrCpy $5 "$4$5"
            Push $5
            Call un._EnvVarUpdate_StripSemicolons
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
        StrCpy $0 3
    Goto un_broadcast

un_do_hkcu:
    SetShellVarContext current
    ClearErrors
    ReadRegStr $2 HKCU "${ENV_HKCU}" $R0
    IfErrors 0 +2
        StrCpy $2 ""

    ${If} $R1 == "A"
        StrCpy $1 ""
        ${If} $2 == ""
            StrCpy $1 $R3
        ${Else}
            Push ";$2;"
            Push ";$R3;"
            Call un._EnvVarUpdate_StrStr
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
            Push "$R3"
            Call un._EnvVarUpdate_StrStr
            Pop $4
            ${If} $4 == ""
                ${ExitDo}
            ${EndIf}
            StrCpy $4 $4 -$6
            StrCpy $5 "$4$5"
            Push $5
            Call un._EnvVarUpdate_StripSemicolons
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
        StrCpy $0 3

un_broadcast:
    SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000

un_done:
    StrCpy $R0 $0
    Pop $6
    Pop $5
    Pop $4
    Pop $3
    Pop $2
    Pop $1
    Pop $0
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_Unquote
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

    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

Function un._EnvVarUpdate_StrStr
    Exch $R0 ; Needle
    Exch
    Exch $R1 ; Haystack
    Push $R2
    Push $R3
    Push $R4
    Push $R5

    StrCpy $R2 ""
    StrLen $R3 $R0
    StrLen $R4 $R1
    IntCmp $R4 $R3 0 un_no_match_strstr un_start
un_start:
    StrCpy $R5 0
un_loop_strstr:
    StrCpy $R2 $R1 $R3 $R5
    ${If} $R2 == $R0
        StrCpy $R0 $R2
        Goto un_done_str_strstr
    ${EndIf}
    IntOp $R5 $R5 + 1
    IntCmp $R5 $R4 un_no_match_strstr un_loop_strstr un_no_match_strstr
un_no_match_strstr:
    StrCpy $R0 ""
un_done_str_strstr:
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