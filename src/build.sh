#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 src/build_font.py
python3 src/verify_font.py
