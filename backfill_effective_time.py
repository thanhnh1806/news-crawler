#!/usr/bin/env python3
"""Backfill effective_time for existing articles."""

import sqlite3
from pathlib import Path

def backfill():
    db_path = Path(__file__).parent / "news.db"
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    # Check if effective_time column exists
    c.execute("PRAGMA table_info(articles)")
    columns = {row[1] for row in c.fetchall()}
    if "effective_time" not in columns:
        print("effective_time column does not exist. Run storage.init_db() first.")
        return

    # Update rows where effective_time is NULL
    c.execute("""
        UPDATE articles
        SET effective_time = COALESCE(published_at, first_seen_at, crawled_at)
        WHERE effective_time IS NULL
    """)
    updated = c.rowcount
    conn.commit()
    conn.close()
    print(f"[BACKFILL] Updated {updated} articles with effective_time.")

if __name__ == "__main__":
    backfill()
