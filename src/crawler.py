import requests
import re
import feedparser
import time
import threading
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional
import concurrent.futures
from datetime import datetime, timezone, timedelta
import urllib3
import os

# SSL verification setting - can be disabled via environment variable if needed
VERIFY_SSL = os.getenv("VERIFY_SSL", "true").lower() == "true"

if not VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

# HTTP caching configuration
ENABLE_HTTP_CACHE = os.getenv("ENABLE_HTTP_CACHE", "true").lower() == "true"
CACHE_BACKEND = os.getenv("CACHE_BACKEND", "sqlite")
CACHE_NAME = os.getenv("CACHE_NAME", "news_crawler_cache")

# Try to import requests-cache if available
try:
    import requests_cache
    if ENABLE_HTTP_CACHE:
        requests_cache.install_cache(
            cache_name=CACHE_NAME,
            backend=CACHE_BACKEND,
            expire_after=int(os.getenv("CACHE_EXPIRE_AFTER", "300"))  # 5 minutes default
        )
except ImportError:
    ENABLE_HTTP_CACHE = False


class DomainRateLimiter:
    """Thread-safe per-domain rate limiter.
    Ensures minimum delay between consecutive requests to the same domain."""

    def __init__(self, min_interval: float = 1.0):
        self.min_interval = min_interval
        self._last_request: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, url: str):
        """Block until min_interval has passed since last request to this domain."""
        domain = urlparse(url).netloc
        with self._lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0)
            wait_time = self.min_interval - (now - last)
        if wait_time > 0:
            time.sleep(wait_time)
        with self._lock:
            self._last_request[domain] = time.monotonic()


_rate_limiter = DomainRateLimiter(min_interval=1.0)


def fetch_url(url: str, max_retries: int = 3) -> Optional[str]:
    """Fetch URL with per-domain rate limiting and exponential backoff on 429."""
    _rate_limiter.wait(url)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20, verify=VERIFY_SSL)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
                print(f"[RATE LIMIT] 429 for {url}, retrying in {retry_after}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_after)
                continue
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429:
                continue
            print(f"[ERROR] Fetch failed: {url} -> {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Fetch failed: {url} -> {e}")
            return None
    print(f"[ERROR] Fetch failed after {max_retries} retries: {url}")
    return None


def validate_url(url: str) -> bool:
    """Check if URL returns a valid response (not 5xx Server Error). Returns True if valid."""
    _rate_limiter.wait(url)
    try:
        resp = requests.head(url, headers=HEADERS, timeout=5, allow_redirects=True, verify=VERIFY_SSL)
        # Status 5xx = Server Error (invalid)
        # Status 4xx = Client Error (might be temporary, still valid)
        # Status 3xx/2xx = OK
        if resp.status_code >= 500:
            print(f"[VALIDATE] Server Error {resp.status_code} for: {url}")
            return False
        return True
    except requests.exceptions.RequestException:
        # If we can't reach it, consider it invalid (skip verbose logging for speed)
        return False


def _extract_img_src(img) -> str:
    """Extract image URL from an <img> tag, checking common lazy-loading attributes."""
    if not img:
        return ""
    return (
        img.get("data-lazy-src")
        or img.get("data-src")
        or img.get("data-original")
        or img.get("src")
        or ""
    )


def _extract_bg_image(elem) -> str:
    """Extract background-image URL from a style attribute."""
    if not elem:
        return ""
    style = elem.get("style", "")
    m = re.search(r'background-image:\s*url\(["\']?([^"\')]+)', style)
    if m:
        return m.group(1)
    return ""


def _find_image_in_item(item, url: str) -> str:
    """Try multiple strategies to find an image URL within a listing item.
    Searches: img tags, background-image CSS, sibling elements, parent elements."""
    if not item:
        return ""
    # Strategy 1: Direct img in item
    img = item.find("img")
    image_url = _extract_img_src(img)
    if image_url:
        if not image_url.startswith("http"):
            image_url = urljoin(url, image_url)
        return image_url
    
    # Strategy 2: Background-image in item itself or children
    for elem in [item] + list(item.find_all()):
        bg = _extract_bg_image(elem)
        if bg:
            if not bg.startswith("http"):
                bg = urljoin(url, bg)
            return bg
    
    # Strategy 3: Look in parent element
    parent = item.find_parent(["div", "li", "article", "section"])
    if parent:
        img = parent.find("img")
        image_url = _extract_img_src(img)
        if image_url:
            if not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            return image_url
        # Check parent's background-image
        bg = _extract_bg_image(parent)
        if bg:
            if not bg.startswith("http"):
                bg = urljoin(url, bg)
            return bg
    
    # Strategy 4: Look in previous sibling (image often placed before text)
    prev = item.find_previous_sibling()
    if prev:
        img = prev.find("img")
        image_url = _extract_img_src(img)
        if image_url:
            if not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            return image_url
        bg = _extract_bg_image(prev)
        if bg:
            if not bg.startswith("http"):
                bg = urljoin(url, bg)
            return bg
    
    # Strategy 5: Look for figure or picture elements near item
    for fig in item.find_all_previous(["figure", "picture"], limit=3):
        img = fig.find("img")
        image_url = _extract_img_src(img)
        if image_url:
            if not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            return image_url
    
    return ""


def _normalize_date(date_str: str) -> str:
    """Normalize date string to ISO 8601 format for consistent SQLite sorting.
    Handles: ISO, US (M/D/YYYY h:mm AM/PM), Vietnamese formats."""
    if not date_str or not date_str.strip():
        return ""
    s = date_str.strip()
    # Already ISO-like (starts with YYYY)
    if re.match(r'^\d{4}-\d{2}-\d{2}', s):
        return s[:25]  # Trim to reasonable length
    # US format: M/D/YYYY h:mm:ss AM/PM or M/D/YYYY H:mm:ss
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


def _make_article(url: str, title: str, image_url: str, description: str, source: str) -> Dict:
    return {
        "url": url,
        "title": title,
        "description": description,
        "image_url": image_url,
        "content": description,
        "source": source,
        "published_at": "",
    }


def _deduplicate_by_url(articles: List[Dict]) -> List[Dict]:
    seen = set()
    result = []
    for art in articles:
        if art["url"] and art["url"] not in seen:
            seen.add(art["url"])
            result.append(art)
    return result


def _fetch_article_detail(article_url: str) -> dict:
    """Fetch article detail page and extract image and published date.
    Returns {"image": "...", "published_at": "..."} with empty strings if not found."""
    html = fetch_url(article_url)
    if not html:
        return {"image": "", "published_at": ""}
    soup = BeautifulSoup(html, "lxml")
    
    result = {"image": "", "published_at": ""}
    
    # --- Extract published_at ---
    # 1. Meta article:published_time
    pub = soup.find("meta", property="article:published_time")
    if pub and pub.get("content"):
        result["published_at"] = _normalize_date(pub["content"])
    
    # 2. Meta datePublished (JSON-LD often has this too)
    if not result["published_at"]:
        pub = soup.find("meta", attrs={"name": "datePublished"})
        if pub and pub.get("content"):
            result["published_at"] = _normalize_date(pub["content"])
    
    # 3. JSON-LD datePublished
    if not result["published_at"]:
        for script in soup.find_all("script", type="application/ld+json"):
            import json
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    dp = data.get("datePublished") or data.get("dateCreated")
                    if dp:
                        result["published_at"] = _normalize_date(dp)
                        break
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            dp = item.get("datePublished") or item.get("dateCreated")
                            if dp:
                                result["published_at"] = _normalize_date(dp)
                                break
            except Exception:
                pass
    
    # 4. Time element
    if not result["published_at"]:
        time_tag = soup.find("time", datetime=True)
        if time_tag:
            result["published_at"] = _normalize_date(time_tag["datetime"])
    
    # --- Extract image ---
    # 1. Open Graph image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        result["image"] = og["content"]
    
    # 2. Twitter card image
    if not result["image"]:
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            result["image"] = tw["content"]
    
    # 3. Meta thumbnail
    if not result["image"]:
        thumb = soup.find("meta", attrs={"name": "thumbnail"})
        if thumb and thumb.get("content"):
            result["image"] = thumb["content"]
    
    # 4. JSON-LD image
    if not result["image"]:
        for script in soup.find_all("script", type="application/ld+json"):
            import json
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict):
                    img = data.get("image")
                    if isinstance(img, str) and img:
                        result["image"] = img
                        break
                    if isinstance(img, list) and img:
                        result["image"] = img[0]
                        break
                if isinstance(data, list) and data:
                    for item in data:
                        if isinstance(item, dict) and item.get("image"):
                            img = item["image"]
                            if isinstance(img, str):
                                result["image"] = img
                                break
                            if isinstance(img, list) and img:
                                result["image"] = img[0]
                                break
            except Exception:
                pass
    
    # 5. First large-ish <img> inside article content area
    if not result["image"]:
        content_selectors = ["article", "[class*='content']", "[class*='detail']", "[class*='article']", "[class*='post']", ".main", "#main", "[class*='body']", "[class*='entry']", "[class*='news-detail']"]
        for sel in content_selectors:
            container = soup.select_one(sel)
            if container:
                imgs = container.find_all("img")
                for img in imgs:
                    src = img.get("data-src") or img.get("src") or img.get("data-original") or ""
                    if src:
                        w = img.get("width")
                        h = img.get("height")
                        if w and h:
                            try:
                                if int(w) < 80 or int(h) < 80:
                                    continue
                            except ValueError:
                                pass
                        lower = src.lower()
                        if any(x in lower for x in ["avatar", "icon", "logo", "banner-ad", "ads", "tracking", "pixel", "1x1", ".svg"]):
                            continue
                        result["image"] = urljoin(article_url, src)
                        break
                if result["image"]:
                    break
    
    # 6. Fallback: any reasonable-sized <img>
    if not result["image"]:
        best_img = ""
        best_size = 0
        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src") or img.get("data-original") or ""
            if not src:
                continue
            lower = src.lower()
            if any(x in lower for x in ["avatar", "icon", "logo", "banner-ad", "ads", "tracking", "pixel", "1x1", ".svg", "/icon/", "/logo/"]):
                continue
            size = 0
            w = img.get("width")
            h = img.get("height")
            if w and h:
                try:
                    size = int(w) * int(h)
                except ValueError:
                    size = 10000
            else:
                size = 10000
            if size > best_size:
                best_size = size
                best_img = src
        if best_img:
            result["image"] = urljoin(article_url, best_img)
    
    return result


