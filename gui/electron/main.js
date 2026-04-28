const { app, BrowserWindow, Menu, dialog, ipcMain, Tray, nativeImage } = require('electron')
const path = require('path')

let mainWindow
let tray
let isQuitting = false

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    titleBarStyle: 'hidden',
    frame: false,
    icon: path.join(__dirname, '../../resource/image/app.ico'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  const isDev = process.env.NODE_ENV !== 'production'
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173')
    // mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'))
  }

  // 关闭窗口时隐藏到系统托盘，而不是退出
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
}

function createTray() {
  // 创建一个 16x16 的托盘图标
  const size = 16
  const buffer = Buffer.alloc(size * size * 4)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const idx = (y * size + x) * 4
      const cx = 8, cy = 8, r = 7
      if (Math.sqrt((x - cx) ** 2 + (y - cy) ** 2) <= r) {
        buffer[idx] = 0x33
        buffer[idx + 1] = 0x99
        buffer[idx + 2] = 0xFF
        buffer[idx + 3] = 0xFF
      }
    }
  }
  const icon = nativeImage.createFromBuffer(buffer, { width: size, height: size })

  tray = new Tray(icon)
  tray.setToolTip('视频采集')

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

  // 双击托盘图标显示窗口
  tray.on('double-click', () => {
    mainWindow.show()
    mainWindow.focus()
  })
}

// 窗口控制
ipcMain.on('window-minimize', () => mainWindow?.minimize())
ipcMain.on('window-maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})
ipcMain.on('window-close', () => mainWindow?.close())

// 打开系统目录选择对话框
ipcMain.handle('select-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  })
  if (result.canceled || result.filePaths.length === 0) {
    return null
  }
  return result.filePaths[0]
})

app.whenReady().then(() => {
  Menu.setApplicationMenu(null)
  createWindow()
  createTray()
})

app.on('before-quit', () => {
  isQuitting = true
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
