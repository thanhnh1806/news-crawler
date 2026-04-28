#!/bin/bash
# Chạy crawler 1 lần và hiển thị bài viết mới
set -e
cd "$(dirname "$0")"
source venv/bin/activate
python src/main.py --run-once
