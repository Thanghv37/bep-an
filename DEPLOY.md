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

### 3. Apply migration (nếu có model mới)

```bash
DB_PASSWORD=thanghv37 python manage.py migrate
```

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

Hiện không có timer nào. (Trước đây có `poll-feedback.timer` để quét DM NetChat — đã gỡ bỏ 2026-05-12 vì gây vi phạm rate limit của NetChat. Tham khảo phần "Tắt poll-feedback" dưới đây nếu service vẫn còn trên server.)

### Tắt `poll-feedback` (chạy 1 lần trên server)
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

Sửa env var → cần `sudo systemctl daemon-reload` + `sudo systemctl restart <service>`.

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
