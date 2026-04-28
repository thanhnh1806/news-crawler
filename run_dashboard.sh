#!/usr/bin/env bash
# Crawl + regenerate dashboard + open browser
set -e

cd "$(dirname "$0")"
source venv/bin/activate
python src/main.py --run-once
