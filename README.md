```
olist-analytics/
├── .venv/
├── data/
│   ├── raw/                     # CSV gốc (đã có) — không bao giờ chỉnh sửa trực tiếp
│   ├── interim/                 # Data sau khi join/clean sơ bộ, chưa hoàn chỉnh
│   └── processed/               # Data sạch, sẵn sàng cho phân tích (parquet/csv)
│
├── notebooks/                   # Jupyter notebooks, đánh số theo thứ tự làm việc
│   ├── 01_data_cleaning.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_rfm_segmentation.ipynb
│   ├── 04_delivery_review_analysis.ipynb
│   ├── 05_market_basket.ipynb
│   └── 06_seller_category_performance.ipynb
│
├── src/                          # Code tái sử dụng (thay vì lặp lại trong notebook)
│   ├── __init__.py
│   ├── data_loader.py            # Hàm load & join các bảng
│   ├── cleaning.py               # Hàm xử lý missing/outlier
│   └── features.py               # Hàm tạo cột phái sinh (delivery_time, RFM...)
│
├── dashboard/                    # App Streamlit hoặc file Power BI/Tableau
│   └── app.py
│
├── documents/                    # (đã có)
│   ├── ERD.svg
│   └── schema.png
│
├── reports/                      # Output cuối: hình ảnh, báo cáo insight
│   ├── figures/
│   └── insights_summary.md
│
├── README.md                     # Quan trọng nhất cho CV — xem gợi ý bên dưới
├── requirements.txt              # (đã có)
└── .gitignore                    # loại trừ .venv/, data/raw nếu file quá nặng cho GitHub
```

### Vài lưu ý quan trọng
- **Tách `notebooks/` và `src/`**: Notebook dùng để khám phá/trình bày, nhưng logic xử lý lặp lại (load, clean, tạo feature) nên đưa vào `src/` dưới dạng hàm — nhà tuyển dụng nhìn vào sẽ thấy bạn viết code có tổ chức, không chỉ copy-paste trong notebook.
- **`data/raw` không commit lên GitHub** nếu dataset nặng — thêm vào `.gitignore`, chỉ để hướng dẫn tải trong README.
- **`reports/insights_summary.md`**: đây là file "tóm tắt insight" độc lập, tách khỏi code — người xem CV lười đọc code có thể đọc file này để thấy ngay giá trị project.
- **README.md ở root** nên có cấu trúc: Giới thiệu project → Dataset → Câu hỏi phân tích → Cách chạy → Kết quả nổi bật (kèm hình từ `reports/figures`) → Kết luận.