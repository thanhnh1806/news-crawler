#!/usr/bin/env python3
"""Backfill: Normalize all date fields to ISO 8601 format for correct SQLite sorting."""

import sqlite3
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "news.db"

def normalize_date(date_str: str) -> str:
    """Normalize date string to ISO 8601 format."""
    if not date_str or not date_str.strip():
        return ""
    s = date_str.strip()
    # Already ISO-like (starts with YYYY)
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return s[:25]
    # US format: M/D/YYYY h:mm:ss AM/PM
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?', s, re.IGNORECASE)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour, minute = int(m.group(4)), int(m.group(5))
        sec = int(m.group(6)) if m.group(6) else 0
        ampm = (m.group(7) or '').upper()
        if ampm == 'PM' and hour < 12:
            hour += 12
        elif ampm == 'AM' and hour == 12:
            hour = 0
        try:
            dt = datetime(year, month, day, hour, minute, sec, tzinfo=timezone(timedelta(hours=7)))
            return dt.isoformat()
        except ValueError:
            return s
    # Vietnamese format: DD/MM/YYYY HH:mm
    m = re.match(r'(\d{2})/(\d{2})/(\d{4})\s+(\d{1,2}):(\d{2})', s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour, minute = int(m.group(4)), int(m.group(5))
        try:
            dt = datetime(year, month, day, hour, minute, tzinfo=timezone(timedelta(hours=7)))
            return dt.isoformat()
        except ValueError:
            return s
    return s

def backfill():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Get all articles with non-ISO published_at or effective_time
    c.execute("SELECT rowid, published_at, effective_time, first_seen_at, crawled_at FROM articles")
    rows = c.fetchall()
    
    updated = 0
    for row in rows:
        rowid, pub, eff, first, crawled = row
        new_pub = normalize_date(pub) if pub else ""
        new_eff = normalize_date(eff) if eff else ""
        
        # If effective_time is still non-ISO or empty, recalculate
        if not new_eff or not re.match(r'^\d{4}-', new_eff):
            if new_pub and re.match(r'^\d{4}-', new_pub):
                new_eff = new_pub
            elif first and re.match(r'^\d{4}-', first):
                new_eff = first
            elif crawled and re.match(r'^\d{4}-', crawled):
                new_eff = crawled
            else:
                new_eff = ""
        
        if new_pub != (pub or "") or new_eff != (eff or ""):
            c.execute("UPDATE articles SET published_at = ?, effective_time = ? WHERE rowid = ?",
                      (new_pub, new_eff, rowid))
            updated += 1
    
    conn.commit()
    conn.close()
    print(f"[BACKFILL] Normalized {updated} articles to ISO date format.")

if __name__ == "__main__":
    backfill()
