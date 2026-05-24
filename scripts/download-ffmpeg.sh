#!/bin/bash
# 下载各平台的 ffmpeg 静态二进制到 bin/ 目录
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BIN_DIR="$SCRIPT_DIR/../bin"
mkdir -p "$BIN_DIR"
BIN_DIR="$(cd "$BIN_DIR" && pwd)"

OS="$(uname -s)"
CURL="curl -fsSL --retry 3 --retry-delay 5 --connect-timeout 30"

if [ "$OS" = "Linux" ]; then
  echo "==> 下载 ffmpeg Linux 静态构建 (BtbN)..."
  $CURL -o /tmp/ffmpeg.tar.xz \
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
  tar xf /tmp/ffmpeg.tar.xz -C /tmp
  cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg \
     /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe \
     "$BIN_DIR/"
  chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"

elif [ "$OS" = "Darwin" ]; then
  echo "==> 下载 ffmpeg macOS 静态构建 (evermeet.cx)..."
  $CURL -o /tmp/ffmpeg.zip \
    "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip" || {
    echo "!! evermeet.cx 下载失败，改用 Homebrew..."
    brew install ffmpeg
    cp "$(brew --prefix ffmpeg)/bin/ffmpeg" "$BIN_DIR/"
    cp "$(brew --prefix ffmpeg)/bin/ffprobe" "$BIN_DIR/"
  }
  if [ -f /tmp/ffmpeg.zip ]; then
    unzip -o /tmp/ffmpeg.zip -d "$BIN_DIR/"
    $CURL -o /tmp/ffprobe.zip \
      "https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip"
    unzip -o /tmp/ffprobe.zip -d "$BIN_DIR/"
  fi
  chmod +x "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe"
  xattr -d com.apple.quarantine "$BIN_DIR/ffmpeg" "$BIN_DIR/ffprobe" 2>/dev/null || true

else
  # Windows (Git Bash)
  echo "==> 下载 ffmpeg Windows 静态构建 (gyan.dev)..."
  $CURL -o /tmp/ffmpeg.zip \
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" || {
    echo "!! gyan.dev 下载失败，改用 BtbN..."
    $CURL -o /tmp/ffmpeg.zip \
      "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
  }
  unzip -o /tmp/ffmpeg.zip -d /tmp/ffmpeg_extracted
  # gyan.dev 结构: ffmpeg-*/bin/*
  # BtbN 结构:    ffmpeg-master-*/bin/*
  cp /tmp/ffmpeg_extracted/ffmpeg-*/bin/* "$BIN_DIR/" 2>/dev/null || true
  cp /tmp/ffmpeg_extracted/ffmpeg-master-*/bin/* "$BIN_DIR/" 2>/dev/null || true
fi

echo "==> 完成！bin/ 目录内容:"
ls -la "$BIN_DIR/"
