#!/bin/bash
# News Crawler - Run crawl once and generate dashboard
# Used by cron job to run every 15 minutes

cd "$(dirname "$0")"
source venv/bin/activate
python src/main.py --run-once >> /tmp/crawler_cron.log 2>&1
