#!/usr/bin/env python3
"""Backfill published_at for existing articles from their detail pages."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from crawler import _fetch_article_detail
from storage import DB_PATH

def backfill_published_at(batch_size: int = 100, max_workers: int = 16):
    """Fetch published_at for articles missing it."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get articles without published_at
    c.execute("""
        SELECT url, title FROM articles 
        WHERE published_at IS NULL OR published_at = ''
        ORDER BY first_seen_at DESC
        LIMIT ?
    """, (batch_size,))
    
    articles = [(row[0], row[1]) for row in c.fetchall()]
    conn.close()
    
    if not articles:
        print("[BACKFILL] No articles missing published_at")
        return 0
    
    print(f"[BACKFILL] Fetching published_at for {len(articles)} articles...")
    filled = 0
    
    def _fetch(item):
        nonlocal filled
        url, title = item
        try:
            detail = _fetch_article_detail(url)
            if detail.get("published_at"):
                # Update DB
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    "UPDATE articles SET published_at = ? WHERE url = ?",
                    (detail["published_at"], url)
                )
                conn.commit()
                conn.close()
                filled += 1
                print(f"  [OK] {title[:50]}... -> {detail['published_at'][:19]}")
            else:
                print(f"  [SKIP] {title[:50]}... (no date found)")
        except Exception as e:
            print(f"  [ERR] {title[:50]}... -> {e}")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(_fetch, articles))
    
    print(f"[BACKFILL] Updated {filled}/{len(articles)} articles with published_at")
    return filled

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill published_at for existing articles")
    parser.add_argument("--batch", type=int, default=100, help="Number of articles to process")
    parser.add_argument("--workers", type=int, default=16, help="Number of parallel workers")
    args = parser.parse_args()
    
    backfill_published_at(args.batch, args.workers)
