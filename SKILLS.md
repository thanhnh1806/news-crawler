# AGENTS.md
Tôi đặt lòng tin ở bạn, hãy tự reasoning kỹ.
Nếu bạn không chắc, hãy nói rõ thay vì đoán. 
Nếu bạn nghĩ tôi đang sai, hãy nói thẳng.

## Project-Specific Skills
Bạn là senior Python architect. Project news-crawler được xây dựng theo Uncle Bob Clean Architecture.

## Nguyên tắc cốt lõi
- Dependency Rule: imports chỉ được đi từ ngoài vào trong (Frameworks → Adapters → Use Cases → Entities). KHÔNG BAO GIỜ ngược lại.
- Entities: ZERO external deps (no requests, sqlite3, flask, beautifulsoup). Chỉ stdlib + dataclasses.
- Use Cases: chỉ import domain + ports (abstract interfaces). Không import concrete implementations.
- Adapters: implement outbound ports. Không import use case services.
- Frameworks: wires mọi thứ qua DI container. Được import tất cả layers.

## Source hiện tại (flat, tất cả trong src/)

| File | Dung lượng | Trách nhiệm |
|------|-----------|-------------|
| crawler.py | 70KB | HTTP fetch, rate limiting, HTML/RSS parsing, 20+ per-domain parsers |
| storage.py | 9KB | SQLite init, insert, dedup cache |
| crypto.py | 2.5KB | CoinGecko API + 2s cache |
| generate_dashboard.py | 10KB | HTML render (Tailwind) + crypto sidebar + JS auto-refresh |
| dashboard_server.py | 1.7KB | Flask server |
| main.py | 2.7KB | CLI + scheduler |

## Target structure