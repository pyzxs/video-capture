/**
 * electron-builder afterPack hook
 * 1. 删除多余语言包，保留 zh-CN 和 en-US
 * 2. 嵌入 Windows 应用清单 (app.manifest)，解决 DPI 缩放 / 长路径 / 兼容性等问题
 */

const fs = require('fs');
const path = require('path');

exports.default = async function (context) {
  const { rcedit } = await import('rcedit');
  const appOutDir = context.appOutDir;

  // ── 1. 移除多余语言包 ──
  const localesDir = path.join(appOutDir, 'locales');
  if (fs.existsSync(localesDir)) {
    const keep = new Set(['zh-CN.pak', 'en-US.pak', 'en.pak']);
    const removed = [];
    for (const file of fs.readdirSync(localesDir)) {
      if (!keep.has(file) && file.endsWith('.pak')) {
        fs.unlinkSync(path.join(localesDir, file));
        removed.push(file);
      }
    }
    if (removed.length > 0) {
      console.log(`[afterPack] 移除了 ${removed.length} 个多余语言包 (保留: ${[...keep].join(', ')})`);
    }
  }

  // ── 2. 嵌入 Windows 应用清单 ──
  const manifestPath = path.join(__dirname, '..', 'build', 'app.manifest');
  if (!fs.existsSync(manifestPath)) {
    console.warn('[afterPack] manifest 文件不存在，跳过: ' + manifestPath);
    return;
  }

  // 查找需要嵌入 manifest 的 exe
  const exeFiles = [];
  if (context.packager.appInfo) {
    // Electron 主程序 exe（Video Capture.exe）
    const mainExe = path.join(appOutDir, context.packager.appInfo.productFilename + '.exe');
    if (fs.existsSync(mainExe)) {
      exeFiles.push(mainExe);
    }
  }

  // 后端 exe (video-capture-server.exe)
  const backendExe = path.join(appOutDir, 'backend', 'video-capture-server.exe');
  if (fs.existsSync(backendExe)) {
    exeFiles.push(backendExe);
  }

  for (const exePath of exeFiles) {
    try {
      console.log(`[afterPack] 嵌入 manifest -> ${path.basename(exePath)}`);
      await rcedit(exePath, {
        'application-manifest': manifestPath,
      });
      console.log(`[afterPack] manifest 嵌入完成 -> ${path.basename(exePath)}`);
    } catch (err) {
      console.error(`[afterPack] 嵌入失败 (${path.basename(exePath)}):`, err.message);
    }
  }
};
