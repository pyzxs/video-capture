; Video Capture 自定义安装脚本
; electron-builder 钩子：通过 nsis.include 引入
; bin/ 已内置在安装目录 backend\bin 下，Whisper 模型由前端首次启动从 CMS 下载

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

!ifndef WM_SETTINGCHANGE
!define WM_SETTINGCHANGE 0x001A
!endif

Var Dialog
Var CheckBox_AddToPath
Var CheckBox_AddDesktopShortcut
Var CheckBox_AddStartMenuShortcut

!macro customPageAfterChangeDir
    Page custom createCustomPage
!macroend

Function createCustomPage
    !insertmacro MUI_HEADER_TEXT "选择附加任务" "选择安装时需要执行的附加任务"

    nsDialogs::Create 1018
    Pop $Dialog

    ${If} $Dialog == error
        Abort
    ${EndIf}

    ; PATH 复选框
    ${NSD_CreateCheckbox} 0 0 100% 12u "将 ffmpeg 等工具添加到用户 PATH 环境变量"
    Pop $CheckBox_AddToPath
    ${NSD_Check} $CheckBox_AddToPath

    ; 桌面快捷方式
    ${NSD_CreateCheckbox} 0 40u 100% 12u "创建桌面快捷方式"
    Pop $CheckBox_AddDesktopShortcut
    ${NSD_Check} $CheckBox_AddDesktopShortcut

    ; 开始菜单
    ${NSD_CreateCheckbox} 0 60u 100% 12u "创建开始菜单快捷方式"
    Pop $CheckBox_AddStartMenuShortcut
    ${NSD_Check} $CheckBox_AddStartMenuShortcut

    nsDialogs::Show
FunctionEnd

; ── 辅助函数：字符串替换（全部替换） ──
; 输入: 栈顶 = 源字符串, 次顶 = 要替换的子串
; 输出: 栈顶 = 替换后字符串（删除所有匹配）
Function StrRemove
    Exch $R0          ; 要删除的子串
    Exch
    Exch $R1          ; 源字符串
    Push $R2
    Push $R3
    Push $R4
    Push $R5

    StrLen $R3 $R0    ; 子串长度
    StrLen $R4 $R1    ; 源长度
    StrCpy $R2 ""     ; 结果
    StrCpy $R5 0      ; 当前位置

    ${While} $R5 < $R4
        StrCpy $R6 $R1 $R3 $R5
        ${If} $R6 == $R0
            IntOp $R5 $R5 + $R3
        ${Else}
            StrCpy $R7 $R1 1 $R5
            StrCpy $R2 "$R2$R7"
            IntOp $R5 $R5 + 1
        ${EndIf}
    ${EndWhile}

    StrCpy $R0 $R2
    Pop $R5
    Pop $R4
    Pop $R3
    Pop $R2
    Pop $R1
    Exch $R0
FunctionEnd

!macro customInstall
    ; PATH 环境变量 — 直接注册表写入，不依赖外部脚本
    ${NSD_GetState} $CheckBox_AddToPath $1
    ${If} $1 == ${BST_CHECKED}
        DetailPrint "正在配置 PATH 环境变量..."
        ReadRegStr $0 HKCU "Environment" "PATH"
        ${If} $0 == ""
            WriteRegExpandStr HKCU "Environment" "PATH" "$INSTDIR\backend\bin"
        ${Else}
            WriteRegExpandStr HKCU "Environment" "PATH" "$0;$INSTDIR\backend\bin"
        ${EndIf}
        SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000
        DetailPrint "  已添加 PATH: $INSTDIR\backend\bin"
    ${Else}
        DetailPrint "跳过 PATH 配置"
    ${EndIf}

    ; 桌面快捷方式
    ${If} $CheckBox_AddDesktopShortcut == ${BST_CHECKED}
        CreateShortCut "$DESKTOP\Video Capture.lnk" "$INSTDIR\Video Capture.exe"
        DetailPrint "已创建桌面快捷方式"
    ${EndIf}

    ; 开始菜单
    ${If} $CheckBox_AddStartMenuShortcut == ${BST_CHECKED}
        CreateDirectory "$SMPROGRAMS\Video Capture"
        CreateShortCut "$SMPROGRAMS\Video Capture\Video Capture.lnk" "$INSTDIR\Video Capture.exe"
        CreateShortCut "$SMPROGRAMS\Video Capture\卸载.lnk" "$INSTDIR\Uninstall.exe"
        DetailPrint "已创建开始菜单快捷方式"
    ${EndIf}
!macroend

!macro customUnInstall
    MessageBox MB_YESNO|MB_ICONQUESTION "是否保留 %APPDATA%\Video Capture 中的数据（视频、日志、下载的模型等）？$\n$\n选择'是'保留，选择'否'全部删除。" IDYES keep_data

    ; 从 PATH 移除当前安装路径
    DetailPrint "正在清理 PATH 环境变量..."
    ReadRegStr $0 HKCU "Environment" "PATH"
    ${If} $0 != ""
        Push "$0"
        Push ";$INSTDIR\backend\bin"
        Call StrRemove
        Pop $1
        Push "$1"
        Push "$INSTDIR\backend\bin;"
        Call StrRemove
        Pop $2
        ; 去掉首尾多余分号
        Push "$2"
        Push ";;"
        Call StrRemove
        Pop $3
        ${If} $3 == ""
            DeleteRegValue HKCU "Environment" "PATH"
            DetailPrint "  已移除 PATH 条目"
        ${ElseIf} $3 == $0
            DetailPrint "  未找到 PATH 条目，跳过"
        ${Else}
            WriteRegExpandStr HKCU "Environment" "PATH" "$3"
            DetailPrint "  已从 PATH 移除: $INSTDIR\backend\bin"
        ${EndIf}
        SendMessage ${HWND_BROADCAST} ${WM_SETTINGCHANGE} 0 "STR:Environment" /TIMEOUT=5000
    ${Else}
        DetailPrint "  用户 PATH 为空，无需清理"
    ${EndIf}

    ; 快捷方式
    ${If} ${FileExists} "$DESKTOP\Video Capture.lnk"
        Delete "$DESKTOP\Video Capture.lnk"
    ${EndIf}
    ${If} ${FileExists} "$SMPROGRAMS\Video Capture"
        RMDir /r "$SMPROGRAMS\Video Capture"
    ${EndIf}

    Goto delete_data

keep_data:
    DetailPrint "保留 %APPDATA%\Video Capture 中的数据"
    Goto done

delete_data:
    nsExec::ExecToLog 'taskkill /f /im video-capture-server.exe'
    Sleep 1500
    ${If} ${FileExists} "$APPDATA\Video Capture"
        RMDir /r /REBOOTOK "$APPDATA\Video Capture"
        ${If} ${FileExists} "$APPDATA\Video Capture"
            DetailPrint "部分文件无法立即删除，已安排在下次系统重启时清理"
        ${Else}
            DetailPrint "已删除 %APPDATA%\Video Capture"
        ${EndIf}
    ${EndIf}

done:
!macroend
