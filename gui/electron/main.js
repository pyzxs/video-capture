const { app, BrowserWindow, Menu, dialog, ipcMain, Tray, nativeImage, shell } = require('electron')
const path = require('path')
const { spawn } = require('child_process')
const http = require('http')

// ── 单实例锁 ──
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', async () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
    // 确保后端仍在运行（窗口隐藏期间可能被意外关闭）
    if (!backendReady) {
      await startBackend()
      await waitForBackend()
    }
  })

let mainWindow
let tray
let isQuitting = false
let backendProcess = null
let backendReady = false

// ── 后端 exe 路径 ──

function getBackendExePath() {
  if (!app.isPackaged) {
    return null
  }
  const exeName = process.platform === 'win32' ? 'video-capture-server.exe' : 'video-capture-server'
  const resourcesPath = process.resourcesPath
  const appRoot = path.dirname(resourcesPath)
  const fs = require('fs')

  // electron-builder extraFiles 默认路径: resources/backend/video-capture-server.exe
  const backendDir = path.join(resourcesPath, 'backend', exeName)
  if (fs.existsSync(backendDir)) return backendDir

  // 兼容: 平铺在 appRoot
  const candidate = path.join(appRoot, exeName)
  if (fs.existsSync(candidate)) return candidate

  // 兼容旧版: video-capture-server/ 子目录
  const nested = path.join(appRoot, 'video-capture-server', exeName)
  if (fs.existsSync(nested)) return nested

  return backendDir
}

// ── 后端进程管理 ──

function checkBackendRunning() {
  return new Promise((resolve) => {
    const req = http.get('http://127.0.0.1:8090/api/health', { timeout: 1500 }, (res) => {
      resolve(res.statusCode === 200)
    })
    req.on('error', () => resolve(false))
    req.setTimeout(1500, () => { req.destroy(); resolve(false) })
  })
}

async function startBackend() {
  const exePath = getBackendExePath()
  if (!exePath) {
    console.log('[backend] 开发模式，请手动启动后端: python main.py')
    backendReady = true
    return
  }

  // 检查后端是否已在运行（上次关闭窗口后守护进程仍存活）
  const alreadyRunning = await checkBackendRunning()
  if (alreadyRunning) {
    console.log('[backend] 检测到已有后端进程，复用')
    backendReady = true
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
      backendReady = false
      if (!isQuitting && code !== 0) {
        console.log('[backend] 3 秒后重试...')
        setTimeout(() => { startBackend(); waitForBackend() }, 3000)
      }
    })
  } catch (e) {
    console.error('[backend] 启动异常:', e.message)
  }
}

function waitForBackend(retries = 30) {
  return new Promise((resolve) => {
    let attempt = 0
    function check() {
      attempt++
      const req = http.get('http://127.0.0.1:8090/api/health', (res) => {
        if (res.statusCode === 200) {
          backendReady = true
          console.log('[backend] 服务就绪 (尝试 %d 次)', attempt)
          resolve(true)
        } else {
          retry()
        }
      })
      req.on('error', () => retry())
      req.setTimeout(2000, () => { req.destroy(); retry() })
    }
    function retry() {
      if (attempt >= retries) {
        console.error('[backend] 等待超时 (%d 次尝试)', retries)
        backendReady = true  // 不再阻塞，让前端显示连接错误
        resolve(false)
        return
      }
      setTimeout(check, 1000)
    }
    check()
  })
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

  if (!app.isPackaged) {
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

// 打开系统默认浏览器
ipcMain.handle('open-external', (_, url) => {
  return shell.openExternal(url)
})

// 前端可查询后端状态
ipcMain.handle('backend-status', async () => {
  const running = await checkBackendRunning()
  return { running, ready: backendReady }
})

// 前端手动启动后端
ipcMain.handle('start-backend', async () => {
  if (backendReady) {
    const running = await checkBackendRunning()
    if (running) return { success: true, message: '已就绪' }
    backendReady = false
  }
  await startBackend()
  const ready = await waitForBackend()
  return { success: ready, message: ready ? '启动成功' : '启动超时' }
})

// ── 应用生命周期 ──

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  startBackend()
  await waitForBackend()
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

} // else 块结束（单实例锁）
