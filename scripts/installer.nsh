!include "EnvVarUpdate.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

; 自定义安装页面 - 询问是否添加 PATH
Var Dialog
Var CheckBox_AddToPath
Var CheckBox_AddDesktopShortcut
Var CheckBox_AddStartMenuShortcut

; 安装前的页面
!macro customPagePre
    !insertmacro MUI_HEADER_TEXT "选择附加任务" "选择安装时需要执行的附加任务"

    nsDialogs::Create 1018
    Pop $Dialog

    ${If} $Dialog == error
        Abort
    ${EndIf}

    ; 添加 PATH 选项
    ${NSD_CreateCheckbox} 0 0 100% 12u "添加到系统 PATH 环境变量（命令行可直接运行）"
    Pop $CheckBox_AddToPath
    ${NSD_Check} $CheckBox_AddToPath

    ; 说明文字
    ${NSD_CreateLabel} 20u 12u 90% 20u "将 Video Capture 的 bin 目录（包含 ffmpeg 等工具）添加到系统 PATH，方便在命令行中使用。"
    Pop $0

    nsDialogs::Show
!macroend

; 自定义安装过程
!macro customInstall
    DetailPrint "正在配置环境变量..."

    ; 定义要添加到 PATH 的路径
    ${If} $CheckBox_AddToPath == ${BST_CHECKED}
        ; 添加 bin 目录（ffmpeg 等工具）到系统 PATH
        ${EnvVarUpdate} $0 "PATH" "A" "HKLM" "$INSTDIR\bin"
        DetailPrint "已添加 bin 目录到系统 PATH: $INSTDIR\bin"

        ${If} $0 != 0
            DetailPrint "警告: 添加 PATH 时出现错误 (错误码: $0)"
        ${Else}
            DetailPrint "成功添加 PATH 环境变量"
        ${EndIf}
    ${Else}
        DetailPrint "跳过 PATH 环境变量配置"
    ${EndIf}

    ; 将 video-capture-server 目录内容展平到根目录
    ${If} ${FileExists} "$INSTDIR\video-capture-server\*.*"
        CopyFiles /SILENT "$INSTDIR\video-capture-server\*" "$INSTDIR"
        RMDir /r "$INSTDIR\video-capture-server"
        DetailPrint "已将 video-capture-server 内容展平到根目录"
    ${EndIf}

    ; 创建启动脚本
    FileOpen $0 "$INSTDIR\start_server.bat" w
    FileWrite $0 '@echo off$\r$\n'
    FileWrite $0 'chcp 65001 >nul$\r$\n'
    FileWrite $0 'title Video Capture Server$\r$\n'
    FileWrite $0 'echo ========================================$\r$\n'
    FileWrite $0 'echo   Video Capture Server$\r$\n'
    FileWrite $0 'echo ========================================$\r$\n'
    FileWrite $0 'echo.$\r$\n'
    FileWrite $0 'echo Starting server at http://localhost:8000$\r$\n'
    FileWrite $0 'echo Press Ctrl+C to stop$\r$\n'
    FileWrite $0 'echo.$\r$\n'
    FileWrite $0 'cd /d "%~dp0"$\r$\n'
    FileWrite $0 'video-capture-server.exe$\r$\n'
    FileWrite $0 'pause$\r$\n'
    FileClose $0

    DetailPrint "已创建启动脚本: start_server.bat"
!macroend

; 自定义卸载过程
!macro customUnInstall
    DetailPrint "正在清理环境变量..."

    ; 从 PATH 中移除 bin 目录
    ${un.EnvVarUpdate} $0 "PATH" "R" "HKLM" "$INSTDIR\bin"
    DetailPrint "已从系统 PATH 移除: $INSTDIR\bin"

    ; 移除旧版本可能残留的 PATH 条目
    ${un.EnvVarUpdate} $0 "PATH" "R" "HKLM" "$INSTDIR"
    ${un.EnvVarUpdate} $0 "PATH" "R" "HKLM" "$INSTDIR\video-capture-server"

    DetailPrint "环境变量清理完成"
!macroend