def _fetch_article_image(article_url: str) -> str:
    """Backward-compatible wrapper that only returns image URL."""
    return _fetch_article_detail(article_url).get("image", "")


def backfill_images(articles: List[Dict], max_workers: int = 8, limit: int = 9999) -> List[Dict]:
    """Fetch missing images and published dates from article detail pages.
    Processes up to 'limit' articles missing images or published_at."""
    # Backfill articles missing image OR missing published_at
    missing = [a for a in articles if not a.get("image_url") or not a.get("published_at")][:limit]
    if not missing:
        return articles

    print(f"[BACKFILL] Fetching details for {len(missing)} articles...")
    filled_img = 0
    filled_pub = 0

    def _fetch(article):
        nonlocal filled_img, filled_pub
        detail = _fetch_article_detail(article["url"])
        if detail.get("image") and not article.get("image_url"):
            article["image_url"] = detail["image"]
            filled_img += 1
        if detail.get("published_at") and not article.get("published_at"):
            article["published_at"] = detail["published_at"]
            filled_pub += 1
        return article

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        list(executor.map(_fetch, missing))

    print(f"[BACKFILL] Found images for {filled_img}/{len(missing)}, published dates for {filled_pub}/{len(missing)}")
    return articles


def parse_bnews(url: str = "https://bnews.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    # Strategy 1: h3 > a links (common on bnews homepage and category pages)
    for h3 in soup.find_all("h3"):
        a = h3.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or "trang-" in href:
            continue
        # Look for image in parent li or nearby
        parent = h3.find_parent()
        img = parent.find("img") if parent else None
        image_url = _extract_img_src(img)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(url, image_url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, image_url, "", "bnews.vn"))
    # Strategy 2: article.news-featured li items
    for art in soup.find_all("article", class_=lambda x: x and "news" in " ".join(x).lower()):
        for li in art.find_all("li"):
            a = li.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            img = li.find("img")
            image_url = _extract_img_src(img)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "bnews.vn"))
    return _deduplicate_by_url(articles)


def parse_thesaigontimes(url: str = "https://thesaigontimes.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    # WordPress typical: h2.entry-title > a, div.td-module-thumb > a
    selectors = [
        "h2.entry-title a",
        "h3.entry-title a",
        "h2.td-module-title a",
        "h3.td-module-title a",
        ".td-module-thumb a",
        ".td-image-wrap a",
        "article h2 a",
        "article h3 a",
    ]
    for sel in selectors:
        for a in soup.select(sel):
            href = a.get("href", "")
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            # Find image in parent module
            parent = a.find_parent(["div", "article", "li"])
            img = parent.find("img") if parent else None
            image_url = _extract_img_src(img)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "thesaigontimes.vn"))
    return _deduplicate_by_url(articles)


