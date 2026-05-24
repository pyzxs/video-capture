#!/bin/bash
# 下载各平台的 ffmpeg 静态二进制到 bin/ 目录
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$SCRIPT_DIR/../bin"
mkdir -p "$BIN_DIR"
BIN_DIR="$(cd "$BIN_DIR" && pwd)"

OS="$(uname -s)"

if [ "$OS" = "Linux" ]; then
  echo "==> 下载 ffmpeg Linux 静态构建..."
  curl -fsSL -o /tmp/ffmpeg.tar.xz \
    "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
  tar xf /tmp/ffmpeg.tar.xz -C /tmp
  cp /tmp/ffmpeg-*-amd64-static/ffmpeg /tmp/ffmpeg-*-amd64-static/ffprobe "$BIN_DIR/"
  chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"

elif [ "$OS" = "Darwin" ]; then
  echo "==> 下载 ffmpeg macOS 静态构建..."
  curl -fsSL -o /tmp/ffmpeg.zip \
    "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip"
  curl -fsSL -o /tmp/ffprobe.zip \
    "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
  unzip -o /tmp/ffmpeg.zip -d "$BIN_DIR/"
  unzip -o /tmp/ffprobe.zip -d "$BIN_DIR/"
  chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"
  xattr -d com.apple.quarantine "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe" 2>/dev/null || true

else
  # Windows (Git Bash / MSYS2)
  echo "==> 下载 ffmpeg Windows 静态构建..."
  curl -fsSL -o /tmp/ffmpeg.zip \
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
  unzip -o /tmp/ffmpeg.zip -d /tmp/ffmpeg_extracted
  cp /tmp/ffmpeg_extracted/ffmpeg-*/bin/* "$BIN_DIR/"
fi

echo "==> 完成！bin/ 目录内容:"
ls -la "$BIN_DIR/"
