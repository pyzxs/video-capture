const { app, BrowserWindow, Menu, dialog, ipcMain, Tray, nativeImage } = require('electron')
const path = require('path')
const { spawn } = require('child_process')

let mainWindow
let tray
let isQuitting = false
let backendProcess = null

// ── 后端 exe 路径 ──

function getBackendExePath() {
  const isDev = process.env.NODE_ENV !== 'production'
  if (isDev) {
    // 开发模式：假设后端已通过 python main.py 单独启动
    return null
  }
  // 生产模式：extraResources 将后端打包到 resources/
  const exeName = process.platform === 'win32' ? 'video-capture-server.exe' : 'video-capture-server'
  return path.join(process.resourcesPath, 'video-capture-server', exeName)
}

// ── 后端进程管理 ──

function startBackend() {
  const exePath = getBackendExePath()
  if (!exePath) {
    console.log('[backend] 开发模式，请手动启动后端: python main.py')
    return
  }

  console.log('[backend] 启动:', exePath)
  try {
    backendProcess = spawn(exePath, [], {
      cwd: path.dirname(exePath),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })

    backendProcess.stdout.on('data', (data) => {
      console.log(`[backend] ${data.toString().trim()}`)
    })
    backendProcess.stderr.on('data', (data) => {
      console.error(`[backend] ${data.toString().trim()}`)
    })
    backendProcess.on('error', (err) => {
      console.error('[backend] 启动失败:', err.message)
    })
    backendProcess.on('close', (code) => {
      console.log(`[backend] 进程退出, code=${code}`)
      backendProcess = null
      // 非主动退出时自动重启
      if (!isQuitting && code !== 0) {
        console.log('[backend] 3 秒后重试...')
        setTimeout(startBackend, 3000)
      }
    })
  } catch (e) {
    console.error('[backend] 启动异常:', e.message)
  }
}

function stopBackend() {
  if (!backendProcess) return
  console.log('[backend] 正在关闭...')
  // Windows 下 spawn 的进程树需要 taskkill
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'], { windowsHide: true })
  } else {
    backendProcess.kill('SIGTERM')
  }
  backendProcess = null
}

// ── 窗口 ──

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    titleBarStyle: 'hidden',
    frame: false,
    icon: path.join(__dirname, '../video-capture.ico'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  const isDev = process.env.NODE_ENV !== 'production'
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
}

// ── 托盘 ──

function createTray() {
  const iconPath = path.join(__dirname, '../video-capture.ico')
  const icon = nativeImage.createFromPath(iconPath)
  const trayIcon = icon.resize({ width: 16, height: 16 })

  tray = new Tray(trayIcon)
  tray.setToolTip('Video Capture')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示界面',
      click: () => {
        mainWindow.show()
        mainWindow.focus()
      },
    },
    {
      label: '退出',
      click: () => {
        isQuitting = true
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)
  tray.on('double-click', () => {
    mainWindow.show()
    mainWindow.focus()
  })
}

// ── IPC ──

ipcMain.on('window-minimize', () => mainWindow?.minimize())
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})
ipcMain.on('window-close', () => mainWindow?.close())

ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  })
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  return result.filePaths[0]
})

ipcMain.handle('select-files', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: '媒体文件', extensions: ['mp4', 'avi', 'mov', 'mkv', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a'] },
      { name: '全部文件', extensions: ['*'] },
    ],
  })
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  return result.filePaths
})

// 前端可查询后端是否在线
ipcMain.handle('backend-status', () => {
  return { running: backendProcess !== null }
})

// ── 应用生命周期 ──

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  startBackend()
  createWindow()
  createTray()
})

app.on('before-quit', () => {
  isQuitting = true
  stopBackend()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