def parse_tinnhanhchungkhoan(url: str = "https://www.tinnhanhchungkhoan.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    # Try common selectors - look for article containers
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item", "cate"]):
            # Find all <a> tags in the container, pick the one with longest text as title
            all_links = item.find_all("a", href=True)
            best_a = None
            for a in all_links:
                text = a.get_text(strip=True)
                if text and len(text) > (len(best_a.get_text(strip=True)) if best_a else 0):
                    best_a = a
            if not best_a:
                continue
            href = best_a["href"]
            title = best_a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            # Search entire container for any image
            image_url = _find_image_in_item(item, url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "tinnhanhchungkhoan.vn"))
    # Fallback: h2/h3 > a with article-like hrefs
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript") or ".htm" not in href:
            continue
        # Search parent container for image, not just inside the heading
        image_url = ""
        parent = tag.find_parent(["div", "li", "article", "section"])
        if parent:
            image_url = _find_image_in_item(parent, url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, image_url, "", "tinnhanhchungkhoan.vn"))
    return _deduplicate_by_url(articles)


def parse_vneconomy(url: str = "https://vneconomy.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            # Skip vneconomy category links (e.g., /infographics.htm, /multimedia.htm)
            if href.endswith(".htm") and "-" not in href.split("/")[-1]:
                continue
            # Find image in item, parent, or siblings (try more selectors)
            image_url = ""
            img = item.find("img")
            if img:
                image_url = _extract_img_src(img)
            if not image_url:
                # Try parent's img or parent's parent's img
                parent = item.find_parent()
                while parent and not image_url:
                    img = parent.find("img")
                    if img:
                        image_url = _extract_img_src(img)
                        break
                    parent = parent.find_parent()
            if not image_url:
                # Try previous/next sibling with img
                for sibling in item.find_previous_siblings() + item.find_next_siblings():
                    img = sibling.find("img")
                    if img:
                        image_url = _extract_img_src(img)
                        break
            # Skip SVG icons and small images
            if image_url and (image_url.endswith('.svg') or 'icon' in image_url.lower() or 'logo' in image_url.lower()):
                image_url = ""
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "vneconomy.vn"))
    # Fallback: h2/h3 > a
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        # Try to find image in parent container, not inside the heading itself
        image_url = ""
        parent = tag.find_parent(["div", "li", "article", "section"])
        if parent:
            image_url = _find_image_in_item(parent, url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, image_url, "", "vneconomy.vn"))
    return _deduplicate_by_url(articles)


def parse_vietstock(url: str = "https://vietstock.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    # Try to find article items by class patterns
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item", "cate", "vsn"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            # Skip fili.vn redirects - they are handled by parse_fili
            if "fili.vn" in href.lower():
                continue
            # Skip non-article URLs (category pages, service pages)
            lower_href = href.lower()
            if any(x in lower_href for x in ["/chu-de/", "/dichvu.", "/finance.vietstock", "/doanh-nghiep-a-z", "/ban-can-biet", "/cong-bo-thong-tin"]):
                continue
            # Skip category pages that end with / or .htm without article ID pattern
            if href.endswith("/") and not href.count("/") > 3:
                continue
            if href.endswith(".htm") and not any(c.isdigit() for c in href.split("/")[-1]):
                continue
            # Use improved image extraction that searches in parent, siblings, and CSS
            image_url = _find_image_in_item(item, url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "vietstock.vn"))
    # Fallback: h2/h3 > a with non-javascript hrefs
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        # Skip fili.vn redirects
        if "fili.vn" in href.lower():
            continue
        # Skip non-article URLs
        lower_href = href.lower()
        if any(x in lower_href for x in ["/chu-de/", "/dichvu.", "/finance.vietstock", "/doanh-nghiep-a-z", "/ban-can-biet", "/cong-bo-thong-tin"]):
            continue
        if href.endswith("/") and not href.count("/") > 3:
            continue
        if href.endswith(".htm") and not any(c.isdigit() for c in href.split("/")[-1]):
            continue
        # Try to find image in parent or siblings
        image_url = _find_image_in_item(tag, url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, image_url, "", "vietstock.vn"))
    return _deduplicate_by_url(articles)


def parse_fili(url: str = "https://fili.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            # Use improved image extraction
            image_url = _find_image_in_item(item, url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "fili.vn"))
    # Fallback: h2/h3 > a
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        # Try to find image
        image_url = _find_image_in_item(tag, url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, image_url, "", "fili.vn"))
    return _deduplicate_by_url(articles)


def parse_nhipsongkinhdoanh(url: str = "https://nhipsongkinhdoanh.vn/hashtag/tin-moi-8332") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    items = soup.select("article.news-item, .article-item, .story, .item-news")
    if not items:
        items = soup.find_all("article")
    for item in items[:20]:
        a = item.find("a", href=True)
        if not a:
            continue
        article_url = urljoin(url, a["href"])
        title_tag = item.find("h2") or item.find("h3") or item.find("a")
        title = title_tag.get_text(strip=True) if title_tag else ""
        desc_tag = item.find("p") or item.find(".summary") or item.find(".sapo")
        description = desc_tag.get_text(strip=True) if desc_tag else ""
        img = item.find("img")
        image_url = urljoin(url, img["src"]) if img and img.get("src") else ""
        time_tag = item.find("time")
        published = time_tag.get_text(strip=True) if time_tag else ""
        articles.append(_make_article(article_url, title, image_url, description, "nhipsongkinhdoanh.vn"))
        articles[-1]["published_at"] = published
    return articles


def parse_vietnambiz(url: str = "https://vietnambiz.vn/tin-moi-nhat.htm") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    items = soup.find_all("div", class_="item")
    for item in items[:20]:
        title_a = item.find("h3", class_="title")
        if title_a:
            title_a = title_a.find("a", href=True)
        if not title_a:
            continue
        article_url = urljoin(url, title_a["href"])
        title = title_a.get_text(strip=True)
        img = item.find("img")
        image_url = urljoin(url, img["src"]) if img and img.get("src") else ""
        articles.append(_make_article(article_url, title, image_url, "", "vietnambiz.vn"))
    return articles


