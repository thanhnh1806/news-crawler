#!/usr/bin/env bash
# Run the dashboard server - auto-crawl on every page refresh
set -e

cd "$(dirname "$0")"
source venv/bin/activate

echo "============================================================"
echo "  News Dashboard Server - Auto-crawl on refresh"
echo "============================================================"
echo ""
echo "Opening http://localhost:5000 ..."
echo "Every time you refresh the page, it will crawl new articles!"
echo ""
echo "Press Ctrl+C to stop the server"
echo "============================================================"
echo ""

# Open browser after server starts
(sleep 3 && open http://localhost:5000) &

python -m src.infrastructure.flask_server
