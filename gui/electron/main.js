const { app, BrowserWindow, Menu, dialog, ipcMain, Tray, nativeImage, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');

// ── 全局状态（必须在单实例回调之前声明，避免 TDZ 错误）──
let mainWindow = null;
let tray = null;
let isQuitting = false;
let backendProcess = null;
let backendReady = false;
let backendStarting = null;  // Promise | null — 防止并发启动
let backendRestartCount = 0;
const MAX_RESTART_COUNT = 5;  // 连续崩溃 N 次后放弃自动重启

// ── 单实例锁 ──
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', async () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
    // 确保后端仍在运行（窗口隐藏期间可能被意外关闭）
    if (!backendReady) {
      await ensureBackend();
    }
  });

  // ── 后端 exe 路径 ──
  function getBackendExePath() {
    if (!app.isPackaged) {
      return null;
    }
    const exeName = process.platform === 'win32' ? 'video-capture-server.exe' : 'video-capture-server';
    const resourcesPath = process.resourcesPath;
    const appRoot = path.dirname(resourcesPath);

    console.log('[backend] app.isPackaged:', app.isPackaged);
    console.log('[backend] process.resourcesPath:', resourcesPath);
    console.log('[backend] appRoot (安装目录):', appRoot);

    const candidates = [path.join(appRoot, 'backend', exeName)];

    for (const p of candidates) {
      console.log('[backend] 检查路径:', p, '| 是否存在:', fs.existsSync(p));
      if (fs.existsSync(p)) {
        console.log('[backend] 找到 exe:', p);
        return p;
      }
    }

    console.error('[backend] 未找到 exe，尝试过的路径:', candidates);
    return candidates[0];
  }

  // ── 后端健康检查 ──
  async function checkBackendRunning() {
    return new Promise((resolve) => {
      const req = http.get('http://127.0.0.1:8090/api/health', { timeout: 1500 }, (res) => {
        resolve(res.statusCode === 200);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(1500, () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  // ── 启动后端进程（不等待就绪）──
  async function startBackend() {
    // 防止并发启动：如果正在启动中，直接等上一次结果
    if (backendStarting) {
      console.log('[backend] 已有启动任务在进行中，等待...');
      return backendStarting;
    }

    const exePath = getBackendExePath();
    if (!exePath) {
      console.log('[backend] 开发模式，请手动启动后端: python main.py');
      backendReady = true;
      return;
    }

    // 检查后端是否已在运行（上次关闭窗口后守护进程仍存活）
    const alreadyRunning = await checkBackendRunning();
    if (alreadyRunning) {
      console.log('[backend] 检测到已有后端进程，复用');
      backendReady = true;
      backendRestartCount = 0;
      return;
    }

    // 文件不存在时直接报错
    if (!fs.existsSync(exePath)) {
      console.error('[backend] exe 文件不存在:', exePath);
      backendReady = true;
      return;
    }

    // 超过最大重启次数，放弃自动重启，等用户手动操作
    if (backendRestartCount >= MAX_RESTART_COUNT) {
      console.error('[backend] 已达最大重启次数 (%d)，停止自动重启', MAX_RESTART_COUNT);
      backendReady = true;
      return;
    }

    console.log('[backend] 启动:', exePath);
    console.log('[backend] cwd:', path.dirname(exePath));
    console.log('[backend] backendRestartCount:', backendRestartCount);

    // 创建启动锁
    let resolveLock;
    backendStarting = new Promise((r) => { resolveLock = r; });

    try {
      backendProcess = spawn(exePath, [], {
        cwd: path.dirname(exePath),
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      });
      console.log('[backend] spawn 成功, pid:', backendProcess.pid);

      backendProcess.stdout.on('data', (data) => {
        console.log(`[backend] ${data.toString().trim()}`);
      });
      backendProcess.stderr.on('data', (data) => {
        console.error(`[backend] ${data.toString().trim()}`);
      });
      backendProcess.on('error', (err) => {
        console.error('[backend] spawn 错误:', err.message);
        backendProcess = null;
        backendReady = true;  // 不再等待，避免 waitForBackend 空等 30 秒
      });
      backendProcess.on('close', (code) => {
        console.log(`[backend] 进程退出, code=${code}`);
        backendProcess = null;
        backendReady = false;
        if (!isQuitting && code !== 0 && code !== null) {
          backendRestartCount++;
          console.log('[backend] 崩溃计数: %d/%d', backendRestartCount, MAX_RESTART_COUNT);
          if (backendRestartCount < MAX_RESTART_COUNT) {
            console.log('[backend] 3 秒后重试...');
            setTimeout(() => {
              startBackend();
              waitForBackend();
            }, 3000);
          } else {
            console.error('[backend] 已达最大重启次数，停止自动重启');
            backendReady = true;
          }
        }
      });
    } catch (e) {
      console.error('[backend] 启动异常:', e.message);
      backendReady = true;
    } finally {
      resolveLock();
      backendStarting = null;
    }
  }

  // ── 等待后端 HTTP 服务就绪 ──
  async function waitForBackend(retries = 30) {
    return new Promise((resolve) => {
      let attempt = 0;
      function check() {
        attempt++;
        const req = http.get('http://127.0.0.1:8090/api/health', (res) => {
          if (res.statusCode === 200) {
            backendReady = true;
            backendRestartCount = 0;
            console.log('[backend] 服务就绪 (尝试 %d 次)', attempt);
            resolve(true);
          } else {
            retry();
          }
        });
        req.on('error', () => retry());
        req.setTimeout(2000, () => {
          req.destroy();
          retry();
        });
      }
      function retry() {
        if (attempt >= retries) {
          console.error('[backend] 等待超时 (%d 次尝试)', retries);
          backendReady = true; // 不再阻塞，让前端显示连接错误
          resolve(false);
          return;
        }
        setTimeout(check, 1000);
      }
      check();
    });
  }

  // ── 确保后端启动并可用（供外部调用）──
  async function ensureBackend() {
    console.log('[backend] ensureBackend 调用, backendReady:', backendReady);
    if (backendReady && (await checkBackendRunning())) {
      console.log('[backend] 后端已在运行，复用');
      backendRestartCount = 0;
      return true;
    }
    console.log('[backend] 启动新后端进程...');
    await startBackend();
    console.log('[backend] 等待后端就绪 (最多 30 次重试)...');
    const ready = await waitForBackend();
    if (ready) {
      console.log('[backend] 后端启动成功');
      backendRestartCount = 0;
    } else {
      console.error('[backend] 后端启动超时或失败');
    }
    return ready;
  }

  // ── 停止后端进程（优先优雅退出，失败则强制）──
  function stopBackend() {
    if (!backendProcess) return;
    console.log('[backend] 正在关闭...');

    const isWin = process.platform === 'win32';
    if (isWin) {
      // 尝试优雅关闭：发送 Ctrl+C 信号（仅对 console 程序有效，简单起见直接用 taskkill）
      // 注意：taskkill /f 是强制结束，/t 结束进程树
      const taskkill = spawn('taskkill', ['/pid', String(backendProcess.pid), '/f', '/t'], {
        windowsHide: true,
      });
      taskkill.on('error', (err) => console.error('[backend] taskkill 失败:', err));
    } else {
      backendProcess.kill('SIGTERM');
      // 若 3 秒未退出则强制杀死
      setTimeout(() => {
        if (backendProcess && !backendProcess.killed) {
          backendProcess.kill('SIGKILL');
        }
      }, 3000);
    }
    backendProcess = null;
    backendReady = false;
  }

  // ── 创建主窗口 ──
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
    });

    if (!app.isPackaged) {
      mainWindow.loadURL('http://localhost:5173');
    } else {
      mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
    }

    mainWindow.on('close', (event) => {
      if (!isQuitting) {
        event.preventDefault();
        mainWindow.hide();
      }
    });
  }

  // ── 创建系统托盘 ──
  function createTray() {
    const iconPath = path.join(__dirname, '../video-capture.ico');
    const icon = nativeImage.createFromPath(iconPath);
    const trayIcon = icon.resize({ width: 16, height: 16 });

    tray = new Tray(trayIcon);
    tray.setToolTip('Video Capture');

    const contextMenu = Menu.buildFromTemplate([
      {
        label: '显示界面',
        click: () => {
          mainWindow.show();
          mainWindow.focus();
        },
      },
      {
        label: '退出',
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]);

    tray.setContextMenu(contextMenu);
    tray.on('double-click', () => {
      mainWindow.show();
      mainWindow.focus();
    });
  }

  // ── IPC 通信 ──
  ipcMain.on('window-minimize', () => mainWindow?.minimize());
  ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });
  ipcMain.on('window-close', () => mainWindow?.close());

  ipcMain.handle('select-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths[0];
  });

  ipcMain.handle('select-files', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: '媒体文件', extensions: ['mp4', 'avi', 'mov', 'mkv', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a'] },
        { name: '全部文件', extensions: ['*'] },
      ],
    });
    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }
    return result.filePaths;
  });

  ipcMain.handle('open-external', (_, url) => {
    return shell.openExternal(url);
  });

  ipcMain.handle('backend-status', async () => {
    const running = await checkBackendRunning();
    return { running, ready: backendReady };
  });

  ipcMain.handle('start-backend', async () => {
    const ready = await ensureBackend();
    return { success: ready, message: ready ? '启动成功' : '启动超时' };
  });

  // ── 应用生命周期 ──
  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null);
    createWindow();
    createTray();
    // 启动后端并等待就绪，但不阻塞窗口显示（窗口会先显示，后端在后台启动）
    ensureBackend(); // 异步执行，不 blocking
  });

  app.on('before-quit', () => {
    isQuitting = true;
    // 后端进程保持运行，作为系统守护进程
    // 下次启动 Video Capture 时会自动检测并复用
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
}