def parse_nguoiquansat(url: str = "https://nguoiquansat.vn/tin-moi-nhat") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    items = soup.find_all("div", class_="b-grid")
    for item in items[:20]:
        title_a = item.find("h2", class_="b-grid__title") or item.find("h3", class_="b-grid__title")
        if title_a:
            title_a = title_a.find("a", href=True)
        if not title_a:
            continue
        article_url = title_a["href"]
        title = title_a.get_text(strip=True)
        img_div = item.find("div", class_="b-grid__img")
        img = img_div.find("img") if img_div else None
        image_url = img["src"] if img and img.get("src") else ""
        desc_div = item.find("div", class_="b-grid__desc")
        description = desc_div.get_text(strip=True) if desc_div else ""
        if not description:
            p = item.find("p")
            description = p.get_text(strip=True) if p else ""
        articles.append(_make_article(article_url, title, image_url, description, "nguoiquansat.vn"))
    return articles


def parse_vnexpress(url: str) -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    source = "vnexpress.net"
    # vnexpress uses article.article-item and article.item-news
    for item in soup.find_all("article"):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if "article-item" not in cls_str and "item-news" not in cls_str:
            continue
        a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        img = item.find("img")
        image_url = _extract_img_src(img)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(url, image_url)
        # vnexpress image src often has thumbor/resize prefix, use original if available
        article_url = href if href.startswith("http") else urljoin(url, href)
        # Description from p tag or .description
        desc_tag = item.find("p") or item.find("div", class_="description")
        description = desc_tag.get_text(strip=True) if desc_tag else ""
        articles.append(_make_article(article_url, title, image_url, description, source))
    return _deduplicate_by_url(articles)


def parse_dantri(url: str) -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    source = "dantri.com.vn"
    # dantri uses article.article-item and article.article.grid
    for item in soup.find_all("article"):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if "article-item" not in cls_str and "grid" not in cls_str:
            continue
        # Find the best <a> — the one with the longest text (title)
        best_a = None
        best_len = 0
        for a in item.find_all("a", href=True):
            text = a.get_text(strip=True)
            if len(text) > best_len:
                best_a = a
                best_len = len(text)
        if not best_a or best_len < 10:
            # Try img alt as fallback title
            img = item.find("img")
            if img and img.get("alt") and len(img["alt"].strip()) >= 10:
                href = item.find("a", href=True)
                if href:
                    title = img["alt"].strip()
                    best_a = href
                    best_len = len(title)
            else:
                continue
        href = best_a["href"]
        title = best_a.get_text(strip=True)
        if not title or len(title) < 10:
            img = item.find("img")
            if img and img.get("alt"):
                title = img["alt"].strip()
            if not title or len(title) < 10:
                continue
        img = item.find("img")
        image_url = _extract_img_src(img)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(url, image_url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        desc_tag = item.find("div", class_="article-excerpt") or item.find("p")
        description = desc_tag.get_text(strip=True) if desc_tag else ""
        articles.append(_make_article(article_url, title, image_url, description, source))
    return _deduplicate_by_url(articles)


def parse_theleader(url: str = "https://theleader.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            img = item.find("img")
            image_url = _extract_img_src(img)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "theleader.vn"))
    # Fallback: h2/h3 > a
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, "", "", "theleader.vn"))
    return _deduplicate_by_url(articles)


def parse_mekongasean(url: str = "https://mekongasean.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            img = item.find("img")
            image_url = _extract_img_src(img)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "mekongasean.vn"))
    # Fallback: h2/h3 > a
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, "", "", "mekongasean.vn"))
    return _deduplicate_by_url(articles)


def parse_thoibaonganhang(url: str = "https://thoibaonganhang.vn/") -> List[Dict]:
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript"):
                continue
            img = item.find("img")
            image_url = _extract_img_src(img)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, "", "thoibaonganhang.vn"))
    # Fallback: h2/h3 > a
    for tag in soup.find_all(["h2", "h3"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, "", "", "thoibaonganhang.vn"))
    return _deduplicate_by_url(articles)


def _extract_description(item) -> str:
    """Extract article summary/description from a listing item."""
    if not item:
        return ""
    # Look for common description/summary elements
    desc_elem = item.find(["p", "div", "span"], class_=lambda c: c and any(k in " ".join(c).lower() for k in [
        "summary", "desc", "sapo", "lead", "abstract", "intro", "excerpt", "brief", "content", "detail"
    ]))
    if desc_elem:
        text = desc_elem.get_text(strip=True)
        if len(text) > 20 and len(text) < 500:
            return text
    # Fallback: look for any <p> with reasonable length
    for p in item.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 30 and len(text) < 400:
            return text
    return ""


def _is_likely_article_url(href: str, source: str) -> bool:
    """Heuristic to detect if URL is an article (not a category page)."""
    h = href.lower()
    # Skip obvious category patterns
    category_patterns = [
        "/kinh-te", "/tai-chinh", "/chung-khoan", "/bat-dong-san",
        "/doanh-nghiep", "/kinh-doanh", "/nha-dat", "/do-thi",
        "/kinh-te.htm", "/kinh-te.html", "/tai-chinh.htm", "/chung-khoan.htm",
        "/bat-dong-san.htm", "/bat-dong-san.html", "/doanh-nghiep.htm",
    ]
    # Check if URL ends with a known category suffix (not an article)
    for pat in category_patterns:
        if h.endswith(pat):
            return False
    # Articles usually have IDs or dates in the URL
    path = href.rstrip("/").split("/")[-1] if "/" in href else href
    if path.endswith(".html") or path.endswith(".htm"):
        slug = path.replace(".html", "").replace(".htm", "")
        # If no digits at all and no "post" or article ID pattern, likely category
        has_id = any(c.isdigit() for c in slug) or "post" in slug or "-" in slug and any(c.isdigit() for c in slug)
        if not has_id:
            return False
    return True


def parse_generic_html(url: str, source_name: str) -> List[Dict]:
    """Generic parser for standard HTML news sites.
    Works for most Vietnamese news sites with article/div/li containers."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li", "section"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if any(k in cls_str for k in ["news", "article", "story", "post", "item", "box", "block", "thumb"]):
            a = item.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or href.startswith("javascript") or href.startswith("#"):
                continue
            # Skip category links
            if not _is_likely_article_url(href, source_name):
                continue
            img = item.find("img")
            image_url = _extract_img_src(img)
            description = _extract_description(item)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
            article_url = href if href.startswith("http") else urljoin(url, href)
            articles.append(_make_article(article_url, title, image_url, description, source_name))
    # Fallback: h2/h3 > a
    for tag in soup.find_all(["h2", "h3", "h4"]):
        a = tag.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript") or href.startswith("#"):
            continue
        # Skip category links
        if not _is_likely_article_url(href, source_name):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, "", "", source_name))
    return _deduplicate_by_url(articles)


def parse_cafef(url: str = "https://cafef.vn/") -> List[Dict]:
    """Parser for cafef.vn — uses .chn extension with numeric article IDs."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li", "section"]):
        a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        if not href.endswith(".chn"):
            continue
        # Skip category/menu links (no long numeric ID)
        if not re.search(r'\d{10,}\.chn$', href):
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 15:
            # Try img alt
            img = item.find("img")
            if img and img.get("alt"):
                title = img["alt"].strip()
            else:
                continue
        img = item.find("img")
        image_url = _extract_img_src(img)
        description = _extract_description(item)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(url, image_url)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, image_url, description, "cafef.vn"))
    return _deduplicate_by_url(articles)


