"""CLI entry point — replaces main.py.
Uses DI container to wire use cases."""
import argparse
import schedule
import time
import sys
import os
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infrastructure.config import AppConfig
from infrastructure.container import Container


def run_crawl(container: Container):
    print("\n" + "=" * 60)
    print(f"[SCHEDULE] Crawling at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    container.article_repository.init_db()
    new_count = container.crawl_use_case.execute()
    container.dashboard_use_case.execute()
    return new_count


def main():
    parser = argparse.ArgumentParser(description="News Crawler - Thu thập tin tức định kỳ")
    parser.add_argument("--run-once", action="store_true", help="Chạy 1 lần ngay lập tức và thoát")
    parser.add_argument("--interval", type=int, default=15, help="Khoảng thời gian giữa các lần crawl (phút), mặc định 15")
    parser.add_argument("--open-dashboard", action="store_true", help="Chỉ mở dashboard trong trình duyệt")
    args = parser.parse_args()

    config = AppConfig()
    container = Container(config)

    if args.open_dashboard:
        if os.path.exists(config.html_path):
            webbrowser.open("file://" + os.path.abspath(config.html_path))
        return

    container.article_repository.init_db()
    print("[INIT] Database initialized")

    if args.run_once:
        run_crawl(container)
        return

    interval = args.interval
    print(f"[SCHEDULER] Starting with interval: {interval} minutes")

    run_crawl(container)

    schedule.every(interval).minutes.do(run_crawl, container=container)

    print(f"[SCHEDULER] Running every {interval} minutes. Press Ctrl+C to stop.\n")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[EXIT] Stopped by user")


if __name__ == "__main__":
    main()
