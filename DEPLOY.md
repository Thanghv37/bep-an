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

| Timer | Service | Tần suất | Mô tả |
|---|---|---|---|
| `poll-feedback.timer` | `poll-feedback.service` | 30 phút | Quét DM NetChat → lưu vào `FeedbackMessage` |

Xem trạng thái:
```bash
sudo systemctl list-timers
sudo journalctl -u poll-feedback.service -n 30
```

Force chạy ngay (không đợi timer):
```bash
sudo systemctl start poll-feedback.service
```

---

## 🔑 Env vars trên server (trong systemd)

Hiện đang set trong `/etc/systemd/system/bep-an.service` và `/etc/systemd/system/poll-feedback.service`:

- `DB_PASSWORD` — mật khẩu PostgreSQL
- `GEMINI_API_KEY` — Google Gemini API key

Sửa env var → cần `sudo systemctl daemon-reload` + `sudo systemctl restart <service>`.

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
