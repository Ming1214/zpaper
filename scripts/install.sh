#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/paper"
LIB_DIR="$HOME/.scholarmind"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Installing zpaper..."

# 1. Install Python package
echo "[1/3] Installing Python package..."
pip install -e "$REPO_ROOT" --quiet

# 2. Create library directory
echo "[2/3] Creating library directory..."
mkdir -p "$LIB_DIR/pdfs"

# 3. Install Claude Code skill
echo "[3/3] Installing Claude Code skill..."
mkdir -p "$SKILL_DIR"
cp "$REPO_ROOT/skill/skill.md" "$SKILL_DIR/skill.md"

echo ""
echo "Done."
echo "  Package : zpaper (editable install)"
echo "  Library : $LIB_DIR"
echo "  Skill   : $SKILL_DIR"
echo ""
echo "Open a Claude Code session and try:"
echo "  /paper add 1706.03762"
