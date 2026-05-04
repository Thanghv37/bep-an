import sqlite3
from pathlib import Path
from django.conf import settings
from datetime import date, timedelta

db_path = Path(settings.BASE_DIR) / 'meal_registration_demo.sqlite3'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Tạo bảng nếu chưa có (an toàn)
cur.execute("""
CREATE TABLE IF NOT EXISTS meal_registration_summary (
    date TEXT PRIMARY KEY,
    registered_count INTEGER
)
""")

start_date = date(2026, 4, 29)
end_date = date(2026, 5, 10)

current = start_date

while current <= end_date:
    cur.execute("""
        INSERT OR REPLACE INTO meal_registration_summary (date, registered_count)
        VALUES (?, ?)
    """, (current.isoformat(), 120))  # 120 người

    current += timedelta(days=1)

conn.commit()
conn.close()

print("Đã tạo dữ liệu từ 29/4 → 10/5")