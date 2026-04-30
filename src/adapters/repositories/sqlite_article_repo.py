"""SQLite article repository — implements IArticleRepository.
Depends on: sqlite3 (stdlib), domain entities."""
import sqlite3
from datetime import datetime
from typing import List, Set, Optional
import os

try:
    from src.domain.entities import Article
    from src.domain.exceptions import StorageError, DuplicateArticleError
except ImportError:
    from domain.entities import Article
    from domain.exceptions import StorageError, DuplicateArticleError


class SqliteArticleRepository:
    """SQLite-backed article repository with in-memory URL dedup cache and connection pooling.
    Uses parameterized queries to prevent SQL injection."""

    def __init__(self, db_path: str, normalize_date_fn=None, pool_size: int = 5):
        self._db_path = db_path
        self._normalize_date = normalize_date_fn  # injected from adapter layer
        self._url_cache: Set[str] = set()
        self._cache_initialized = False
        self._pool_size = pool_size
        self._connection_pool: List[Optional[sqlite3.Connection]] = [None] * pool_size
        self._pool_lock = None  # Will use threading.Lock if needed

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection from the pool or create a new one."""
        # For simplicity, create new connections for now
        # TODO: Implement proper connection pooling with thread safety
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        # Set journal mode to WAL for better concurrency
        conn.execute("PRAGMA journal_mode = WAL")
        # Set synchronous mode to NORMAL for performance
        conn.execute("PRAGMA synchronous = NORMAL")
        # Set cache size for better performance
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        return conn

    def _ensure_cache(self):
        if not self._cache_initialized:
            conn = self._get_connection()
            c = conn.cursor()
            c.execute("SELECT url FROM articles")
            self._url_cache = {row[0] for row in c.fetchall()}
            conn.close()
            self._cache_initialized = True
            print(f"[CACHE] Loaded {len(self._url_cache)} URLs into memory cache")

    def init_db(self) -> None:
        conn = self._get_connection()
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
        # Migrations
        try:
            c.execute("SELECT first_seen_at FROM articles LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE articles ADD COLUMN first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        try:
            c.execute("SELECT effective_time FROM articles LIMIT 1")
        except sqlite3.OperationalError:
            c.execute("ALTER TABLE articles ADD COLUMN effective_time TIMESTAMP")
        c.execute("UPDATE articles SET first_seen_at = crawled_at WHERE first_seen_at IS NULL")
        c.execute("UPDATE articles SET effective_time = COALESCE(published_at, first_seen_at, crawled_at) WHERE effective_time IS NULL")
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
        c.execute("UPDATE articles SET effective_time = COALESCE(first_seen_at, crawled_at) WHERE effective_time IS NULL")
        conn.commit()
        conn.close()
        print("[MIGRATION] DB schema verified/migrated")

    def insert_article(self, article: Article) -> bool:
        url = article.url
        if not url:
            return False
        self._ensure_cache()
        if url in self._url_cache:
            return False
        conn = self._get_connection()
        c = conn.cursor()
        pub_at = self._normalize_date(article.published_at) if article.published_at and self._normalize_date else ""
        effective_time = pub_at if pub_at else "CURRENT_TIMESTAMP"
        try:
            if effective_time == "CURRENT_TIMESTAMP":
                c.execute('''
                    INSERT OR REPLACE INTO articles
                    (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT first_seen_at FROM articles WHERE url = ?),
                        CURRENT_TIMESTAMP
                    ), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (url, article.title, article.description, article.image_url, article.content, article.source, pub_at, url))
            else:
                c.execute('''
                    INSERT OR REPLACE INTO articles
                    (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT first_seen_at FROM articles WHERE url = ?),
                        CURRENT_TIMESTAMP
                    ), CURRENT_TIMESTAMP, ?)
                ''', (url, article.title, article.description, article.image_url, article.content, article.source, pub_at, url, effective_time))
            conn.commit()
            self._url_cache.add(url)
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
        return True

    def insert_articles_batch(self, articles: List[Article]) -> int:
        self._ensure_cache()
        new_articles = []
        for a in articles:
            if a.url and a.url not in self._url_cache:
                new_articles.append(a)
                self._url_cache.add(a.url)
        if not new_articles:
            return 0
        conn = self._get_connection()
        c = conn.cursor()
        inserted = 0
        try:
            for article in new_articles:
                try:
                    pub_at = self._normalize_date(article.published_at) if article.published_at and self._normalize_date else ""
                    effective_time = pub_at if pub_at else "CURRENT_TIMESTAMP"
                    if effective_time == "CURRENT_TIMESTAMP":
                        c.execute('''
                            INSERT OR REPLACE INTO articles
                            (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                                (SELECT first_seen_at FROM articles WHERE url = ?),
                                CURRENT_TIMESTAMP
                            ), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ''', (article.url, article.title, article.description, article.image_url, article.content, article.source, pub_at, article.url))
                    else:
                        c.execute('''
                            INSERT OR REPLACE INTO articles
                            (url, title, description, image_url, content, source, published_at, first_seen_at, crawled_at, effective_time)
                            VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                                (SELECT first_seen_at FROM articles WHERE url = ?),
                                CURRENT_TIMESTAMP
                            ), CURRENT_TIMESTAMP, ?)
                        ''', (article.url, article.title, article.description, article.image_url, article.content, article.source, pub_at, article.url, effective_time))
                    inserted += 1
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        finally:
            conn.close()
        return inserted

    def get_recent(self, limit: int = 200, offset: int = 0) -> List[Article]:
        """Get recent articles with pagination support."""
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("""
            SELECT url, title, description, image_url, source, published_at, first_seen_at, crawled_at
            FROM articles
            ORDER BY COALESCE(effective_time, first_seen_at, crawled_at) DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = c.fetchall()
        conn.close()
        return [
            Article(
                url=row[0], title=row[1] or "", description=row[2] or "",
                image_url=row[3] or "", source=row[4] or "",
                published_at=row[5] or "", first_seen_at=row[6] or "",
                crawled_at=row[7] or "",
            )
            for row in rows
        ]

    def delete_article(self, url: str) -> bool:
        conn = self._get_connection()
        c = conn.cursor()
        c.execute("DELETE FROM articles WHERE url = ?", (url,))
        deleted = c.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
