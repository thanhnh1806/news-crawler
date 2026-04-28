# News Crawler

Thu thập tin tức từ nhiều nguồn web (chạy thủ công hoặc qua server).

## Nguồn crawl

### Trang chủ + chuyên mục kinh tế (~96-100% có ảnh)

- `bnews.vn` — Trang chủ, Tài chính - Ngân hàng, Chứng khoán, Doanh nghiệp, BĐS
- `thesaigontimes.vn` — Trang chủ, Kinh tế, Tài chính - Ngân hàng, Chứng khoán
- `tinnhanhchungkhoan.vn` — Trang chủ, Tài chính, Doanh nghiệp, BĐS
- `vneconomy.vn` — Trang chủ, Tài chính, Chứng khoán, BĐS (Thị trường, Chính sách, Dự án)
- `vietstock.vn` — Trang chủ, Tin tức, Phân tích, Doanh nghiệp
- `vnexpress.net` — Kinh doanh, Bất động sản
- `dantri.com.vn` — Kinh doanh, Bất động sản

### Chuyên trang (~97-100% có ảnh)

- `theleader.vn` — Lãnh đạo mới (Kinh tế, Tài chính, Chứng khoán)
- `mekongasean.vn` — Mekong ASEAN (Kinh tế, Đầu tư)
- `thoibaonganhang.vn` — Thời báo ngân hàng
- `fili.vn` — Tài chính, Kinh tế (trước đây là subdomain của vietstock.vn)
- `nhipsongkinhdoanh.vn` — Nhịp sống kinh doanh
- `vietnambiz.vn` — VietnamBiz
- `nguoiquansat.vn` — Người quan sát

## Cách dùng

### Chạy 1 lần ngay lập tức (yêu cầu thủ công)

```bash
./run_once.sh
```

Hoặc:

```bash
cd /Users/omc-thanhnh23-m1/news-crawler
source venv/bin/activate
python src/main.py --run-once
```

### Chạy Server (tự động crawl khi refresh trang)

Chế độ server — mỗi lần bạn refresh trang web, hệ thống tự động crawl lấy dữ liệu mới nhất.

```bash
./run_server.sh
```

Sau đó mở trình duyệt tại `http://localhost:5000`:

- **Mỗi lần refresh (F5)** → tự động chạy crawl → hiển thị tin mới
- Không cần chạy lệnh crawl thủ công
- Dữ liệu vẫn được lưu vào SQLite để deduplicate
- Nhấn **Ctrl+C** để tắt server

### Mở Dashboard (trang tin tức tĩnh)

Dashboard tự động regenerate sau mỗi lần crawl.

**Chỉ mở dashboard** (không crawl):

```bash
./open_dashboard.sh
```

Hoặc mở file trực tiếp:

```bash
open dashboard/index.html
```

Tính năng dashboard:

- Hiển thị 200 bài mới nhất từ tất cả nguồn
- Trộn lẫn các nguồn tin, sắp xếp theo thời gian (mới nhất trên cùng)
- Click vào card mở link gốc trong tab mới
- ~96% bài viết có ảnh thumbnail (tự động lấy từ trang chi tiết)
- Responsive, design theo UI UX Pro Max guidelines
- **Server mode**: Auto-crawl khi refresh trang

## Cấu trúc

- `src/crawler.py` — Hàm crawl cho từng nguồn (HTML parsing, fallback selectors)
- `src/storage.py` — SQLite deduplicate theo URL
- `src/main.py` — Scheduler và CLI
- `src/generate_dashboard.py` — Export DB ra HTML tĩnh
- `src/dashboard_server.py` — Flask server (auto-crawl on refresh)
- `dashboard/index.html` — Trang tin tức tĩnh, mở bằng double-click
- `cleanup_invalid.py` — Dọn dẹp bài viết lỗi khỏi DB
- `backfill_published_at.py` — Cập nhật ngày đăng bài cho bài viết cũ
- `news.db` — Database lưu bài viết đã crawl

## Tối ưu hiệu năng

### URL Deduplication O(1)

Sử dụng **in-memory cache** (Python `set()`) thay vì query SQLite:

- **Trước**: Query DB cho mỗi bài → O(n) round-trips
- **Sau**: Cache lookup O(1), batch insert → **~10x nhanh hơn**

### Sắp xếp theo thời gian đăng bài (không phải thời gian crawl)

**Vấn đề**: Bài cũ bị đẩy lên đầu khi recrawl vì `crawled_at` được update.

**Giải pháp**:

- **`published_at`**: Ngày đăng bài thực tế (ưu tiên cao nhất, lấy từ trang web)
- **`first_seen_at`**: Thời điểm URL lần đầu xuất hiện trong DB (không thay đổi khi recrawl)
- Dashboard sort: `published_at DESC` → `first_seen_at DESC`

### Backfill ảnh + ngày đăng

Tự động vào trang chi tiết bài báo để lấy:

- **Ảnh thumbnail** từ og:image, twitter:image, JSON-LD, content area
- **Ngày đăng bài** từ meta tags, time element, structured data
- Xử lý **song song 16 workers**
- ~96% bài viết có thumbnail sau backfill

## Xử lý lỗi

### Loại bỏ bài viết Server Error

Tự động kiểm tra URL trước khi lưu DB, loại bỏ bài trả về lỗi 5xx.

**Dọn dẹp database hiện tại** (xóa bài lỗi đã lưu):

```bash
python cleanup_invalid.py
```

## Mở rộng

- Thêm nguồn: sửa `SOURCES` trong `src/crawler.py`
- Đổi khoảng thời gian: `python src/main.py --interval 10` (phút)
- Gửi Telegram: thêm module `notifier.py` và gọi trong `main.py`
