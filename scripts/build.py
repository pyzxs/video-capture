"""后端 PyInstaller 打包脚本。

用法:
    python scripts/build.py              # 默认打包（UPX + ZIP 压缩）
    python scripts/build.py --clean      # 清理后打包
    python scripts/build.py --no-compress  # 跳过压缩
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
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
    # 其他
    "cryptography",
    "lxml",
    "aiohttp",
    "aiofiles",
]

# 需要收集整个包的模块（含二进制 .dll/.so）
COLLECT_PACKAGES = [
    "ctranslate2",
    "faster_whisper",
    "huggingface_hub",
    "chromadb",
    "imageio",
    "imageio_ffmpeg",
    "onnxruntime",
    "opentelemetry",
    "opentelemetry.sdk",
    "opentelemetry.api",
    "opentelemetry.exporter.otlp.proto.grpc",
    "opentelemetry.semconv",
    "overrides",
    "typing_extensions",
    "pydantic",
    "pydantic_settings",
]

# 排除的大型/无用包
EXCLUDE_PACKAGES = [
    "tkinter",
    "test",
    "tests",
    "unittest",
    "setuptools",
    "pip",
    "wheel",
    "pytest",
    "mypy",
    "black",
    "isort",
    "flake8",
    "numpy.tests",
    "scipy",
    "torch",
    "tensorflow",
    "tensorboard",
    "matplotlib",
    "pandas.tests",
    "jupyter",
    "IPython",
    "notebook",
]

# 需要复制包元数据的模块（importlib.metadata.version 用）
COPY_METADATA = [
    "imageio",
    "moviepy",
    "numpy",
    "pillow",
]

# 移除 ADD_DATA（不再需要 certifi）


def run(cmd, **kwargs):
    print(f"  → {' '.join(cmd)}")
    return subprocess.check_call(cmd, **kwargs)


def find_upx() -> str | None:
    """查找 UPX 可执行文件路径。"""
    # 优先找项目 bin/ 下的
    for name in ["upx.exe", "upx"]:
        local = ROOT / "bin" / name
        if local.exists():
            return str(local)
    # 再找 PATH 里的
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


def build(compress: bool = True):
    print("=" * 56)
    print("  后端打包: PyInstaller (one-dir)")
    print("=" * 56)

    shutil.rmtree(DIST_DIR, ignore_errors=True)
    clean_artifacts()

    pyi_args = [
        PYTHON, "-m", "PyInstaller",
        "--distpath", str(DIST_DIR),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT),
        "--name", "video-capture-server",
        "--onedir",
        "--console",  # 保留控制台以便调试
        "--clean",
        "--noconfirm",
    ]

    # UPX 压缩（压缩 .exe / .dll / .pyd 约 30-50%）
    if compress:
        upx_path = find_upx()
        if upx_path:
            pyi_args += ["--upx-dir", str(Path(upx_path).parent)]
            print(f"  UPX: {upx_path}")
        else:
            print("  提示: 未找到 UPX，跳过二进制压缩（放到 bin/upx.exe 即可自动启用）")

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

    # 移除 ADD_DATA 部分（注释掉）
    # for src_path, dst_name in ADD_DATA:
    #     pyi_args += ["--add-data", f"{src_path}{os.pathsep}{dst_name}"]

    # 添加入口文件
    pyi_args.append(str(ROOT / "main.py"))

    try:
        run(pyi_args)
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败: {e}")
        print("\n诊断建议:")
        print("1. 检查 main.py 是否存在且语法正确")
        print("2. 尝试移除 --console 参数，添加 --debug 查看详细错误")
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
    total_size = 0
    for file in out_dir.rglob("*"):
        if file.is_file():
            total_size += file.stat().st_size
    size_mb = total_size / (1024 * 1024)
    size_gb = size_mb / 1024

    print(f"\n✅ 打包完成 → {exe}")
    print(f"📦 输出目录大小: {size_mb:.2f} MB ({size_gb:.2f} GB)")
    print(f"\n运行方式:")
    print(f"  cd {out_dir}")
    print(f"  video-capture-server.exe")
    print(f"  或双击 start_server.bat (如果已创建)")

    # 可选：创建启动脚本
    create_start_script(out_dir)


def create_start_script(out_dir: Path):
    """创建启动脚本方便运行"""
    bat_content = f'''@echo off
chcp 65001 >nul
title Video Capture Server
echo ========================================
echo   Video Capture Server
echo ========================================
echo.
echo Starting server at http://localhost:8000
echo Press Ctrl+C to stop
echo.

cd /d "%~dp0"
video-capture-server.exe

pause
'''
    bat_file = out_dir / "start_server.bat"
    bat_file.write_text(bat_content, encoding='utf-8')
    print(f"📝 已创建启动脚本: {bat_file}")


def main():
    parser = argparse.ArgumentParser(description="后端打包脚本")
    parser.add_argument("--clean", action="store_true", help="打包前清理 build/dist 目录")
    parser.add_argument("--no-compress", action="store_true", help="跳过 UPX 压缩")
    parser.add_argument("--console", action="store_true", help="保留控制台窗口（调试用）")
    args = parser.parse_args()

    os.chdir(ROOT)

    if args.clean:
        print("🧹 清理构建目录...")
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "dist", ignore_errors=True)
        for spec in ROOT.glob("*.spec"):
            spec.unlink()
        print("  清理完成")

    build(compress=not args.no_compress)


if __name__ == "__main__":
    main()