def parse_vietnamnet(url: str = "https://vietnamnet.vn/kinh-doanh") -> List[Dict]:
    """Parser for vietnamnet.vn news sections."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []

    # Strategy 1: horizontalArticle / verticalArticle containers
    for item in soup.find_all(["article", "div"], class_=re.compile(r"(horizontal|vertical)Article")):
        thumb = item.find("a", class_="thumbArt", href=True)
        title_a = item.find("h3")
        title_a = title_a.find("a", href=True) if title_a else None

        if not title_a:
            # Fallback: any a with substantial text
            continue

        title = title_a.get_text(strip=True)
        if not title or len(title) < 10:
            continue

        href = thumb["href"] if thumb else title_a["href"]
        article_url = href if href.startswith("http") else urljoin(url, href)

        image_url = ""
        if thumb:
            img = thumb.find("img")
            if img:
                for attr in ["data-src", "src"]:
                    if img.get(attr):
                        image_url = img[attr]
                        break
                if image_url and not image_url.startswith("http"):
                    image_url = urljoin(url, image_url)
        if not image_url:
            image_url = _find_image_in_item(item, url)

        articles.append(_make_article(article_url, title, image_url, "", "vietnamnet.vn"))

    # Strategy 2: Fallback — h2/h3 > a with vietnamnet.vn href
    if len(articles) < 5:
        for tag in soup.find_all(["h2", "h3"]):
            a = tag.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if "vietnamnet.vn" not in href and not href.startswith("/"):
                continue
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            article_url = href if href.startswith("http") else urljoin(url, href)
            # Avoid duplicates
            if any(ar["url"] == article_url for ar in articles):
                continue
            image_url = _find_image_in_item(tag, url)
            articles.append(_make_article(article_url, title, image_url, "", "vietnamnet.vn"))

    return _deduplicate_by_url(articles)


def parse_vietnamfinance(url: str = "https://vietnamfinance.vn/") -> List[Dict]:
    """Parser for vietnamfinance.vn."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []

    # Strategy 1: article/news containers
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if not any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            continue
        a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        image_url = _find_image_in_item(item, url)
        articles.append(_make_article(article_url, title, image_url, "", "vietnamfinance.vn"))

    # Strategy 2: Fallback — h2/h3 > a
    if len(articles) < 5:
        for tag in soup.find_all(["h2", "h3"]):
            a = tag.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            article_url = href if href.startswith("http") else urljoin(url, href)
            if any(ar["url"] == article_url for ar in articles):
                continue
            image_url = _find_image_in_item(tag, url)
            articles.append(_make_article(article_url, title, image_url, "", "vietnamfinance.vn"))

    return _deduplicate_by_url(articles)


def parse_kbs(url: str = "https://world.kbs.co.kr/service/news_list.htm?lang=v&id=Ec") -> List[Dict]:
    """Parser for world.kbs.co.kr Vietnamese news section."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []

    # KBS uses div.news-item or similar containers
    for item in soup.find_all(["article", "div", "li"]):
        cls = item.get("class", [])
        cls_str = " ".join(cls).lower() if cls else ""
        if not any(k in cls_str for k in ["news", "article", "story", "post", "item"]):
            continue
        a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10 or href.startswith("javascript"):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        image_url = _find_image_in_item(item, url)
        articles.append(_make_article(article_url, title, image_url, "", "world.kbs.co.kr"))

    # Fallback: h2/h3/h4 > a
    if len(articles) < 3:
        for tag in soup.find_all(["h2", "h3", "h4"]):
            a = tag.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            article_url = href if href.startswith("http") else urljoin(url, href)
            if any(ar["url"] == article_url for ar in articles):
                continue
            image_url = _find_image_in_item(tag, url)
            articles.append(_make_article(article_url, title, image_url, "", "world.kbs.co.kr"))

    return _deduplicate_by_url(articles)


def parse_rss(url: str, source_name: str) -> List[Dict]:
    """Generic RSS/Atom feed parser using feedparser."""
    html = fetch_url(url)
    if not html:
        return []
    feed = feedparser.parse(html)
    articles = []
    for entry in feed.entries:
        article_url = entry.get("link", "")
        if not article_url:
            continue
        title = entry.get("title", "").strip()
        if not title:
            continue
        description = entry.get("summary", "").strip()
        # Remove HTML tags from description
        if description:
            description = re.sub(r'<[^>]+>', '', description).strip()[:200]
        # Extract image from media_content, enclosures, or summary
        image_url = ""
        # Strategy 1: media_content (Media RSS)
        media = entry.get("media_content", [])
        if media:
            image_url = media[0].get("url", "")
        # Strategy 2: enclosures
        if not image_url:
            for enc in entry.get("enclosures", []):
                if enc.get("type", "").startswith("image"):
                    image_url = enc.get("href", "")
                    break
        # Strategy 3: look for <img> in summary
        if not image_url and entry.get("summary"):
            img_match = re.search(r'<img[^>]+src=["\']([^"\'>]+)', entry["summary"])
            if img_match:
                image_url = img_match.group(1)
        if image_url and not image_url.startswith("http"):
            image_url = urljoin(url, image_url)
        articles.append(_make_article(article_url, title, image_url, description, source_name))
    return _deduplicate_by_url(articles)


def parse_pyn(url: str = "https://www.pyn.fi/en/news/") -> List[Dict]:
    """Parser for pyn.fi news/reviews/blog posts."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    # Only match actual posts (blog, reviews, investor-letters with year)
    # Skip navigation pages like /pyn-elite-fund/, /category/*, etc.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        # Must be an actual article URL (contains year after /blog/, /reviews/, /investor-letters/)
        if not re.search(r'/(blog|reviews|investor-letters)/\d{4}/', href):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        # Avoid duplicates
        if any(ar["url"] == article_url for ar in articles):
            continue
        image_url = ""
        parent = a.find_parent(["article", "div", "li"])
        if parent:
            img = parent.find("img")
            image_url = _extract_img_src(img)
            if image_url and not image_url.startswith("http"):
                image_url = urljoin(url, image_url)
        articles.append(_make_article(article_url, title, image_url, "", "pyn.fi"))
    return _deduplicate_by_url(articles)


