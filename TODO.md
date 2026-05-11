# 📌 Những điểm cần xử lý sau

Ghi lại các vấn đề / cải tiến đã biết nhưng tạm hoãn. Sắp xếp theo độ ưu tiên.

---

## 🔴 Bảo mật (nên làm sớm)

### 1. Đổi password DB trên server
Password `thanghv37` đã từng nằm trong git history (trước khi tách ra env var). Bất kỳ ai có quyền đọc repo đều thấy. Cần:
1. Đặt password mới mạnh hơn cho user `postgres` của PostgreSQL
2. Update `Environment="DB_PASSWORD=..."` trong `/etc/systemd/system/bep-an.service`
3. Update `.env` trên dev (nếu cần kết nối DB prod)

### 2. Revoke `GEMINI_API_KEY` cũ
Key cũ đã lộ trong log chat hôm 2026-05-10. Vào https://aistudio.google.com/app/apikey → xóa key cũ → tạo key mới → update vào systemd service.

### 3. Tách `SECRET_KEY` khỏi git
[config/settings.py](config/settings.py) vẫn có `SECRET_KEY = 'django-insecure-...'` hardcoded. Django warning rõ là `insecure`. Cần làm tương tự cách đã làm với `DB_PASSWORD`:
```python
SECRET_KEY = os.getenv('SECRET_KEY', '<fallback>')
```
Generate key mới: `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`

### 4. Tắt `DEBUG` và siết `ALLOWED_HOSTS` trên prod
Hiện trên prod: `DEBUG=True`, `ALLOWED_HOSTS=['*']` — lộ stack trace khi lỗi, nhận request từ mọi host. Cần:
- `DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'`
- `ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',')`
- Trên server set: `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=domain.com,127.0.0.1`

---

## 🟡 Tính năng

### 5. Review double-counting (đánh giá 2 lần từ 1 người)
[reviews/views.py](reviews/views.py): public review (anonymous) và logged-in review là 2 record riêng biệt trong DB. 1 người có thể quét QR vote ẩn danh, sau đó login vote lần nữa → báo cáo Like/Dislike bị +2 từ cùng 1 người.

**Hướng fix khuyến nghị**: khi user login, check session đó có public review (`user=None, session_key=X`) hôm nay → gắn record đó vào user (`review.user = request.user`). Sau đó luồng login review sẽ thấy "đã đánh giá" và không cho vote lại.

### 6. Poll feedback NetChat: per-channel baseline để tránh mất tin
[reviews/feedback_poller.py](reviews/feedback_poller.py) hiện dùng 1 timestamp baseline chung (`feedback_last_poll_ts`). Edge case: nếu 1 channel succeed (ts mới hơn) + 1 channel khác fail 429 (ts cũ hơn) → cuối loop baseline advance qua post của channel fail → lần poll sau channel đó không vào diện active → tin bị bỏ qua.

**Hướng fix**: lưu `last_post_id` riêng cho từng channel trong bảng (vd `FeedbackChannelCursor`) thay vì 1 timestamp global.

**Long-term**: chuyển từ polling sang **outgoing webhook** Mattermost — gần real-time, không lo rate limit, không lo mất tin. Cần endpoint HTTPS public + cấu hình webhook trên Mattermost admin.

---

## 🟢 Tech debt (làm khi rảnh)

### 7. SDK `google.generativeai` đã deprecated
Chạy `manage.py check` thấy warning: SDK cũ không còn được Google bảo trì, khuyến nghị chuyển sang `google.genai`. Cả 2 đã có trong [requirements.txt](requirements.txt). Cần refactor:
- [core/ai_config.py](core/ai_config.py)
- [core/services/menu_ai.py](core/services/menu_ai.py)
- [core/services/finance_ai.py](core/services/finance_ai.py)
- [core/services/nutrition_ai.py](core/services/nutrition_ai.py)

API mới khác cú pháp, cần đọc docs trước khi migrate.

### 8. `.claude/settings.local.json` đang trong git
File cấu hình cá nhân của Claude Code không nên ở repo. Khi nào có người khác cùng làm → thêm vào `.gitignore` và `git rm --cached .claude/settings.local.json`.

### 9. AI services dùng `print()` thay vì logging
[core/services/finance_ai.py](core/services/finance_ai.py) và [nutrition_ai.py](core/services/nutrition_ai.py) khi lỗi chỉ `print(...)` — log không vào systemd journal. Nên đổi sang `logging.getLogger(__name__).error(...)` như [menu_ai.py](core/services/menu_ai.py) đã làm.

### 10. Xóa `set_unusable_password()` thừa
[accounts/views.py](accounts/views.py) trong `user_create`: `User.objects.create_user(username=...)` không truyền password thì Django đã tự gọi `set_unusable_password()`. Hai dòng `user.set_unusable_password()` + `user.save()` thứ 2 là dư.

### 11. OTP flow: lấy username từ email bằng `split('@')`
[accounts/views.py](accounts/views.py) `request_otp`: `username = profile.email.split('@')[0]`. Giả định email luôn dạng `username@viettel.com.vn`. Nếu user có email khác domain hoặc email trống → có thể lỗi. Đã có check `if not email` trước, nhưng vẫn nên thêm validation chặt hơn.

---

## 📅 Cập nhật

- 2026-05-10: Tạo file. Ghi lại các điểm tồn đọng sau phiên refactor lớn (OTP login, env var, AI/Bot config UI).
- 2026-05-11: Thêm mục #6 (per-channel baseline cho poll feedback NetChat) sau khi tích hợp tính năng thu thập DM.
