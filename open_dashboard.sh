#!/usr/bin/env bash
# Only open dashboard in browser (no crawl)
cd "$(dirname "$0")"
source venv/bin/activate
python src/main.py --open-dashboard
