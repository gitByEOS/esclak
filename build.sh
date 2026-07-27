#!/usr/bin/env bash
# 构建 clak 单文件二进制到上级目录（tools/clak）
# 用法：在 clak_src 根目录执行 ./build.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

OUT_DIR="$SCRIPT_DIR/.."
OUT_BIN="$OUT_DIR/clak"

BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

echo "→ 准备隔离构建环境: $BUILD_DIR"
python3 -m venv "$BUILD_DIR/venv"
# shellcheck disable=SC1091
source "$BUILD_DIR/venv/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet pyinstaller
pip install --quiet -e .

echo "→ 打包单文件二进制"
pyinstaller \
    --onefile \
    --name clak \
    --distpath "$OUT_DIR" \
    --workpath "$BUILD_DIR/work" \
    --specpath "$BUILD_DIR" \
    --collect-all textual \
    --collect-submodules clak.commands \
    --clean \
    --noconfirm \
    src/clak/__main__.py

deactivate

# 清理 pyinstaller 残留的 spec/构建目录（distpath 已指定，但保险起见）
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/clak.spec"

echo "✓ 构建完成: $OUT_BIN"
"$OUT_BIN" --help 2>&1 | head -5 || true
