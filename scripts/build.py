"""后端 PyInstaller 打包脚本。

用法:
    python scripts/build.py                  # 默认打包（无 UPX，无控制台窗口）
    python scripts/build.py --clean          # 清理后打包
    python scripts/build.py --console        # 保留控制台窗口（调试用）
    python scripts/build.py --upx            # 启用 UPX 压缩（⚠️ 增加杀软误报风险）
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

# PyInstaller 不会自动检测的隐藏导入
HIDDEN_IMPORTS = [
    # uvicorn 子模块
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    # fastapi
    "fastapi",
    "fastapi.middleware.cors",
    # faster-whisper + ctranslate2
    "faster_whisper",
    "ctranslate2",
    # huggingface_hub (faster-whisper 下载模型用)
    "huggingface_hub",
    "huggingface_hub.hf_api",
    # sqlalchemy + chromadb
    "sqlalchemy",
    "chromadb",
    "chromadb.db",
    "chromadb.utils.embedding_functions",
    # 项目内部模块
    "src",
    "src.api",
    "src.api.routes",
    "src.db",
    "src.db.models",
    "src.processing",
    "src.pipelines",
    "src.services",
    "src.download",
    "src.migrations",
    "src.http_client",
    # 其他
    "cryptography",
    "cryptography.fernet",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.kdf.pbkdf2",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.backends",
    "lxml",
    "aiohttp",
    "aiofiles",
]

# 需要收集整个包的模块（含二进制 .dll/.so）
COLLECT_PACKAGES = [
    "cryptography",
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
    "chromadb",
    "imageio",
    "imageio_ffmpeg",  # moviepy 导入链需要 imageio.plugins.ffmpeg
    "onnxruntime",
    "typing_extensions",
    "pydantic",
    "pydantic_settings",
]

# 排除的大型/无用包
EXCLUDE_PACKAGES = [
    # GUI / 测试
    "tkinter",
    "test",
    "tests",
    "unittest",
    "pytest",
    "mypy",
    "black",
    "isort",
    "flake8",
    # 包管理
    "setuptools",
    "pip",
    "wheel",
    "distutils",
    # 科学计算 / 数据集（numpy 被 imageio/moviepy 使用，不能排除）
    "scipy",
    "torch",
    "tensorflow",
    "tensorboard",
    "matplotlib",
    "pandas",
    "pandas.tests",
    # Jupyter
    "jupyter",
    "IPython",
    "notebook",
]

# 需要复制包元数据的模块（importlib.metadata.version 用）
COPY_METADATA = [
    "cryptography",
    "imageio",
    "moviepy",
    "numpy",
    "pillow",
]


def run(cmd, **kwargs):
    print(f"  -> {' '.join(cmd)}")
    return subprocess.check_call(cmd, **kwargs)


def find_upx() -> str | None:
    """查找 UPX 可执行文件路径。"""
    for name in ["upx.exe", "upx"]:
        local = ROOT / "bin" / name
        if local.exists():
            return str(local)
    for name in ["upx.exe", "upx"]:
        found = shutil.which(name)
        if found:
            return found
    return None


def clean_artifacts():
    """清理 PyInstaller 生成的中间文件。"""
    for p in [ROOT / "build", ROOT / "video-capture-server.spec"]:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink()


def write_version_file():
    """生成 Windows 版本信息资源文件。"""
    version_txt = ROOT / "build" / "version_info.txt"
    version_txt.parent.mkdir(parents=True, exist_ok=True)

    content = """# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(0, 1, 0, 0),
    prodvers=(0, 1, 0, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'080404b0',
          [
            StringStruct(u'CompanyName', u'Video Capture'),
            StringStruct(u'FileDescription', u'Video Capture Server'),
            StringStruct(u'FileVersion', u'0.1.0'),
            StringStruct(u'InternalName', u'video-capture-server'),
            StringStruct(u'LegalCopyright', u'Copyright (C) 2025'),
            StringStruct(u'OriginalFilename', u'video-capture-server.exe'),
            StringStruct(u'ProductName', u'Video Capture'),
            StringStruct(u'ProductVersion', u'0.1.0'),
          ]
        ),
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])]),
  ]
)
"""
    version_txt.write_text(content, encoding="utf-8")
    return str(version_txt)


def build(use_upx: bool = False, console: bool = False):
    print("=" * 56)
    print("  Video Capture Server - PyInstaller 打包")
    print("=" * 56)

    shutil.rmtree(DIST_DIR, ignore_errors=True)
    clean_artifacts()

    # 生成版本信息
    version_file = write_version_file()

    pyi_args = [
        PYTHON, "-m", "PyInstaller",
        "--distpath", str(DIST_DIR),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
        "--name", "video-capture-server",
        "--onedir",
        "--clean",
        "--noconfirm",
        "--noupx",
        "--version-file", version_file,
    ]

    # 控制台窗口：默认关闭（减少杀软误报），调试时用 --console 开启
    if console:
        pyi_args += ["--console"]
    else:
        pyi_args += ["--windowed"]

    # UPX 压缩：默认关闭（UPX 是杀软误报的首要原因），用 --upx 手动开启
    if use_upx:
        upx_path = find_upx()
        if upx_path:
            pyi_args += ["--upx-dir", str(Path(upx_path).parent)]
            print(f"  UPX: {upx_path} (⚠ 可能增加杀软误报)")
        else:
            print("  提示: 未找到 UPX，跳过二进制压缩（放到 bin/upx.exe 即可启用）")
    else:
        print("  UPX: 已禁用（推荐，减少杀软误报）")

    # 添加隐藏导入
    for mod in HIDDEN_IMPORTS:
        pyi_args += ["--hidden-import", mod]
    print(f"  隐藏导入: {len(HIDDEN_IMPORTS)} 个模块")

    # 收集整个包
    for pkg in COLLECT_PACKAGES:
        pyi_args += ["--collect-all", pkg]
    print(f"  收集包: {len(COLLECT_PACKAGES)} 个包")

    # 排除不需要的包
    for pkg in EXCLUDE_PACKAGES:
        pyi_args += ["--exclude-module", pkg]
    print(f"  排除包: {len(EXCLUDE_PACKAGES)} 个包")

    # 复制包元数据（importlib.metadata.version 需要）
    for pkg in COPY_METADATA:
        pyi_args += ["--copy-metadata", pkg]
    print(f"  复制元数据: {len(COPY_METADATA)} 个包")

    # 添加入口文件
    pyi_args.append(str(ROOT / "main.py"))

    print(f"  窗口模式: {'控制台' if console else '后台（无控制台）'}")

    try:
        run(pyi_args)
    except subprocess.CalledProcessError as e:
        print(f"\n* 打包失败: {e}")
        print("\n诊断建议:")
        print("1. 检查 main.py 是否存在且语法正确")
        print("2. 尝试添加 --console 查看错误输出")
        print("3. 确保所有依赖都已安装: uv sync")
        print("4. 尝试单独导入问题模块: python -c 'import faster_whisper'")
        sys.exit(1)

    clean_artifacts()

    out_dir = DIST_DIR / "video-capture-server"
    exe = out_dir / "video-capture-server.exe"
    if not exe.exists():
        print(f"\n  错误: 未找到 {exe}")
        sys.exit(1)

    # 计算输出大小
    total_size = sum(
        f.stat().st_size for f in out_dir.rglob("*") if f.is_file()
    )
    size_mb = total_size / (1024 * 1024)

    print(f"\n  * 打包完成 -> {exe}")
    print(f"  * 输出目录大小: {size_mb:.2f} MB")

    if not console:
        print(f"\n  注意: --windowed 模式下无控制台窗口，日志请查看 %APPDATA%/Video Capture/logs/")

    create_start_script(out_dir)


def create_start_script(out_dir: Path):
    """创建启动脚本方便运行"""
    bat_content = f"""@echo off
chcp 65001 >nul
title Video Capture Server
echo ========================================
echo   Video Capture Server
echo ========================================
echo.
echo Starting server at http://localhost:8090
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0"
video-capture-server.exe

pause
"""
    bat_file = out_dir / "start_server.bat"
    bat_file.write_text(bat_content, encoding="utf-8")
    print(f"  * 已创建启动脚本: {bat_file}")


def main():
    parser = argparse.ArgumentParser(description="后端打包脚本")
    parser.add_argument("--clean", action="store_true", help="打包前清理 build/dist 目录")
    parser.add_argument("--console", action="store_true", help="保留控制台窗口（调试用）")
    parser.add_argument("--upx", action="store_true", help="启用 UPX 压缩（⚠ 增加杀软误报风险）")
    args = parser.parse_args()

    os.chdir(ROOT)

    if args.clean:
        print("* 清理构建目录...")
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "dist", ignore_errors=True)
        for spec in ROOT.glob("*.spec"):
            spec.unlink()
        print("  清理完成")

    build(use_upx=args.upx, console=args.console)


if __name__ == "__main__":
    main()
