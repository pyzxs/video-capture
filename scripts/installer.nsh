; Installer.nsh
; Video Capture Installer Script

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "EnvVarUpdate.nsh"
!include "UserInfo.nsh"

; 自定义变量
Var Dialog
Var CheckBox_AddToPath
Var CheckBox_AddDesktopShortcut
Var CheckBox_AddStartMenuShortcut
Var InstallPath

; 安装程序初始化
Function .onInit
    ; 检查管理员权限
    UserInfo::GetAccountType
    Pop $0
    ${If} $0 != "admin"
    ${AndIf} $0 != "Administrator"
        MessageBox MB_ICONSTOP "安装需要管理员权限！$\n$\n请右键点击安装程序，选择"以管理员身份运行"。" 
        Abort
    ${EndIf}
    
    ; 初始化复选框状态
    StrCpy $CheckBox_AddToPath ${BST_CHECKED}
    StrCpy $CheckBox_AddDesktopShortcut ${BST_CHECKED}
    StrCpy $CheckBox_AddStartMenuShortcut ${BST_CHECKED}
    
    ; 设置默认安装路径
    StrCpy $InstallPath "$PROGRAMFILES\Video Capture"
FunctionEnd

; 自定义安装页面
!macro customPage
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
    
    ; 桌面快捷方式选项
    ${NSD_CreateCheckbox} 0 40u 100% 12u "创建桌面快捷方式"
    Pop $CheckBox_AddDesktopShortcut
    ${NSD_Check} $CheckBox_AddDesktopShortcut
    
    ; 开始菜单快捷方式选项
    ${NSD_CreateCheckbox} 0 60u 100% 12u "创建开始菜单快捷方式"
    Pop $CheckBox_AddStartMenuShortcut
    ${NSD_Check} $CheckBox_AddStartMenuShortcut
    
    nsDialogs::Show
!macroend

; 自定义安装过程
!macro customInstall
    DetailPrint "========================================="
    DetailPrint "开始安装配置..."
    DetailPrint "========================================="
    
    ; 创建必要的目录结构
    DetailPrint "正在创建目录结构..."
    
    
    ; 创建 logs 目录（用于存放日志文件）
    CreateDirectory "$INSTDIR\logs"
    DetailPrint "✓ 已创建 logs 目录: $INSTDIR\logs"
    
    ; 创建 storage 目录（用于存放数据文件）
    CreateDirectory "$INSTDIR\storage"
    DetailPrint "✓ 已创建 storage 目录: $INSTDIR\storage"
    
    ; 配置环境变量
    DetailPrint "正在配置环境变量..."
    
    ${If} $CheckBox_AddToPath == ${BST_CHECKED}
        ; 添加 bin 目录到系统 PATH
        ${EnvVarUpdate} $0 "PATH" "A" "HKLM" "$INSTDIR\bin"
        
        ${If} $0 == 0
            DetailPrint "✓ 成功添加 PATH 环境变量: $INSTDIR\bin"
        ${Else}
            ${If} $0 == 4
                DetailPrint "✗ 警告: PATH 添加失败 - 无效的操作类型"
            ${ElseIf} $0 == 5
                DetailPrint "✗ 警告: PATH 添加失败 - 无效的注册表位置"
            ${Else}
                DetailPrint "✗ 警告: PATH 添加失败 - 错误码: $0"
            ${EndIf}
            MessageBox MB_ICONWARNING "无法自动添加 PATH 环境变量。$\n$\n请手动将以下路径添加到系统 PATH：$\n$\n$INSTDIR\bin"
        ${EndIf}
    ${Else}
        DetailPrint "跳过 PATH 环境变量配置"
    ${EndIf}
    
    
    ; 创建快捷方式
    ${If} $CheckBox_AddDesktopShortcut == ${BST_CHECKED}
        CreateShortCut "$DESKTOP\Video Capture.lnk" "$INSTDIR\start_server.bat" "" "$INSTDIR\video-capture-server.exe" 0
        DetailPrint "✓ 已创建桌面快捷方式"
    ${EndIf}
    
    ${If} $CheckBox_AddStartMenuShortcut == ${BST_CHECKED}
        CreateDirectory "$SMPROGRAMS\Video Capture"
        CreateShortCut "$SMPROGRAMS\Video Capture\Start Server.lnk" "$INSTDIR\start_server.bat"
        CreateShortCut "$SMPROGRAMS\Video Capture\Stop Server.lnk" "$INSTDIR\stop_server.bat"
        CreateShortCut "$SMPROGRAMS\Video Capture\Clean Logs.lnk" "$INSTDIR\clean_logs.bat"
        CreateShortCut "$SMPROGRAMS\Video Capture\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
        CreateShortCut "$SMPROGRAMS\Video Capture\README.lnk" "$INSTDIR\README.txt"
        CreateShortCut "$SMPROGRAMS\Video Capture\Logs Directory.lnk" "$INSTDIR\logs"
        CreateShortCut "$SMPROGRAMS\Video Capture\Storage Directory.lnk" "$INSTDIR\storage"
        DetailPrint "✓ 已创建开始菜单快捷方式"
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
    MessageBox MB_YESNO|MB_ICONQUESTION "是否保留 logs 和 storage 目录中的数据？$\n$\n选择"是"将保留数据，选择"否"将删除所有数据。" IDYES keep_data
    
    ; 从 PATH 中移除 bin 目录
    DetailPrint "正在清理环境变量..."
    
    ${un.EnvVarUpdate} $0 "PATH" "R" "HKLM" "$INSTDIR\bin"
    ${If} $0 == 0
        DetailPrint "✓ 已从系统 PATH 移除: $INSTDIR\bin"
    ${Else}
        DetailPrint "⚠ 从 PATH 移除时出现警告 (错误码: $0)"
    ${EndIf}
    
    ; 清理可能存在的旧路径
    ${un.EnvVarUpdate} $0 "PATH" "R" "HKCU" "$INSTDIR\bin"
    
    ; 清理快捷方式
    ${If} ${FileExists} "$DESKTOP\Video Capture.lnk"
        Delete "$DESKTOP\Video Capture.lnk"
        DetailPrint "✓ 已删除桌面快捷方式"
    ${EndIf}
    
    ${If} ${FileExists} "$SMPROGRAMS\Video Capture"
        RMDir /r "$SMPROGRAMS\Video Capture"
        DetailPrint "✓ 已删除开始菜单文件夹"
    ${EndIf}

    
    ; 清理目录
    ${If} ${FileExists} "$INSTDIR\bin"
        RMDir "$INSTDIR\bin"
        DetailPrint "✓ 已删除 bin 目录"
    ${EndIf}
    
    ; 根据用户选择决定是否删除数据目录
    Goto delete_data
    
