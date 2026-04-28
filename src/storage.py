import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Set

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "news.db")

# Global URL cache for O(1) deduplication lookups
_url_cache: Set[str] = set()
_cache_initialized = False


def _ensure_cache():
    """Initialize URL cache from DB if not already loaded."""
    global _cache_initialized, _url_cache
    if not _cache_initialized:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT url FROM articles")
        _url_cache = {row[0] for row in c.fetchall()}
        conn.close()
        _cache_initialized = True
        print(f"[CACHE] Loaded {len(_url_cache)} URLs into memory cache")


def get_url_cache() -> Set[str]:
    """Get the URL cache set for fast lookups."""
    _ensure_cache()
    return _url_cache


def add_to_cache(url: str):
    """Add a URL to the cache after successful insert."""
    global _url_cache
    _url_cache.add(url)


def clear_cache():
    """Clear the URL cache (useful for testing)."""
    global _cache_initialized, _url_cache
    _url_cache.clear()
    _cache_initialized = False


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT,
            description TEXT,
            image_url TEXT,
            content TEXT,
            source TEXT,
            published_at TEXT,
            first_seen_at TEXT,
            crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            effective_time TIMESTAMP
        )
    """)
    # Migration: add first_seen_at if not exists (for existing DBs)
    c.execute("PRAGMA table_info(articles)")
    columns = [row[1] for row in c.fetchall()]
    try:
        c.execute("SELECT first_seen_at FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE articles ADD COLUMN first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    try:
        c.execute("SELECT effective_time FROM articles LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE articles ADD COLUMN effective_time TIMESTAMP")
    # Populate first_seen_at from crawled_at for existing rows
    c.execute("UPDATE articles SET first_seen_at = crawled_at WHERE first_seen_at IS NULL")
    print("[MIGRATION] Added first_seen_at column, populated from crawled_at")
    # Populate effective_time for existing rows
    c.execute("UPDATE articles SET effective_time = COALESCE(published_at, first_seen_at, crawled_at) WHERE effective_time IS NULL")
    print("[MIGRATION] Populated effective_time column")
    # Normalize non-ISO published_at / effective_time values for correct sorting
    c.execute("""
        UPDATE articles SET 
            published_at = COALESCE(
                CASE WHEN published_at GLOB '[0-9][0-9][0-9][0-9]-*' THEN published_at ELSE NULL END,
                published_at
            ),
            effective_time = COALESCE(
                CASE WHEN effective_time GLOB '[0-9][0-9][0-9][0-9]-*' THEN effective_time ELSE NULL END,
                effective_time
            )
        WHERE (published_at IS NOT NULL AND published_at != '' AND published_at NOT GLOB '[0-9][0-9][0-9][0-9]-*')
           OR (effective_time IS NOT NULL AND effective_time != '' AND effective_time NOT GLOB '[0-9][0-9][0-9][0-9]-*')
    """)
    # For rows where we just nulled effective_time, recalculate from first_seen_at
    c.execute("UPDATE articles SET effective_time = COALESCE(first_seen_at, crawled_at) WHERE effective_time IS NULL")
    print("[MIGRATION] Normalized date formats for sorting")
    conn.commit()
    conn.close()


def insert_article(article: dict) -> bool:
    """Insert article. Return True if new, False if duplicate.
    Uses in-memory cache for O(1) deduplication check."""
    url = article.get("url")
    if not url:
        return False
    
    # Fast O(1) cache check
    _ensure_cache()
    if url in _url_cache:
        return False
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    # Normalize published_at to ISO format for consistent sorting
    from src.crawler import _normalize_date
    pub_at = _normalize_date(article.get("published_at", "")) if article.get("published_at") else ""
    try:
        effective_time = pub_at if pub_at else "CURRENT_TIMESTAMP"
    except KeyError:
        effective_time = "CURRENT_TIMESTAMP"
    if effective_time == "CURRENT_TIMESTAMP":
        c.execute('''
            INSERT OR REPLACE INTO articles
            (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                (SELECT first_seen_at FROM articles WHERE url = ?),
                CURRENT_TIMESTAMP
            ), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (url, article.get("title"), article.get("description"), article.get("image_url"), article.get("content"), article.get("source"), pub_at, url))
    else:
        c.execute('''
            INSERT OR REPLACE INTO articles
            (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                (SELECT first_seen_at FROM articles WHERE url = ?),
                CURRENT_TIMESTAMP
            ), CURRENT_TIMESTAMP, ?)
        ''', (url, article.get("title"), article.get("description"), article.get("image_url"), article.get("content"), article.get("source"), pub_at, url, effective_time))
    conn.commit()
    _url_cache.add(url)  # Add to cache on success
    conn.close()
    return True


def insert_articles_batch(articles: List[Dict]) -> int:
    """Batch insert articles. Returns count of new articles inserted.
    Much faster than individual inserts for large batches.
    Sets first_seen_at = now for new articles, preserving it for existing ones."""
    _ensure_cache()
    
    # Filter out duplicates using cache
    new_articles = []
    for article in articles:
        url = article.get("url")
        if url and url not in _url_cache:
            new_articles.append(article)
            _url_cache.add(url)  # Pre-add to prevent duplicates in same batch
    
    if not new_articles:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    from src.crawler import _normalize_date
    inserted = 0
    
    try:
        for article in new_articles:
            try:
                pub_at = _normalize_date(article.get("published_at", "")) if article.get("published_at") else ""
                effective_time = pub_at if pub_at else "CURRENT_TIMESTAMP"
                if effective_time == "CURRENT_TIMESTAMP":
                    c.execute('''
                        INSERT OR REPLACE INTO articles
                        (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                            (SELECT first_seen_at FROM articles WHERE url = ?),
                            CURRENT_TIMESTAMP
                        ), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (article.get("url"), article.get("title"), article.get("description"), article.get("image_url"), article.get("content"), article.get("source"), pub_at, article.get("url")))
                else:
                    c.execute('''
                        INSERT OR REPLACE INTO articles
                        (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                            (SELECT first_seen_at FROM articles WHERE url = ?),
                            CURRENT_TIMESTAMP
                        ), CURRENT_TIMESTAMP, ?)
                    ''', (article.get("url"), article.get("title"), article.get("description"), article.get("image_url"), article.get("content"), article.get("source"), pub_at, article.get("url"), effective_time))
                inserted += 1
            except sqlite3.IntegrityError:
                pass  # Already exists
        conn.commit()
    finally:
        conn.close()
    
    return inserted


def delete_article(url: str) -> bool:
    """Delete article by URL. Returns True if deleted."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM articles WHERE url = ?", (url,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_recent(limit: int = 20):
    """Get recent articles sorted by published_at (priority) then first_seen_at.
    This ensures articles appear by their actual publish date, not crawl time."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Sort: published_at DESC (actual article date) → first_seen_at DESC (when first discovered)
    c.execute("""
        SELECT url, title, description, image_url, source, published_at, first_seen_at, crawled_at
        FROM articles
        ORDER BY COALESCE(effective_time, first_seen_at, crawled_at) DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    return rows
