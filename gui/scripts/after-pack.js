/**
 * electron-builder afterPack hook — 删除用不着的语言包，保留 zh-CN 和 en-US。
 * 节省 ~40MB 安装体积。
 */
const fs = require('fs');
const path = require('path');

exports.default = async function (context) {
  const localesDir = path.join(context.appOutDir, 'locales');
  if (!fs.existsSync(localesDir)) return;

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
};