keep_data:
    DetailPrint "保留 logs 和 storage 目录中的数据"
    Goto cleanup_done
    
delete_data:
    ${If} ${FileExists} "$INSTDIR\logs"
        RMDir /r "$INSTDIR\logs"
        DetailPrint "✓ 已删除 logs 目录及其内容"
    ${EndIf}
    
    ${If} ${FileExists} "$INSTDIR\storage"
        RMDir /r "$INSTDIR\storage"
        DetailPrint "✓ 已删除 storage 目录及其内容"
    ${EndIf}
    
cleanup_done:
    DetailPrint "========================================="
    DetailPrint "清理完成！"
    DetailPrint "========================================="
!macroend

; 页面定义
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "license.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_CUSTOMFUNCTION_PRE customPage
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

; 语言和设置
!insertmacro MUI_LANGUAGE "SimpChinese"

; 安装程序属性
Name "Video Capture"
OutFile "Video Capture_Setup.exe"
InstallDir "$PROGRAMFILES\Video Capture"
InstallDirRegKey HKLM "Software\Video Capture" "InstallPath"
RequestExecutionLevel admin

; 版本信息
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "Video Capture"
VIAddVersionKey "CompanyName" "Your Company"
VIAddVersionKey "FileDescription" "Video Capture Installer"
VIAddVersionKey "FileVersion" "1.0.0"
VIAddVersionKey "ProductVersion" "1.0.0"

; 需要安装的文件
Section "Video Capture" SecMain
    SectionIn RO
    SetOutPath "$INSTDIR"
    
    ; 这里放置需要安装的实际文件
    ; File "..\release\video-capture-server.exe"
    ; File /r "..\release\bin"
    
    ; 写入注册表
    WriteRegStr HKLM "Software\Video Capture" "InstallPath" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "DisplayName" "Video Capture"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "UninstallString" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "DisplayIcon" "$INSTDIR\video-capture-server.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "DisplayVersion" "1.0.0"
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "NoRepair" 1
    
    ; 计算安装大小（可选）
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture" "EstimatedSize" "$0"
    
    ; 创建卸载程序
    WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

; 卸载部分
Section "Uninstall"
    ; 调用自定义卸载宏
    !insertmacro customUnInstall
    
    ; 删除注册表
    DeleteRegKey HKLM "Software\Video Capture"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Video Capture"
    
    ; 如果安装目录为空，则删除
    RMDir "$INSTDIR"
SectionEnd