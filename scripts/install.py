"""完整打包脚本：后端 PyInstaller + 前端 Electron → release/

用法:
    python scripts/install.py              # 完整打包
    python scripts/install.py --clean      # 清理后打包
    python scripts/install.py --skip-backend   # 跳过后端
    python scripts/install.py --skip-frontend  # 跳过前端
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = ROOT / "release"
GUI_DIR = ROOT / "gui"
GUI_RELEASE_DIR = GUI_DIR / "release"


def run(cmd, cwd=None, env=None):
    print(f"  → {' '.join(cmd)}")
    # Windows 下 npm 等是 .cmd 文件，需 shell=True 才能找到
    subprocess.check_call(cmd, cwd=cwd, env=env, shell=True)


def get_version() -> str:
    """从 pyproject.toml 读取版本号。"""
    toml_path = ROOT / "pyproject.toml"
    content = toml_path.read_text(encoding="utf-8")
    m = re.search(r'version\s*=\s*"([^"]+)"', content)
    if m:
        return m.group(1)
    return "0.1.0"


def build_backend(clean: bool, compress: bool):
    print("=" * 56)
    print("  第 1/2 步: 后端打包 (PyInstaller)")
    print("=" * 56)

    args = [sys.executable, str(ROOT / "scripts" / "build.py")]
    if clean:
        args.append("--clean")
    if not compress:
        args.append("--no-compress")
    run(args, cwd=ROOT)


def build_frontend():
    print()
    print("=" * 56)
    print("  第 2/2 步: 前端打包 (Electron)")
    print("=" * 56)

    # 检查 node_modules 是否存在
    if not (GUI_DIR / "node_modules").exists():
        print("  安装 GUI 依赖...")
        run(["npm", "install"], cwd=GUI_DIR)

    run(["npm", "run", "electron:build"], cwd=GUI_DIR)


def collect_release(version: str):
    print()
    print("=" * 56)
    print("  收集安装包到 release/")
    print("=" * 56)

    shutil.rmtree(RELEASE_DIR, ignore_errors=True)
    RELEASE_DIR.mkdir(parents=True)

    copied = []

    # NSIS 安装包
    setup_exe = GUI_RELEASE_DIR / f"Video Capture Setup {version}.exe"
    if setup_exe.exists():
        shutil.copy2(setup_exe, RELEASE_DIR / setup_exe.name)
        copied.append(setup_exe.name)

    # zip 分发包
    zip_file = GUI_RELEASE_DIR / f"Video Capture-{version}-win.zip"
    if zip_file.exists():
        shutil.copy2(zip_file, RELEASE_DIR / zip_file.name)
        copied.append(zip_file.name)

    if not copied:
        print("  ⚠ 未找到安装包，请确认 gui/release/ 下生成了文件")
        return

    for name in copied:
        path = RELEASE_DIR / name
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  ✓ {name}  ({size_mb:.1f} MB)")

    print(f"\n✅ 完成 → {RELEASE_DIR}")


def main():
    parser = argparse.ArgumentParser(description="完整打包脚本")
    parser.add_argument("--clean", action="store_true", help="打包前清理")
    parser.add_argument("--no-compress", action="store_true", help="跳过 UPX 压缩")
    parser.add_argument("--skip-backend", action="store_true", help="跳过后端打包")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端打包")
    args = parser.parse_args()

    os.chdir(ROOT)
    version = get_version()
    print(f"Video Capture v{version} 完整打包")
    print()

    if args.clean:
        print("🧹 清理构建缓存...")
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "dist", ignore_errors=True)
        shutil.rmtree(GUI_RELEASE_DIR, ignore_errors=True)
        shutil.rmtree(GUI_DIR / "dist", ignore_errors=True)
        for spec in ROOT.glob("*.spec"):
            spec.unlink()
        print("  清理完成")
        print()

    if not args.skip_backend:
        build_backend(clean=False, compress=not args.no_compress)
    else:
        print("⏭ 跳过后端打包")
        print()

    if not args.skip_frontend:
        build_frontend()
    else:
        print("⏭ 跳过前端打包")
        print()

    collect_release(version)


if __name__ == "__main__":
    main()
