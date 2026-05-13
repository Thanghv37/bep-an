# 🍱 Hệ thống Quản lý Bếp ăn Thông minh (Smart Kitchen Management)
### 📍 Dự án Quản lý Bếp ăn KV2 - VT NET

![Django](https://img.shields.io/badge/django-%23092E20.svg?style=for-the-badge&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Bootstrap](https://img.shields.io/badge/bootstrap-%23563D7C.svg?style=for-the-badge&logo=bootstrap&logoColor=white)
![AI Gemini](https://img.shields.io/badge/AI-Gemini-blue?style=for-the-badge&logo=google-gemini&logoColor=white)

---

## 🌟 Giới thiệu
Hệ thống Quản lý Bếp ăn là giải pháp toàn diện giúp tự động hóa quy trình vận hành bếp ăn nội bộ công ty. Dự án tích hợp trí tuệ nhân tạo (AI) để phân tích dinh dưỡng, lên thực đơn tự động và hệ thống thông báo qua Bot (Mattermost/NetChat), giúp tối ưu hóa chi phí và nâng cao trải nghiệm người ăn.

## ✨ Tính năng chính

### 1. Dashboard & AI Analysis
*   **Tổng quan Real-time:** Theo dõi số lượng người đăng ký, chi phí thu-chi và chênh lệch tài chính trong ngày.
*   **AI Dinh dưỡng:** Tự động phân tích hàm lượng Calo và đưa ra lời khuyên sức khỏe dựa trên thực đơn thực tế qua Gemini AI.
*   **Xu hướng tài chính:** Biểu đồ so sánh thu-chi theo tuần/tháng/năm bằng Chart.js.

### 2. Quản lý Đăng ký & Điểm danh
*   **Import Đăng ký:** Hỗ trợ import danh sách đăng ký ăn hàng ngày từ file Excel.
*   **Gửi thông báo Bot:** Tự động gửi tin nhắn nhắc nhở/xác nhận qua NetChat tới từng nhân viên.
*   **Điểm danh thực tế:** Tab "Tham gia" hiển thị danh sách người ăn thực tế được đồng bộ qua API từ hệ thống điểm danh bên ngoài.

### 3. Quản lý Thực đơn & Món ăn
*   **Kho món ăn:** Quản lý chi tiết món ăn (loại món, hình ảnh, mô tả).
*   **Công thức & Nguyên liệu:** Khai báo định mức nguyên liệu chi tiết cho từng món ăn để tự động tính toán khối lượng cần mua dựa trên số người đăng ký.
*   **AI Menu Suggestion:** AI gợi ý thực đơn 5 ngày trong tuần dựa trên các tiêu chí cân bằng dinh dưỡng và sự đa dạng.
*   **Quy trình phê duyệt:** Thực đơn và món ăn mới do bếp trưởng tạo sẽ được Admin phê duyệt trước khi hiển thị.

### 4. Quản lý Kho & Tài chính
*   **Đặt hàng (Purchase):** Tạo đơn hàng nguyên liệu chính và đơn hàng phụ (gia vị, dầu ăn...).
*   **Quản lý Chi phí:** Ghi nhận và phân loại mọi chi phí phát sinh, hỗ trợ quy trình phê duyệt chi phí minh bạch.
*   **Cấu hình giá:** Linh hoạt thiết lập giá suất ăn theo biến động thị trường.

### 5. Hệ thống & Profile
*   **Phân quyền (RBAC):** Phân chia vai trò rõ ràng giữa Admin, Nhân viên bếp và Người ăn.
*   **Đăng nhập OTP:** Người dùng đăng nhập bằng mã OTP nhận qua NetChat (thay cho mật khẩu).
*   **Cấu hình runtime trong Profile Admin:** Bot NetChat (URL/Token), AI Gemini (model + API key), và mẫu tin nhắn OTP/đặt cơm.

## 🛠 Công nghệ sử dụng
*   **Backend:** Python 3.12, Django 5.x
*   **Database:** PostgreSQL
*   **Frontend:** HTML5, CSS3 (Vanilla + Bootstrap 5), JavaScript (ES6+)
*   **AI Integration:** Google Generative AI (Gemini Pro)
*   **Deployment:** Ubuntu Server, Nginx, Gunicorn
*   **Communication:** NetChat API (Mattermost compatible)

## 📂 Cấu trúc thư mục
```text
├── accounts/          # Quản lý người dùng, profile và phân quyền
├── core/              # Các tính năng lõi, Dashboard và AI services
├── meals/             # Quản lý thực đơn, món ăn và định mức
├── finance/           # Quản lý thu chi, hóa đơn và giá suất ăn
├── registrations/     # Quản lý đăng ký và tham gia thực tế
├── reviews/           # Hệ thống đánh giá công khai qua QR Code
├── templates/         # Giao diện người dùng (HTML Templates)
├── static/            # Files tĩnh (CSS, JS, Images)
└── media/             # Lưu trữ hình ảnh món ăn, avatar
```

## 🚀 Cài đặt & Chạy thử

1. **Clone dự án:**
   ```bash
   git clone https://github.com/Thanghv37/bep-an.git
   cd bep-an
   ```

2. **Cài đặt môi trường ảo & Thư viện:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Cấu hình Database:**
   Chỉnh sửa thông số DATABASE trong `config/settings.py` cho phù hợp với PostgreSQL của bạn.

4. **Migrate & Chạy server:**
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## 📝 Nhật ký thay đổi

### 2026-05-13
- **Bảo mật**: tách `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` ra env var (TODO #3 + #4). [config/settings.py](config/settings.py) giờ đọc từ `SECRET_KEY` / `DJANGO_DEBUG` / `DJANGO_ALLOWED_HOSTS`. Default an toàn cho prod: `DEBUG=False`, `ALLOWED_HOSTS=[]` (Django sẽ chặn nếu chưa set env). Dev không set env thì DEBUG=False mặc định; muốn xem trace phải `DJANGO_DEBUG=True` trong `.env`. Khi DEBUG=True và `DJANGO_ALLOWED_HOSTS` rỗng, fallback `localhost,127.0.0.1` để dev khỏi 400. Trên prod cần set 3 env mới trong systemd service.
- [.env.example](.env.example): thêm 3 biến mới `SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` với hướng dẫn generate key + ví dụ giá trị prod.
- [config/settings.py](config/settings.py): commit `CSRF_TRUSTED_ORIGINS` vào repo (trước đây là chỉnh tay trực tiếp trên server, gây conflict khi pull). Giá trị giống y bản server đang chạy: `https://net2kitchen.viettel.pro.vn` + `http://...`.
- **Đã deploy + verify trên prod**: service `bep-an` chạy OK sau khi set `SECRET_KEY` + `DJANGO_DEBUG=False` + `DJANGO_ALLOWED_HOSTS` trong systemd. Verify: (1) URL sai → trang 404 ngắn gọn không lộ stack trace; (2) request qua IP (sai host) → 400 Bad Request. Session user cũ bị invalidate do `SECRET_KEY` đổi (expected).
- [DEPLOY.md](DEPLOY.md): cập nhật danh sách env var trên server (thêm 3 biến mới) + ví dụ block `[Service]` đầy đủ.
- [TODO.md](TODO.md): đóng mục #3 và #4 bảo mật. Nhóm bảo mật còn lại 2 mục: #1 (đổi DB password), #2 (revoke Gemini API key — đặc biệt cần vì key vừa lộ thêm 1 lần trong session deploy hôm nay).
- **Bảo mật cookies**: thêm `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` (auto theo DEBUG), `*_HTTPONLY=True`, `*_SAMESITE='Lax'` và `SECURE_PROXY_SSL_HEADER` vào [config/settings.py](config/settings.py). Chặn XSS steal cookie + đảm bảo cookie chỉ gửi qua HTTPS trên prod. Đã verify Nginx Proxy Manager (container Docker terminate HTTPS) có gửi header `X-Forwarded-Proto` → Django nhận biết HTTPS đúng cách. Đã deploy + verify trên prod: cookie `sessionid` và `csrftoken` đều có flag Secure + HttpOnly + SameSite=Lax. Fix BLOCKER #2 trong audit prod-readiness 2026-05-13.
- **OTP brute-force protection + UX "Gửi lại mã"** (fix BLOCKER #1 audit): thêm 3 field vào [UserProfile](accounts/models.py) (`otp_failed_attempts`, `otp_locked_until`, `otp_last_sent_at`) + 4 helper method. Quy tắc: (1) verify sai 10 lần → khoá 15 phút; (2) khi đang khoá, request/resend OTP đều KHÔNG gửi tin NetChat mới (tránh spam) — chỉ redirect tới trang verify để user thấy countdown mở khoá; (3) min 60s giữa 2 lần request/resend; (4) verify thành công → reset attempts. Refactor logic gửi OTP ra helper `_send_otp_netchat()` dùng chung cho request và resend. Thêm view + URL [resend_otp](accounts/views.py) (`/accounts/resend-otp/`). UI: [otp_verify.html](templates/registration/otp_verify.html) thêm nút "Gửi lại mã" với countdown 60s, banner lock với countdown đến giờ mở khoá (auto reload page khi hết khoá), thông báo "còn N lần thử" khi sai mã. Migration mới `0008_userprofile_otp_failed_attempts_and_more`.
- **UX "Gửi tin nhắn báo cơm"**: nút giữ disable + spinner "Đang gửi (N người) - còn M:SS" trong suốt thời gian background thread chạy (ước tính `ceil(N/15) * 75s + 15s buffer` theo throttle 15 tin/phút của [_send_notifications_bg](registrations/views.py)). Tránh user spam-click queue thêm batch trùng. Khi hết countdown → tự enable lại. [registrations/registration_list.html](templates/registrations/registration_list.html) refactor JS handler.
- **Format ngày trong tin báo cơm**: ngày trong message giờ hiển thị `13-05-2026` thay vì `2026-05-13`. Sửa ở [_send_notifications_bg](registrations/views.py) — parse target_date ISO từ frontend rồi format `%d-%m-%Y` trước khi pass vào `render_template`. Template `{target_date}` vẫn giữ nguyên (không cần đổi cấu hình SystemConfig).
- **Thêm biến `{meal_count}` cho tin báo cơm**: hiển thị số lượng suất ăn (lấy từ `MealRegistration.quantity`), zero-pad 2 chữ số (`01`, `02`, … `12`). Cập nhật [core/message_templates.py](core/message_templates.py): thêm vào `VARS_MEAL` (xuất hiện trong UI cấu hình Profile admin) + sửa `DEFAULT_MEAL`. Sửa [_send_notifications_bg](registrations/views.py) pass thêm `meal_count` vào render_template. ⚠️ Template hiện tại của admin nằm trong DB (`SystemConfig`) sẽ KHÔNG tự đổi — admin cần vào trang Profile để chèn `{meal_count}` vào template hiện có.

### 2026-05-12
- Trang Login mobile: thêm "mobile-brand" banner trên cùng (🍱 + "Net2Kitchen" + subtitle) chỉ hiện ở màn hình ≤900px — fix vấn đề user mở trang trên điện thoại không biết đang đăng nhập phần mềm gì (panel trái với ảnh nền bị ẩn trên mobile). Đồng bộ branding panel trái sang "Net2Kitchen" / "© Ban CĐS – TTKTKV2".
- Sidebar branding: đổi "Hệ thống quản lí bếp ăn" → **"Net2Kitchen"** (text gradient cyan→green), subtitle "@ CĐS Team - KV2" → "© Ban CĐS – TTKTKV2". Refactor brand-box thành layout flex (emoji + text) cho gọn; cập nhật CSS sidebar collapsed mode để show đúng emoji thật thay vì `::before`.
- DEPLOY.md: nâng bước "Apply migration" thành quy tắc bắt buộc chạy MỖI lần deploy (kể cả khi nghĩ schema không đổi) — sau sự cố production lỗi `ProgrammingError: column meals_weeklymenudraft.status does not exist` do migration commit trước chưa apply trên server.
- **Bắt buộc duyệt với mọi role (kể cả admin)** để double-check tránh sai sót. Trước đây: admin tạo `Dish` auto-approve ngay; admin tạo/sửa `DailyMenu` có thể chọn `STATUS_APPROVED` thẳng trong dropdown form → bypass bước duyệt. Sau fix: (1) `dish_create`/`dish_update` luôn set status=PENDING bất kể role; (2) `DailyMenuForm` disable field `status` cho mọi role, `menu_create`/`menu_update` luôn force PENDING. Admin muốn duyệt phải dùng action "Phê duyệt" tách riêng. Đơn mua bổ sung và chi phí mua đã PENDING cho mọi role từ trước — không cần đổi.
- Fix bug menu bị từ chối: khi user (đặc biệt là admin) chỉnh sửa menu đã REJECTED và bấm "Cập nhật thực đơn", status vẫn giữ `rejected` (ô lịch vẫn đỏ). Nguyên nhân: với admin, code đọc `form.cleaned_data['status']` mà form initial inherit từ instance = rejected → không change → save lại rejected. Sửa: bắt `was_rejected` ngay đầu view trước khi form __init__, nếu trước đó là REJECTED thì luôn force PENDING khi resubmit (bất kể role). Áp dụng cho cả `menu_create` và `menu_update`.
- Refactor workflow "Gợi ý AI tuần sau": tách 2 trạng thái rõ ràng cho `WeeklyMenuDraft` (migration 0014). (1) **`suggested`** — sau khi bấm "AI gợi ý", chỉ hiện preview cards, lịch tháng vẫn trắng. (2) **`applied`** — sau khi bấm "Áp dụng gợi ý", lịch tháng đổi xanh dương, day detail pre-tick các món, KHÔNG tạo `DailyMenu` ngay. (3) User vào day detail tinh chỉnh + bấm "Lưu thực đơn" → mới tạo `DailyMenu` PENDING (xanh lá, chờ phê duyệt), draft tự xóa. (4) Admin duyệt → APPROVED. Fix kèm bug `name 'json' is not defined` trong `apply_week_menu_draft` do thiếu `import json`.
- UI nút "Gợi ý thực đơn" đổi thành "AI gợi ý" với pill viền gradient cyan→green→amber + icon `bi-stars`, nền trắng — phù hợp với phong cách "AI button" hiện đại.
- Trang "Lên thực đơn": gợi ý AI tuần sau giờ persist qua reload trang. Khi `WeeklyMenuDraft` được tạo trong ngày hôm nay vẫn nằm DB, view load lại + đẩy xuống template, JS render preview giống lúc bấm "Gợi ý". Bấm "Gợi ý thực đơn" sẽ overwrite (xóa draft cũ + tạo mới — logic này đã có sẵn). Sau nửa đêm filter `created_at__date=today` không match → tự động không hiển thị. Tiết kiệm quota AI Gemini.
- Cập nhật `AVAILABLE_MODELS` trong [core/ai_config.py](core/ai_config.py): bỏ các model đã deprecated (1.5-pro, 1.5-flash, 2.0-flash, 2.0-flash-exp), thêm model hiện hành theo AI Studio (3.1-pro, 3.1-flash-lite, 3-flash, 2.5-pro, 2.5-flash, 2.5-flash-lite). Lưu ý: `*-pro` cần tài khoản trả phí — free tier quota = 0.
- Trang Tham gia: dịch nhãn trạng thái sang tiếng Việt (`valid → Đã điểm danh`, `not_registered → Chưa đăng ký`) và **bổ sung nhóm "Chưa điểm danh"** (đỏ) — những người có trong `MealRegistration` ngày đó nhưng chưa có lần quét nào trong `AttendanceLog`. Filter trạng thái thêm option mới `not_attended`. View refactor sang dùng `rows` (struct thống nhất từ 2 nguồn) thay vì `logs` (chỉ AttendanceLog).
- UI dọn topbar: xóa badge "Nội bộ" góc phải (không có ý nghĩa thông tin), giảm `content-wrap` padding-top từ 28px → 12px để nội dung sát topbar hơn, đỡ khoảng trống thừa ở đầu mỗi trang.
- Fix ảnh static không hiển thị trên server (login background, default avatar): thêm URL pattern serve `/static/` qua `django.views.static.serve` trong [config/urls.py](config/urls.py) (mirror cách media đang serve). Lý do: gunicorn không tự serve static như `runserver` ở dev, kể cả khi `DEBUG=True`. Thêm file `static/images/default-avatar.png` (trước đây lạc trong `media/user_avatars/`).
- Fix `attendance_log_api`: nếu cùng ngày & cùng `employee_code` đã có record nhưng **trạng thái khác** (vd quét lần 1 `not_registered`, đăng ký bù xong quét lần 2 `valid`) → cập nhật record cũ (status + scan_time + full_name) thay vì bỏ qua. Cùng trạng thái vẫn skip để giữ dedup. Trả thêm field `updated` trong response.
- Tăng gunicorn `--workers 3 → 5`, thêm `--timeout 120` (mặc định 30s không đủ cho Gemini AI call). Fix bug: worker đang gọi AI menu suggestion bị master kill SIGKILL sau 30s → connection của request khác đứng cùng worker bị reset → người dùng thấy "Internal Server Error", F5 lại OK.
- **Gỡ bỏ tính năng thu thập góp ý qua DM NetChat** (`FeedbackMessage` / `poll_feedback`). Lý do: bot bị NetChat soft-suspend lúc 9:30 do `poll_feedback` gọi 44+ API call/phút sau khi bot tự broadcast tin đặt cơm. Phương án sửa root-cause (per-channel cursor / webhook) phức tạp; user quyết định tắt hẳn, bắt buộc góp ý qua web. Xóa: `reviews/feedback_poller.py`, `reviews/management/commands/poll_feedback.py`, model `FeedbackMessage` (migration `0005_delete_feedbackmessage`), cột "Đánh giá từ NetChat" trong trang đánh giá. Trên server: dừng + disable + xóa `poll-feedback.timer/.service` (xem [DEPLOY.md](DEPLOY.md)).
- (Sửa trước khi quyết tắt) Throttle `poll_feedback` lên 1.2s/call và abort khi 429 — code này đã được xóa cùng feature.

### 2026-05-11
- Dashboard: ẩn badge "Đã đăng kí / Chưa đăng kí" ở các thẻ ngày trong tuần khi đăng nhập bằng tài khoản superuser (admin Django) — dùng cho màn hình TV ở bếp ăn (tài khoản này không bao giờ đăng ký ăn).
- Trang Tham gia (`registration_participation`): cột "Người dùng" hiển thị tên thực (lookup `UserProfile` theo `employee_code`, fallback `log.full_name` rồi đến mã NV) kèm avatar; header cột thêm badge "Tổng: N" (đếm distinct nhân viên sau filter); filter Trạng thái đổi label/value sang `valid` / `not_registered` cho khớp dữ liệu API; ô tìm kiếm giờ match cả tên và mã NV.
- Thu thập tin nhắn góp ý DM bot NetChat: model `FeedbackMessage`, polling service + management command `poll_feedback` (cron 30 phút qua systemd timer), hiển thị tích hợp ngay trong section "Tổng hợp đánh giá" của trang đánh giá (chia 2 cột website / NetChat). Tin cùng người cùng ngày được gộp 1 dòng cách nhau bằng " / " (dùng `StringAgg` PostgreSQL).
- UI tinh chỉnh: trang Danh sách đăng kí gộp filter + Log gửi tin trên cùng 1 hàng (9/3); trang Đánh giá hiển thị compact `MNV - Tên: nội dung` 1 dòng, MNV màu xanh.
- Fix: template `{{` đầu dòng → raw text; `});` rác cuối menu_list; crash `VariableDoesNotExist` khi `profile=None` (đăng ký có mã NV chưa có user).
- Tạo [DEPLOY.md](DEPLOY.md) — quy trình deploy chuẩn, troubleshooting, danh sách env var trên server.

### 2026-05-10
- Thu thập góp ý qua tin nhắn DM NetChat: thêm model `FeedbackMessage` + service [reviews/feedback_poller.py](reviews/feedback_poller.py) + management command `poll_feedback`. Trang `/reviews/feedback/` hiển thị bảng tổng hợp (filter theo ngày, search), link từ trang đánh giá. Cần setup systemd timer trên server để chạy định kỳ — xem [TODO.md](TODO.md) hoặc hướng dẫn deploy.
- Tách `DB_PASSWORD` ra biến môi trường (`python-dotenv` + file `.env` gitignored). Deploy giờ chỉ cần `git pull + restart`, không còn conflict do secrets khác nhau giữa dev và prod.
- Cấu hình runtime trong Profile admin: BOT NetChat, AI Gemini (model + API key), mẫu tin nhắn OTP / đặt cơm. Đổi config có hiệu lực ngay không cần restart server.
- Đăng nhập chuyển hoàn toàn sang OTP qua NetChat, gỡ các view password cũ. Form thêm user: dropdown gợi ý đơn vị / phòng ban / chức vụ từ DB.
- Phân quyền: ẩn "Xuất báo cáo Excel" với người ăn (chỉ admin + nhân viên bếp).
- Tinh chỉnh CSS responsive cho mobile (4 trang chính: Dashboard / Đánh giá / Báo cáo / Profile).

---

## 📧 Liên hệ
*   **Người phát triển:** Thanghv37
*   **Đơn vị:** VT NET KV2

---
*Dự án được phát triển nhằm mục đích nâng cao chất lượng bữa ăn và tối ưu hóa quản trị nội bộ.*