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