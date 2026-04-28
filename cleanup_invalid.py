#!/usr/bin/env python3
"""Clean up invalid articles (server errors) from database."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from crawler import validate_url
from storage import get_recent, delete_article

def cleanup_invalid_articles(batch_size: int = 100):
    """Check and remove articles with server errors from database."""
    print(f"[CLEANUP] Checking for invalid articles in database...")
    
    # Get all articles (we'll check in batches)
    articles = get_recent(1000)  # Get up to 1000 most recent
    
    removed = 0
    checked = 0
    
    for row in articles:
        url = row[0]  # url is first column
        checked += 1
        
        if not validate_url(url):
            if delete_article(url):
                removed += 1
                print(f"[CLEANUP] Removed: {url[:60]}...")
    
    print(f"[CLEANUP] Checked {checked} articles, removed {removed} invalid ones")
    return removed

if __name__ == "__main__":
    cleanup_invalid_articles()
