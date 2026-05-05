; Video Capture 自定义安装脚本
; electron-builder 钩子：通过 nsis.include 引入

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "StrFunc.nsh"

; 注册字符串函数（安装段和卸载段都需要）
${StrRep}
${UnStrRep}

; 自定义变量
Var Dialog
Var CheckBox_AddToPath
Var CheckBox_AddDesktopShortcut
Var CheckBox_AddStartMenuShortcut

; 自定义安装页面 — 在安装目录选择之后、开始安装之前显示
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

    ; 添加到 PATH 复选框
    ${NSD_CreateCheckbox} 0 0 100% 12u "添加到系统 PATH 环境变量（命令行可直接运行）"
    Pop $CheckBox_AddToPath
    ${NSD_Check} $CheckBox_AddToPath

    ; 说明文字
    ${NSD_CreateLabel} 20u 12u 90% 20u "将 bin 目录（包含 ffmpeg 等工具）添加到系统 PATH，方便在命令行中使用。"
    Pop $0

    ; 桌面快捷方式复选框
    ${NSD_CreateCheckbox} 0 40u 100% 12u "创建桌面快捷方式"
    Pop $CheckBox_AddDesktopShortcut
    ${NSD_Check} $CheckBox_AddDesktopShortcut

    ; 开始菜单快捷方式复选框
    ${NSD_CreateCheckbox} 0 60u 100% 12u "创建开始菜单快捷方式"
    Pop $CheckBox_AddStartMenuShortcut
    ${NSD_Check} $CheckBox_AddStartMenuShortcut

    nsDialogs::Show
FunctionEnd

; 自定义安装过程
!macro customInstall
    DetailPrint "========================================="
    DetailPrint "开始安装配置..."
    DetailPrint "========================================="

    ; 创建必要的目录结构
    DetailPrint "正在创建目录结构..."
    CreateDirectory "$INSTDIR\logs"
    DetailPrint "已创建 logs 目录: $INSTDIR\logs"
    CreateDirectory "$INSTDIR\storage"
    DetailPrint "已创建 storage 目录: $INSTDIR\storage"

    ; 添加 bin 到系统 PATH
    ${If} $CheckBox_AddToPath == ${BST_CHECKED}
        DetailPrint "正在配置环境变量..."
        ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
        ${If} $0 != ""
            StrCpy $0 "$0;$INSTDIR\bin"
        ${Else}
            StrCpy $0 "$INSTDIR\bin"
        ${EndIf}
        WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" "$0"
        SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
        DetailPrint "已添加 PATH 环境变量: $INSTDIR\bin"
    ${Else}
        DetailPrint "跳过 PATH 环境变量配置"
    ${EndIf}

    ; 创建桌面快捷方式
    ${If} $CheckBox_AddDesktopShortcut == ${BST_CHECKED}
        CreateShortCut "$DESKTOP\Video Capture.lnk" "$INSTDIR\start_server.bat" "" "$INSTDIR\video-capture-server.exe" 0
        DetailPrint "已创建桌面快捷方式"
    ${EndIf}

    ; 创建开始菜单快捷方式
    ${If} $CheckBox_AddStartMenuShortcut == ${BST_CHECKED}
        CreateDirectory "$SMPROGRAMS\Video Capture"
        CreateShortCut "$SMPROGRAMS\Video Capture\Start Server.lnk" "$INSTDIR\start_server.bat"
        CreateShortCut "$SMPROGRAMS\Video Capture\Stop Server.lnk" "$INSTDIR\stop_server.bat"
        CreateShortCut "$SMPROGRAMS\Video Capture\Clean Logs.lnk" "$INSTDIR\clean_logs.bat"
        CreateShortCut "$SMPROGRAMS\Video Capture\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
        CreateShortCut "$SMPROGRAMS\Video Capture\README.lnk" "$INSTDIR\README.txt"
        CreateShortCut "$SMPROGRAMS\Video Capture\Logs Directory.lnk" "$INSTDIR\logs"
        CreateShortCut "$SMPROGRAMS\Video Capture\Storage Directory.lnk" "$INSTDIR\storage"
        DetailPrint "已创建开始菜单快捷方式"
    ${EndIf}

    DetailPrint "========================================="
    DetailPrint "安装配置完成！"
    DetailPrint "========================================="
!macroend

; 自定义卸载过程
!macro customUnInstall
    DetailPrint "========================================="
    DetailPrint "开始清理配置..."
    DetailPrint "========================================="

    ; 询问是否保留数据
    MessageBox MB_YESNO|MB_ICONQUESTION "是否保留 logs 和 storage 目录中的数据？$\n$\n选择'是'将保留数据，选择'否'将删除所有数据。" IDYES keep_data

    ; 从 PATH 中移除 bin 目录
    DetailPrint "正在清理环境变量..."
    ReadRegStr $0 HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path"
    ${If} $0 != ""
        ; 移除 $INSTDIR\bin 及其可能的分隔符
        ${UnStrRep} $0 "$0" "$INSTDIR\bin;" ""
        ${UnStrRep} $0 "$0" ";$INSTDIR\bin" ""
        ${UnStrRep} $0 "$0" "$INSTDIR\bin" ""
        WriteRegExpandStr HKLM "SYSTEM\CurrentControlSet\Control\Session Manager\Environment" "Path" "$0"
        SendMessage ${HWND_BROADCAST} ${WM_WININICHANGE} 0 "STR:Environment" /TIMEOUT=5000
        DetailPrint "已从系统 PATH 移除: $INSTDIR\bin"
    ${EndIf}

    ; 清理快捷方式
    ${If} ${FileExists} "$DESKTOP\Video Capture.lnk"
        Delete "$DESKTOP\Video Capture.lnk"
        DetailPrint "已删除桌面快捷方式"
    ${EndIf}

    ${If} ${FileExists} "$SMPROGRAMS\Video Capture"
        RMDir /r "$SMPROGRAMS\Video Capture"
        DetailPrint "已删除开始菜单文件夹"
    ${EndIf}

    ; 清理 bin 目录（electron-builder 不会自动清理 extraFiles 中的 bin）
    ${If} ${FileExists} "$INSTDIR\bin"
        RMDir /r "$INSTDIR\bin"
        DetailPrint "已删除 bin 目录"
    ${EndIf}

    Goto delete_data

keep_data:
    DetailPrint "保留 logs 和 storage 目录中的数据"
    Goto cleanup_done

delete_data:
    ${If} ${FileExists} "$INSTDIR\logs"
        RMDir /r "$INSTDIR\logs"
        DetailPrint "已删除 logs 目录及其内容"
    ${EndIf}

    ${If} ${FileExists} "$INSTDIR\storage"
        RMDir /r "$INSTDIR\storage"
        DetailPrint "已删除 storage 目录及其内容"
    ${EndIf}

cleanup_done:
    DetailPrint "========================================="
    DetailPrint "清理完成！"
    DetailPrint "========================================="
!macroend
