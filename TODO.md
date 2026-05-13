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

### 3. ~~Tách `SECRET_KEY` khỏi git~~ — ĐÃ XỬ LÝ (2026-05-13)
~~[config/settings.py](config/settings.py) vẫn có `SECRET_KEY = 'django-insecure-...'` hardcoded.~~

**Đã đóng**: code đọc qua `os.getenv('SECRET_KEY', '<dev fallback>')`. Trên prod **bắt buộc** set `SECRET_KEY` trong systemd (xem [DEPLOY.md](DEPLOY.md) phần Env vars). Fallback trong code có prefix `django-insecure-dev-only-` nên Django check vẫn cảnh báo nếu lỡ chạy prod chưa set env.

### 4. ~~Tắt `DEBUG` và siết `ALLOWED_HOSTS` trên prod~~ — ĐÃ XỬ LÝ (2026-05-13)
~~Hiện trên prod: `DEBUG=True`, `ALLOWED_HOSTS=['*']`.~~

**Đã đóng**: `DEBUG = os.getenv('DJANGO_DEBUG', 'False') == 'True'` (default an toàn). `ALLOWED_HOSTS` đọc từ `DJANGO_ALLOWED_HOSTS` (CSV), khi DEBUG=True và env rỗng thì fallback `localhost,127.0.0.1` cho dev. Trên prod cần set 2 env này trong systemd — xem [DEPLOY.md](DEPLOY.md).

---

## 🟡 Tính năng

### 5. Review double-counting (đánh giá 2 lần từ 1 người)
[reviews/views.py](reviews/views.py): public review (anonymous) và logged-in review là 2 record riêng biệt trong DB. 1 người có thể quét QR vote ẩn danh, sau đó login vote lần nữa → báo cáo Like/Dislike bị +2 từ cùng 1 người.

**Hướng fix khuyến nghị**: khi user login, check session đó có public review (`user=None, session_key=X`) hôm nay → gắn record đó vào user (`review.user = request.user`). Sau đó luồng login review sẽ thấy "đã đánh giá" và không cho vote lại.

### 6. ~~Poll feedback NetChat~~ — ĐÃ GỠ BỎ
~~Per-channel baseline để tránh mất tin & gọi thừa.~~

**Đã đóng (2026-05-12)**: gỡ hẳn tính năng thu thập góp ý qua DM bot. Lý do: bot bị NetChat soft-suspend vì poll_feedback gọi 44+ API call/phút sau khi bot broadcast đặt cơm. User quyết tắt hẳn, bắt buộc góp ý qua web. Code đã xóa, model `FeedbackMessage` đã drop (migration 0005). Nếu sau này muốn làm lại, ưu tiên outgoing webhook Mattermost thay vì polling.

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

### 11. Audit template null-safety
Hôm 2026-05-11 phát hiện crash `VariableDoesNotExist` ở [registration_list.html](templates/registrations/registration_list.html) do dùng `default:profile.full_name` khi `profile=None`. Cần audit các template khác có pattern tương tự — bất kỳ chỗ nào access `obj.attr` với `obj` là kết quả `dict.get()` / `Model.first()` / FK nullable đều có thể gặp lỗi tương tự khi data thực có null. Defensive pattern: `{% if obj %}{{ obj.attr }}{% endif %}` thay vì `{{ obj.attr|default:"" }}`.

### 12. FOUC khi load trang — Bootstrap CSS từ CDN chậm
Khi mở trang heavy Bootstrap (vd `/users/`), thấy ~0.5s "raw flash" trước khi CSS load xong. Nguyên nhân: [base.html](templates/base.html) load Bootstrap CSS + Icons từ `cdn.jsdelivr.net`, mạng nội bộ Viettel có firewall/throttle nên chậm.

**Hướng fix khuyến nghị**: download Bootstrap (`bootstrap.min.css`) và Bootstrap Icons về `static/vendor/`, serve qua nginx local. Ưu điểm: load instant, không phụ thuộc internet outbound, hoạt động kể cả khi mất mạng. Nhược điểm: ~250KB commit vào repo, phải update Bootstrap thủ công khi cần.

**Quick fix tạm**: thêm `<script>document.documentElement.style.visibility='hidden'</script>` đầu `<head>` và remove ở `window.load` event → đổi 0.5s "raw flash" thành 0.5s trang trắng (clean hơn nhưng không nhanh hơn).

### 13. OTP flow: lấy username từ email bằng `split('@')`
[accounts/views.py](accounts/views.py) `request_otp`: `username = profile.email.split('@')[0]`. Giả định email luôn dạng `username@viettel.com.vn`. Nếu user có email khác domain hoặc email trống → có thể lỗi. Đã có check `if not email` trước, nhưng vẫn nên thêm validation chặt hơn.

---

## 📅 Cập nhật

- 2026-05-10: Tạo file. Ghi lại các điểm tồn đọng sau phiên refactor lớn (OTP login, env var, AI/Bot config UI).
- 2026-05-11: Thêm mục #6 (per-channel baseline cho poll feedback NetChat) sau khi tích hợp tính năng thu thập DM.
- 2026-05-11: Thêm mục #11 (audit template null-safety) sau khi fix crash ở registration_list khi profile=None.
- 2026-05-11: Thêm mục #12 (FOUC do Bootstrap CDN chậm) sau khi user thấy 0.5s raw flash khi load trang Quản lý người dùng.
- 2026-05-12: Cập nhật mục #6 — bổ sung điểm "gọi API thừa sau broadcast" sau sự cố bot bị soft-suspend lúc 9:30 do poll_feedback gọi 44 channels với throttle 0.2s (~220 req/min). Đã quick-mitigate bằng throttle 1.2s; root-cause fix vẫn cần per-channel cursor.
- 2026-05-12: Đóng mục #6 — user quyết định gỡ hẳn tính năng thu thập góp ý qua DM NetChat (bắt buộc góp ý qua web). Code + model + migration đã xóa.
- 2026-05-13: Đóng mục #3 + #4 — tách `SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` ra env var. Code default an toàn cho prod (DEBUG=False, ALLOWED_HOSTS=[]); dev fallback localhost. [DEPLOY.md](DEPLOY.md) đã cập nhật ví dụ systemd.
