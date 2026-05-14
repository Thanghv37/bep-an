# 🚀 Quy trình Deploy

Hướng dẫn deploy code từ máy dev lên server production. **Bookmark file này** để mỗi lần deploy mở ra làm theo.

---

## 📍 Thông tin server

- **SSH**: `ssh ipcdkv2@171.232.250.6`
- **Project path**: `/home/ipcdkv2/thanghv37`
- **Service**: `bep-an` (Gunicorn) chạy trên port 6011
- **DB**: PostgreSQL local, password lưu trong systemd env var

---

## 🔄 Quy trình deploy chuẩn (5 bước)

### 0. Trên máy DEV — push code lên GitHub

```powershell
git add .
git commit -m "mô tả ngắn"
git push origin main
```

Nếu push fail → trên dev có local change xung đột với remote → resolve trước.

---

### 1. SSH vào server + pull code mới

```bash
ssh ipcdkv2@171.232.250.6
cd ~/thanghv37
source venv/bin/activate
git pull origin main
```

→ Phải báo `Updating ...` và `Fast-forward`. Nếu báo `Aborting` xem [Troubleshooting](#-troubleshooting).

### 2. Cài thư viện mới (nếu requirements đổi)

```bash
pip install -r requirements.txt
```

Nếu in toàn `Requirement already satisfied` → không có gì mới, OK.

### 3. Apply migration (**LUÔN CHẠY** — không skip)

```bash
DB_PASSWORD=thanghv37 python manage.py migrate
```

⚠️ **Quy tắc vàng**: lần nào pull code xong cũng chạy migrate, **kể cả khi nghĩ "không đổi schema"**. Lý do: có thể commit trước đó có migration mà server chưa apply — sẽ gây lỗi `ProgrammingError: column ... does not exist` khi restart (đã xảy ra 2026-05-12, mất 5 phút để fix). `No migrations to apply` không tốn gì, sai một lần là production xuống.

⚠️ **Bắt buộc prefix `DB_PASSWORD=...`** vì shell không có env var.

→ `No migrations to apply` = OK, hoặc thấy `Applying ...` = migration mới đã chạy.

### 4. Collect static (nếu có sửa CSS/JS trong template hoặc folder static)

```bash
DB_PASSWORD=thanghv37 python manage.py collectstatic --noinput
```

→ Báo `N static files copied` hoặc `0 copied, N unmodified`.

### 5. Restart Gunicorn

```bash
sudo systemctl restart bep-an
sudo systemctl status bep-an
```

→ Phải thấy `Active: active (running)` màu xanh.

---

## 🧪 Verify sau deploy

Mở web → đăng nhập → kiểm tra tính năng vừa deploy. Nếu trang load lỗi 500:

```bash
sudo journalctl -u bep-an -n 50 --no-pager
```

---

## 🛟 Troubleshooting

### `git pull` báo "Aborting" — local changes overwrite

Nguyên nhân: file local trên server đã sửa khác với remote.

```bash
# Xem file nào bị conflict
git status

# Xem khác gì
git diff <file>

# Nếu local change KHÔNG cần thiết (vd password cũ hardcoded) → discard
git checkout -- <file>
git pull origin main

# Nếu local change CẦN giữ (rare) → stash + merge
git stash push -m "backup" <file>
git pull origin main
git stash pop  # có thể conflict, sửa thủ công
```

### `manage.py` báo `fe_sendauth: no password supplied`

Quên prefix env var. Chạy lại:

```bash
DB_PASSWORD=thanghv37 python manage.py <command>
```

Hoặc export 1 lần cho session:

```bash
export DB_PASSWORD=thanghv37
python manage.py <command>
```

### Sửa file `/etc/systemd/system/bep-an.service` mà không có hiệu lực

Thiếu `daemon-reload`. Chạy:

```bash
sudo systemctl daemon-reload
sudo systemctl restart bep-an
```

### Service vẫn chạy code cũ sau pull

Restart Gunicorn để load code mới:

```bash
sudo systemctl restart bep-an
```

### Migration báo `Unknown command: 'X'`

App management command file có thể thiếu, hoặc git pull chưa lấy về. Kiểm tra:

```bash
git log --oneline -3       # commit mới nhất phải có
ls reviews/management/commands/  # file phải tồn tại
```

---

## 📅 Cron / systemd timer trên server

### `db-backup.timer` — backup PostgreSQL hàng ngày

Backup bep_an DB ra `/home/ipcdkv2/db_backups/` mỗi ngày lúc 02:00 VN (19:00 UTC server time). Giữ 7 bản gần nhất, tự xoá bản cũ. Unit file commit trong [scripts/](scripts/) của repo.

**Setup lần đầu (chạy 1 lần trên server, sau khi pull về có folder scripts/):**

```bash
# 1. Cấp quyền execute cho script
chmod +x ~/thanghv37/scripts/db_backup.sh

# 2. Symlink unit files vào systemd
sudo ln -sf /home/ipcdkv2/thanghv37/scripts/db-backup.service /etc/systemd/system/db-backup.service
sudo ln -sf /home/ipcdkv2/thanghv37/scripts/db-backup.timer /etc/systemd/system/db-backup.timer

# 3. Reload systemd để nhận unit mới
sudo systemctl daemon-reload

# 4. Test backup ngay lần đầu (thủ công) — verify script chạy OK
sudo systemctl start db-backup.service
sudo systemctl status db-backup.service
ls -lh ~/db_backups/

# 5. Bật timer chạy daily
sudo systemctl enable --now db-backup.timer

# 6. Verify timer đã schedule
sudo systemctl list-timers | grep db-backup
```

**Recovery — phục hồi DB từ backup (khi có sự cố):**

```bash
# Liệt kê bản backup có sẵn
ls -lht ~/db_backups/

# CẢNH BÁO: lệnh dưới sẽ XOÁ TOÀN BỘ DB hiện tại và thay bằng bản backup.
# Stop bep-an trước để tránh ghi đè trong khi restore:
sudo systemctl stop bep-an.service

# Drop + recreate DB:
sudo -u postgres psql -c "DROP DATABASE bep_an;"
sudo -u postgres psql -c "CREATE DATABASE bep_an OWNER postgres;"

# Restore từ file backup cụ thể:
gunzip < ~/db_backups/bep_an_2026-05-13_190000.sql.gz | sudo -u postgres psql bep_an

# Bật lại app
sudo systemctl start bep-an.service
sudo systemctl status bep-an.service
```

**Debug khi backup fail:**
```bash
sudo journalctl -u db-backup.service -n 50 --no-pager
sudo systemctl status db-backup.timer    # xem lần chạy gần nhất + lần chạy tiếp theo
```

### `participation-report.timer` — auto-gửi báo cáo Tham gia qua NetChat DM

Mỗi phút check: nếu giờ:phút VN khớp `send_time` cấu hình trong UI + hôm nay chưa gửi → gửi Excel báo cáo cho danh sách MNV trong UI cài đặt. Recipient + send_time đổi qua trang `/registrations/participation/` → icon ⚙ (modal cài đặt). Không cần edit lại unit file khi đổi giờ.

**Setup lần đầu (chạy 1 lần trên server, sau khi pull về có folder scripts/):**

```bash
# 1. Symlink unit files vào systemd
sudo ln -sf /home/ipcdkv2/thanghv37/scripts/participation-report.service /etc/systemd/system/participation-report.service
sudo ln -sf /home/ipcdkv2/thanghv37/scripts/participation-report.timer /etc/systemd/system/participation-report.timer

# 2. Reload systemd
sudo systemctl daemon-reload

# 3. Test thủ công ngay — dùng --force để bỏ qua check thời gian
sudo systemctl edit --full --no-validate participation-report.service  # không cần, chỉ verify
# Thay vì sửa unit, test bằng cách chạy command trực tiếp:
cd ~/thanghv37
DB_PASSWORD=thanghv37 venv/bin/python manage.py send_participation_report --force

# 4. Bật timer chạy mỗi phút
sudo systemctl enable --now participation-report.timer

# 5. Verify timer
sudo systemctl list-timers | grep participation-report
```

**Debug:**
```bash
sudo journalctl -u participation-report.service -n 50 --no-pager
sudo systemctl status participation-report.timer
```

**Tắt tạm:**
```bash
sudo systemctl stop participation-report.timer
sudo systemctl disable participation-report.timer
```

**Gỡ hoàn toàn:**
```bash
sudo systemctl stop participation-report.timer
sudo systemctl disable participation-report.timer
sudo rm /etc/systemd/system/participation-report.timer /etc/systemd/system/participation-report.service
sudo systemctl daemon-reload
```

### `poll-feedback` (đã gỡ bỏ 2026-05-12)

Nếu service vẫn còn trên server, xoá:
```bash
sudo systemctl stop poll-feedback.timer poll-feedback.service
sudo systemctl disable poll-feedback.timer poll-feedback.service
sudo rm /etc/systemd/system/poll-feedback.timer /etc/systemd/system/poll-feedback.service
sudo systemctl daemon-reload
```

---

## 🔑 Env vars trên server (trong systemd)

Hiện đang set trong `/etc/systemd/system/bep-an.service`:

- `DB_PASSWORD` — mật khẩu PostgreSQL
- `GEMINI_API_KEY` — Google Gemini API key
- `SECRET_KEY` — Django secret key (bắt buộc, đừng dùng fallback trong code)
- `DJANGO_DEBUG` — phải để `False` trên prod (default trong code đã là False, nhưng nên set rõ)
- `DJANGO_ALLOWED_HOSTS` — `net2kitchen.viettel.pro.vn,127.0.0.1`. Nếu bỏ trống và `DJANGO_DEBUG=False`, Django sẽ từ chối mọi request → 400 Bad Request.

Sửa env var → cần `sudo systemctl daemon-reload` + `sudo systemctl restart <service>`.

Generate `SECRET_KEY` mới:
```bash
DB_PASSWORD=<pw> python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Ví dụ block `[Service]` đầy đủ trong `/etc/systemd/system/bep-an.service`:
```ini
Environment="DB_PASSWORD=<password>"
Environment="GEMINI_API_KEY=<api_key>"
Environment="SECRET_KEY=<generated_key>"
Environment="DJANGO_DEBUG=False"
Environment="DJANGO_ALLOWED_HOSTS=net2kitchen.viettel.pro.vn,127.0.0.1"
```

---

## ⚙️ Gunicorn config (trong `bep-an.service`)

Dòng `ExecStart` hiện tại:
```
ExecStart=/home/ipcdkv2/thanghv37/venv/bin/gunicorn config.wsgi:application --workers 5 --timeout 120 --bind 0.0.0.0:6011
```

- `--workers 5`: đủ cho ~50 user nội bộ, 1 worker bận gọi AI vẫn còn 4 worker phục vụ request khác. Đừng nâng quá cao vì mỗi worker copy hết app vào RAM.
- `--timeout 120`: Gemini AI có thể mất 30-60s/call (gợi ý menu, phân tích dinh dưỡng). Default gunicorn là 30s → worker bị SIGKILL giữa chừng → request đứng cùng nhà bị connection reset (browser show "Internal Server Error", F5 lại OK).
- Sau khi sửa unit: `sudo systemctl daemon-reload && sudo systemctl restart bep-an`.

---

## 🚨 Rollback khẩn cấp

Nếu deploy gây lỗi production:

```bash
# Xem 5 commit gần nhất
git log --oneline -5

# Quay lùi về commit cũ
git reset --hard <hash_cũ>

# Nếu có migration mới → rollback luôn
DB_PASSWORD=thanghv37 python manage.py migrate <app> <migration_cũ>

# Restart
sudo systemctl restart bep-an
```
