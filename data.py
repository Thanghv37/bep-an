import os
import django
import sqlite3
from pathlib import Path
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

db_path = Path(settings.BASE_DIR) / 'meal_registration_demo.sqlite3'

conn = sqlite3.connect(db_path)
cur = conn.cursor()

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
    """, (current.isoformat(), 120))

    current += timedelta(days=1)

conn.commit()
conn.close()

print("Done")