def parse_hoaphat(url: str = "https://www.hoaphat.com.vn/tin-tuc/tin-tuc-tap-doan") -> List[Dict]:
    """Parser for hoaphat.com.vn corporate news."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/tin-tuc/" not in href or not href.endswith(".html"):
            continue
        title = a.get_text(strip=True)
        title = re.sub(r'^\d{2}/\d{2}/\d{4}\d{2}:\d{2}', '', title).strip()
        # Skip if this looks like a category/tag page
        slug = href.rstrip("/").split("/")[-1].replace(".html", "")
        # Try to extract description from nearby sibling or parent
        description = ""
        parent = a.find_parent(["li", "div", "article"])
        if parent:
            description = _extract_description(parent)
        if len(slug) < 10 or not any(c.isdigit() for c in slug):
            continue
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, "", description, "hoaphat.com.vn"))
    return _deduplicate_by_url(articles)


def parse_mwg(url: str = "https://mwg.vn/tin-tuc") -> List[Dict]:
    """Parser for mwg.vn corporate news."""
    html = fetch_url(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    articles = []
    for item in soup.find_all(["article", "div", "li"]):
        a = item.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        # MWG news URLs typically contain /tin-tuc/ or numeric IDs
        if "/tin-tuc/" not in href and not re.search(r'\d', href.split("/")[-1]):
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 15:
            continue
        # Skip menu/category items (short slugs without numbers)
        slug = href.rstrip("/").split("/")[-1]
        if len(slug) < 15 and not any(c.isdigit() for c in slug):
            continue
        description = _extract_description(item)
        article_url = href if href.startswith("http") else urljoin(url, href)
        articles.append(_make_article(article_url, title, "", description, "mwg.vn"))
    return _deduplicate_by_url(articles)


# Sources that use the generic HTML parser (standard news site layout)
GENERIC_SOURCES = [
    "znews.vn", "tienphong.vn", "nld.com.vn", "diaoc.nld.com.vn",
    "hanoimoi.vn", "nhandan.vn", "hanoionline.vn", "baophapluat.vn",
    "baotintuc.vn", "nguoiduatin.vn", "taichinhdoanhnghiep.net.vn",
    "daibieunhandan.vn", "thoibaotaichinhvietnam.vn", "baokiemtoan.vn",
    "doanhnhan.congly.vn", "tapchicongthuong.vn", "baodanang.vn",
    "vanhoavaphattrien.vn", "vtcnews.vn",
    "masanconsumer.com", "reecorp.com", "gemadept.com.vn",
    "frt.vn", "ptsc.com.vn", "viettelpost.com.vn",
    "pc1group.vn", "hado.com.vn", "digiworld.com.vn",
    "viettelconstruction.com.vn", "coteccons.vn", "cmc.com.vn",
    "datphuong.com.vn", "mic.vn", "bidiphar.com", "tvs.vn",
]

SOURCES = {
    "bnews.vn": [
        "https://bnews.vn/",
        "https://bnews.vn/tai-chinh-ngan-hang/",
        "https://bnews.vn/chung-khoan/",
        "https://bnews.vn/doanh-nghiep/",
        "https://bnews.vn/bat-dong-san/21/trang-1.html",
    ],
    "thesaigontimes.vn": [
        "https://thesaigontimes.vn/",
        "https://thesaigontimes.vn/kinh-te/",
        "https://thesaigontimes.vn/tai-chinh-ngan-hang/",
        "https://thesaigontimes.vn/chung-khoan/",
    ],
    "tinnhanhchungkhoan.vn": [
        "https://www.tinnhanhchungkhoan.vn/",
        "https://www.tinnhanhchungkhoan.vn/tai-chinh/",
        "https://www.tinnhanhchungkhoan.vn/doanh-nghiep/",
        "https://www.tinnhanhchungkhoan.vn/bat-dong-san/",
    ],
    "vneconomy.vn": [
        "https://vneconomy.vn/",
        "https://vneconomy.vn/tai-chinh.htm",
        "https://vneconomy.vn/chung-khoan.htm",
        "https://vneconomy.vn/thi-truong-bat-dong-san.htm",
        "https://vneconomy.vn/chinh-sach-bat-dong-san.htm",
        "https://vneconomy.vn/du-an-bat-dong-san.htm",
    ],
    "vietstock.vn": [
        "https://vietstock.vn/",
        "https://vietstock.vn/tin-tuc.htm",
        "https://vietstock.vn/phan-tich.htm",
        "https://vietstock.vn/doanh-nghiep.htm",
    ],
    "vnexpress.net": [
        "https://vnexpress.net/kinh-doanh",
        "https://vnexpress.net/bat-dong-san",
    ],
    "dantri.com.vn": [
        "https://dantri.com.vn/kinh-doanh.htm",
        "https://dantri.com.vn/bat-dong-san.htm",
        "https://dantri.com.vn/rss/kinh-doanh.rss",
        "https://dantri.com.vn/rss/bat-dong-san.rss",
    ],
    "nhipsongkinhdoanh.vn": [
        "https://nhipsongkinhdoanh.vn/hashtag/tin-moi-8332",
    ],
    "vietnambiz.vn": [
        "https://vietnambiz.vn/tin-moi-nhat.htm",
    ],
    "nguoiquansat.vn": [
        "https://nguoiquansat.vn/tin-moi-nhat",
    ],
    "fili.vn": [
        "https://fili.vn/",
    ],
    "theleader.vn": [
        "https://theleader.vn/",
        "https://theleader.vn/kinh-te/",
        "https://theleader.vn/tai-chinh/",
        "https://theleader.vn/chung-khoan/",
    ],
    "mekongasean.vn": [
        "https://mekongasean.vn/",
        "https://mekongasean.vn/kinh-te/",
        "https://mekongasean.vn/dau-tu/",
    ],
    "thoibaonganhang.vn": [
        "https://thoibaonganhang.vn/",
        "https://thoibaonganhang.vn/tin-tuc/",
        "https://thoibaonganhang.vn/tai-chinh/",
    ],
    "znews.vn": [
        "https://znews.vn/kinh-doanh-tai-chinh.html",
    ],
    "tienphong.vn": [
        "https://tienphong.vn/kinh-te/",
    ],
    "nld.com.vn": [
        "https://nld.com.vn/kinh-te.htm",
    ],
    "diaoc.nld.com.vn": [
        "https://diaoc.nld.com.vn/",
    ],
    "hanoimoi.vn": [
        "https://hanoimoi.vn/kinh-te",
        "https://hanoimoi.vn/do-thi",
    ],
    "nhandan.vn": [
        "https://nhandan.vn/kinhte/",
    ],
    "hanoionline.vn": [
        "https://hanoionline.vn/kinh-te.htm",
        "https://hanoionline.vn/nha-dat.htm",
    ],
    "baophapluat.vn": [
        "https://baophapluat.vn/chuyen-muc/kinh-te.html",
        "https://baophapluat.vn/chuyen-muc/bat-dong-san.html",
    ],
    "baotintuc.vn": [
        "https://baotintuc.vn/kinh-te-128ct0.htm",
    ],
    "nguoiduatin.vn": [
        "https://www.nguoiduatin.vn/kinh-te.htm",
    ],
    "taichinhdoanhnghiep.net.vn": [
        "https://taichinhdoanhnghiep.net.vn/",
    ],
    "daibieunhandan.vn": [
        "https://daibieunhandan.vn/kinh-te",
    ],
    "thoibaotaichinhvietnam.vn": [
        "https://thoibaotaichinhvietnam.vn/",
    ],
    "baokiemtoan.vn": [
        "http://baokiemtoan.vn/kinh-te",
    ],
    "doanhnhan.congly.vn": [
        "https://doanhnhan.congly.vn/",
    ],
    "tapchicongthuong.vn": [
        "https://tapchicongthuong.vn/",
    ],
    "baodanang.vn": [
        "https://baodanang.vn/kinh-te",
    ],
    "vanhoavaphattrien.vn": [
        "https://vanhoavaphattrien.vn/c/doanh-nghiep",
    ],
    "vtcnews.vn": [
        "https://vtcnews.vn/kinh-te-29.html",
    ],
    "cafef.vn": [
        "https://cafef.vn/",
    ],
    "hoaphat.com.vn": [
        "https://www.hoaphat.com.vn/tin-tuc/tin-tuc-tap-doan",
    ],
    "mwg.vn": [
        "https://mwg.vn/tin-tuc",
    ],
    "masanconsumer.com": [
        "https://masanconsumer.com/tin-tuc/tin-thi-truong/",
        "https://masanconsumer.com/tin-tuc/tin-doanh-nghiep/",
    ],
    "reecorp.com": [
        "https://www.reecorp.com/tin-tuc-su-kien/",
    ],
    "gemadept.com.vn": [
        "https://www.gemadept.com.vn/tin-tuc/tin-cong-ty/",
    ],
    "frt.vn": [
        "https://frt.vn/tin-tuc",
    ],
    "ptsc.com.vn": [
        "https://www.ptsc.com.vn/tin-tuc",
    ],
    "vng.com.vn": [
        "https://vng.com.vn/news/list.1.html",
    ],
    "viettelpost.com.vn": [
        "https://viettelpost.com.vn/tin-tuc/",
    ],
    "pc1group.vn": [
        "https://www.pc1group.vn/category/trung-tam-pr/tin-tuc/",
    ],
    "hado.com.vn": [
        "https://hado.com.vn/tin-tuc",
    ],
    "digiworld.com.vn": [
        "https://digiworld.com.vn/tin-tuc",
    ],
    "viettelconstruction.com.vn": [
        "https://viettelconstruction.com.vn/tin-tuc/",
    ],
    "coteccons.vn": [
        "https://www.coteccons.vn/news-vn/",
    ],
    "cmc.com.vn": [
        "https://www.cmc.com.vn/insight",
    ],
    "datphuong.com.vn": [
        "https://www.datphuong.com.vn/tin-tuc",
    ],
    "mic.vn": [
        "https://mic.vn/tin-tuc/",
    ],
    "bidiphar.com": [
        "https://bidiphar.com/tin-tuc/",
    ],
    "tvs.vn": [
        "https://www.tvs.vn/vi/tin-tuc?tab=news",
    ],
    "vietnamnet.vn": [
        "https://vietnamnet.vn/kinh-doanh",
        "https://vietnamnet.vn/bat-dong-san",
    ],
    "vietnamfinance.vn": [
        "https://vietnamfinance.vn/",
        "https://vietnamfinance.vn/tieu-diem/",
        "https://vietnamfinance.vn/tai-chinh/",
        "https://vietnamfinance.vn/ngan-hang/",
        "https://vietnamfinance.vn/bat-dong-san/",
        "https://vietnamfinance.vn/tai-chinh-quoc-te/",
        "https://vietnamfinance.vn/doanh-nghiep/",
        "https://vietnamfinance.vn/dau-tu/",
        "https://vietnamfinance.vn/nhan-vat/",
        "https://vietnamfinance.vn/dien-dan-vnf/",
        "https://vietnamfinance.vn/tai-chinh-ca-nhan/",
        "https://vietnamfinance.vn/thi-truong/",
        "https://vietnamfinance.vn/cong-nghe/",
    ],
    "antt.nguoiduatin.vn": [
        "https://antt.nguoiduatin.vn/",
        "https://antt.nguoiduatin.vn/doanh-nghiep.htm",
        "https://antt.nguoiduatin.vn/tai-chinh-ngan-hang.htm",
        "https://antt.nguoiduatin.vn/toan-canh.htm",
        "https://antt.nguoiduatin.vn/thi-truong-chung-khoan.htm",
        "https://antt.nguoiduatin.vn/bat-dong-san.htm",
        "https://antt.nguoiduatin.vn/phap-luat.htm",
        "https://antt.nguoiduatin.vn/photo.htm",
        "https://antt.nguoiduatin.vn/infographic.htm",
        "https://antt.nguoiduatin.vn/emagazine.htm",
    ],
    "world.kbs.co.kr": [
        "https://world.kbs.co.kr/service/news_list.htm?lang=v&id=Ec",
    ],
    "vietnamplus.vn": [
        "https://www.vietnamplus.vn/",
        "https://www.vietnamplus.vn/rss/kinhte/kinhdoanh-342.rss",
        "https://www.vietnamplus.vn/rss/kinhte/taichinh-343.rss",
        "https://www.vietnamplus.vn/rss/kinhte-311.rss",
        "https://www.vietnamplus.vn/rss/kinhte/chungkhoan-344.rss",
        "https://www.vietnamplus.vn/rss/kinhte/batdongsan-372.rss",
        "https://www.vietnamplus.vn/rss/kinhte/doanhnghiep-345.rss",
        "https://www.vietnamplus.vn/rss/kinhte/thong-tin-doanh-nghiep-433.rss",
    ],
    "pyn.fi": [
        "https://www.pyn.fi/en/news/",
    ],
    "tctd.vn": [
        "https://tctd.vn/rss/tin-moi.rss",
    ],
}


def crawl_all() -> List[Dict]:
    results = []
    # bnews.vn
    for url in SOURCES["bnews.vn"]:
        print(f"[CRAWL] bnews.vn from {url} ...")
        results.extend(parse_bnews(url))
    # thesaigontimes.vn
    for url in SOURCES["thesaigontimes.vn"]:
        print(f"[CRAWL] thesaigontimes.vn from {url} ...")
        results.extend(parse_thesaigontimes(url))
    # tinnhanhchungkhoan.vn
    for url in SOURCES["tinnhanhchungkhoan.vn"]:
        print(f"[CRAWL] tinnhanhchungkhoan.vn from {url} ...")
        results.extend(parse_tinnhanhchungkhoan(url))
    # vneconomy.vn
    for url in SOURCES["vneconomy.vn"]:
        print(f"[CRAWL] vneconomy.vn from {url} ...")
        results.extend(parse_vneconomy(url))
    # vietstock.vn
    for url in SOURCES["vietstock.vn"]:
        print(f"[CRAWL] vietstock.vn from {url} ...")
        results.extend(parse_vietstock(url))
    # fili.vn
    for url in SOURCES["fili.vn"]:
        print(f"[CRAWL] fili.vn from {url} ...")
        results.extend(parse_fili(url))
    # vnexpress.net
    for url in SOURCES["vnexpress.net"]:
        print(f"[CRAWL] vnexpress.net from {url} ...")
        results.extend(parse_vnexpress(url))
    # dantri.com.vn
    for url in SOURCES["dantri.com.vn"]:
        print(f"[CRAWL] dantri.com.vn from {url} ...")
        if url.endswith(".rss"):
            results.extend(parse_rss(url, "dantri.com.vn"))
        else:
            results.extend(parse_dantri(url))
    # existing sources
    for url in SOURCES["nhipsongkinhdoanh.vn"]:
        print(f"[CRAWL] nhipsongkinhdoanh.vn from {url} ...")
        results.extend(parse_nhipsongkinhdoanh(url))
    for url in SOURCES["vietnambiz.vn"]:
        print(f"[CRAWL] vietnambiz.vn from {url} ...")
        results.extend(parse_vietnambiz(url))
    for url in SOURCES["nguoiquansat.vn"]:
        print(f"[CRAWL] nguoiquansat.vn from {url} ...")
        results.extend(parse_nguoiquansat(url))
    # theleader.vn
    for url in SOURCES["theleader.vn"]:
        print(f"[CRAWL] theleader.vn from {url} ...")
        results.extend(parse_theleader(url))
    # mekongasean.vn
    for url in SOURCES["mekongasean.vn"]:
        print(f"[CRAWL] mekongasean.vn from {url} ...")
        results.extend(parse_mekongasean(url))
    # thoibaonganhang.vn
    for url in SOURCES["thoibaonganhang.vn"]:
        print(f"[CRAWL] thoibaonganhang.vn from {url} ...")
        results.extend(parse_thoibaonganhang(url))
    # Generic HTML sources (19 new sources)
    for source_name in GENERIC_SOURCES:
        for url in SOURCES.get(source_name, []):
            print(f"[CRAWL] {source_name} from {url} ...")
            results.extend(parse_generic_html(url, source_name))
    # cafef.vn
    for url in SOURCES["cafef.vn"]:
        print(f"[CRAWL] cafef.vn from {url} ...")
        results.extend(parse_cafef(url))
    # hoaphat.com.vn
    for url in SOURCES["hoaphat.com.vn"]:
        print(f"[CRAWL] hoaphat.com.vn from {url} ...")
        results.extend(parse_hoaphat(url))
    # vietnamnet.vn
    for url in SOURCES["vietnamnet.vn"]:
        print(f"[CRAWL] vietnamnet.vn from {url} ...")
        results.extend(parse_vietnamnet(url))
    # vietnamfinance.vn
    for url in SOURCES["vietnamfinance.vn"]:
        print(f"[CRAWL] vietnamfinance.vn from {url} ...")
        results.extend(parse_vietnamfinance(url))
    # mwg.vn
    for url in SOURCES["mwg.vn"]:
        print(f"[CRAWL] mwg.vn from {url} ...")
        results.extend(parse_mwg(url))
    # vng.com.vn (special URL pattern /news/list.N.html)
    for url in SOURCES["vng.com.vn"]:
        print(f"[CRAWL] vng.com.vn from {url} ...")
        results.extend(parse_generic_html(url, "vng.com.vn"))
    # antt.nguoiduatin.vn
    for url in SOURCES["antt.nguoiduatin.vn"]:
        print(f"[CRAWL] antt.nguoiduatin.vn from {url} ...")
        results.extend(parse_generic_html(url, "antt.nguoiduatin.vn"))
    # world.kbs.co.kr
    for url in SOURCES["world.kbs.co.kr"]:
        print(f"[CRAWL] world.kbs.co.kr from {url} ...")
        results.extend(parse_kbs(url))
    # vietnamplus.vn
    for url in SOURCES["vietnamplus.vn"]:
        print(f"[CRAWL] vietnamplus.vn from {url} ...")
        if url.endswith(".rss"):
            results.extend(parse_rss(url, "vietnamplus.vn"))
        else:
            results.extend(parse_generic_html(url, "vietnamplus.vn"))
    # pyn.fi
    for url in SOURCES["pyn.fi"]:
        print(f"[CRAWL] pyn.fi from {url} ...")
        results.extend(parse_pyn(url))
    # tctd.vn
    for url in SOURCES["tctd.vn"]:
        print(f"[CRAWL] tctd.vn from {url} ...")
        results.extend(parse_rss(url, "tctd.vn"))

    # Validate and filter out articles with server errors (parallel)
    print(f"[VALIDATE] Checking {len(results)} articles for server errors...")
    valid_results = []
    invalid_count = 0

    def _validate_article(article):
        if validate_url(article["url"]):
            return article
        return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        validated = list(executor.map(_validate_article, results))

    for art in validated:
        if art:
            valid_results.append(art)
        else:
            invalid_count += 1

    if invalid_count > 0:
        print(f"[VALIDATE] Removed {invalid_count} articles with server errors")
    results = valid_results

    # Backfill missing images by fetching article detail pages (all missing)
    results = backfill_images(results, max_workers=4, limit=9999)
    return results
