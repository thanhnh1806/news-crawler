import argparse
import schedule
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from storage import init_db, insert_articles_batch
from crawler import crawl_all
from generate_dashboard import generate_dashboard, open_dashboard


def run_crawl():
    print("\n" + "=" * 60)
    print(f"[SCHEDULE] Crawling at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Crawl articles (includes backfill for images)
    articles = crawl_all()
    
    # Batch insert with optimized deduplication
    new_count = insert_articles_batch(articles)
    
    # Print new articles
    inserted_urls = set()
    for article in articles:
        # Check if this was newly inserted by seeing if we've printed it
        if article.get('url') not in inserted_urls:
            # This is a new article
            inserted_urls.add(article['url'])
            if len(inserted_urls) <= new_count:  # Only print first 'new_count' articles
                print(f"\n[NEW] [{article['source']}] {article['title']}")
                print(f"      URL: {article['url']}")
                if article['image_url']:
                    print(f"      IMG: {article['image_url']}")
                if article['description']:
                    desc = article['description'][:150] + "..." if len(article['description']) > 150 else article['description']
                    print(f"      DESC: {desc}")
    
    print(f"\n[SUMMARY] Total: {len(articles)} | New inserted: {new_count}")
    print("=" * 60 + "\n")
    generate_dashboard()
    return new_count


def main():
    parser = argparse.ArgumentParser(description="News Crawler - Thu thập tin tức định kỳ")
    parser.add_argument("--run-once", action="store_true", help="Chạy 1 lần ngay lập tức và thoát")
    parser.add_argument("--interval", type=int, default=15, help="Khoảng thời gian giữa các lần crawl (phút), mặc định 15")
    parser.add_argument("--open-dashboard", action="store_true", help="Chỉ mở dashboard trong trình duyệt")
    args = parser.parse_args()

    if args.open_dashboard:
        open_dashboard()
        return

    init_db()
    print("[INIT] Database initialized")

    if args.run_once:
        run_crawl()
        return

    interval = args.interval
    print(f"[SCHEDULER] Starting with interval: {interval} minutes")
    
    # Run immediately first time
    run_crawl()
    
    schedule.every(interval).minutes.do(run_crawl)
    
    print(f"[SCHEDULER] Running every {interval} minutes. Press Ctrl+C to stop.\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[EXIT] Stopped by user")


if __name__ == "__main__":
    main()
