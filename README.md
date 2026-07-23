```
olist-analytics/
├── .venv/
├── data/
│   ├── raw/                     
│   ├── interim/                 
│   └── processed/               
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
├── documents/                    
│   ├── ERD.svg
│   └── schema.png
│
├── reports/                      # Output cuối: hình ảnh, báo cáo insight
│   ├── figures/
│   └── insights_summary.md
│
├── README.md                    
├── requirements.txt              
└── .gitignore                   
```