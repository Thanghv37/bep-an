# 🤖 Hướng dẫn: Tạo BOT gửi tin nhắn & Đăng nhập bằng mã OTP

Tài liệu dành cho đồng nghiệp vận hành hệ thống **Net2Kitchen** (Quản lý Bếp ăn KV2 - VT NET).

Hệ thống dùng **BOT NetChat** (nền tảng tương thích Mattermost) để:
- Gửi tin nhắn nhắc/xác nhận đặt cơm tới từng nhân viên.
- Gửi **mã OTP** để nhân viên đăng nhập (không cần mật khẩu).

> ⚠️ Việc **cấu hình BOT** chỉ làm 1 lần và phải do **tài khoản Admin** thực hiện. Việc **đăng nhập bằng OTP** thì mọi nhân viên đều làm.

---

## PHẦN 1 — TẠO BOT GỬI TIN NHẮN (dành cho Admin)

Hệ thống không tự tạo BOT trên NetChat. Bạn cần tạo BOT trong NetChat trước, lấy **Token**, rồi dán vào phần cấu hình trong web.

### Bước 1: Tạo BOT trên NetChat

1. Đăng nhập NetChat bằng tài khoản **có quyền quản trị (System Admin)**.
2. Vào **System Console** → mục **Integrations** → **Bot Accounts**.
   - Nếu chưa thấy mục này: vào **System Console → Integration Management** và bật **Enable Bot Account Creation** = `true`.
3. Bấm **Add Bot Account** và điền:
   - **Username**: ví dụ `bep-an-bot` (tên gợi nhớ).
   - **Display Name**: ví dụ `BOT Bếp ăn`.
   - **Role**: để **Member** là đủ.
4. Bấm **Create Bot Account**.
5. Màn hình sẽ hiện ra **Token** (chuỗi dài dạng `xxxxxxxxxxxxxxxxxxxxxxxxxx`).
   - 👉 **Copy và lưu Token này ngay** — NetChat chỉ hiện 1 lần duy nhất. Nếu lỡ mất phải tạo lại token mới.

> 💡 **Lưu ý quan trọng để BOT nhắn được cho nhân viên:**
> BOT gửi tin theo cách tìm nhân viên bằng **username NetChat = phần trước dấu @ của email**.
> Ví dụ email `nguyenvana@viettel.com.vn` → username NetChat phải là `nguyenvana`.
> Nhân viên **phải đã từng đăng nhập NetChat ít nhất 1 lần** thì BOT mới tìm thấy và nhắn được.

### Bước 2: Lấy địa chỉ (URL) của NetChat

Đây là địa chỉ máy chủ NetChat của công ty, **không có dấu `/` ở cuối**.
- Ví dụ: `https://chat.congty.vn` hoặc địa chỉ NetChat nội bộ Viettel đang dùng.

### Bước 3: Nhập cấu hình BOT vào web

1. Đăng nhập web Net2Kitchen bằng tài khoản **Admin**.
2. Vào **Trang cá nhân (Profile)** → khối **🤖 Cấu hình BOT NetChat** (cột bên trái).
3. Điền 2 ô:
   - **URL NetChat**: dán địa chỉ ở Bước 2 (vd `https://chat.congty.vn`).
   - **BOT Token**: dán Token ở Bước 1.
4. Bấm nút **Kiểm tra** (Verify) để thử kết nối.
   - ✅ Thành công: hiện dòng `Xác minh thành công! Tên Bot: ...`.
   - ❌ Thất bại: kiểm tra lại URL (đúng `https://`, không thừa `/`) và Token (copy đủ, không dính khoảng trắng).
5. Khi đã xác minh OK, bấm **Lưu**.

> 🔁 Muốn đổi BOT/Token sau này: bấm nút **Sửa** để mở khoá 2 ô, nhập lại rồi **Kiểm tra** → **Lưu**.

### Bước 4 (tuỳ chọn): Chỉnh nội dung tin nhắn

Trong cùng trang Profile có khối **🔒 Cấu hình tin nhắn gửi OTP** (và mẫu tin đặt cơm).
- Bạn có thể sửa lời văn của tin nhắn.
- Bấm vào các **biến** (vd `{otp_code}`, `{full_name}`, `{employee_code}`) để chèn — hệ thống sẽ tự thay bằng dữ liệu thật khi gửi.
- ⚠️ **Bắt buộc giữ biến `{otp_code}`** trong mẫu tin OTP, nếu không nhân viên sẽ không thấy mã.

✅ **Hoàn tất.** Sau bước này, hệ thống đã có thể tự gửi OTP và các thông báo qua BOT.

---

## PHẦN 2 — ĐĂNG NHẬP BẰNG MÃ OTP (dành cho mọi nhân viên)

Nhân viên đăng nhập **không cần mật khẩu**. Hệ thống gửi mã 6 số qua NetChat.

### Điều kiện bắt buộc
- Đã được Admin tạo tài khoản (có **Mã nhân viên** và **Email** trong hệ thống).
- Đã **đăng nhập NetChat** trên máy tính hoặc điện thoại (để nhận tin từ BOT).

### Cách đăng nhập

1. Mở trang đăng nhập web Net2Kitchen.
2. Nhập **Mã nhân viên** của bạn.
3. Bấm **NHẬN MÃ OTP QUA NETCHAT**.
4. Mở ứng dụng **NetChat** → BOT sẽ nhắn cho bạn một **mã 6 số**.
5. Quay lại web, nhập mã 6 số vào ô, bấm **XÁC NHẬN ĐĂNG NHẬP**.

### Những điều cần biết về mã OTP

| Tình huống | Quy định |
|---|---|
| ⏱️ Mã có hiệu lực | **10 phút** kể từ lúc gửi, dùng 1 lần. |
| 🔁 Bấm "Gửi lại mã" | Phải đợi **60 giây** giữa 2 lần gửi. |
| ❌ Nhập sai nhiều lần | Sai quá **10 lần** → tài khoản bị **khoá tạm 15 phút**, màn hình hiện đồng hồ đếm ngược. |
| 🆕 Mỗi lần xin mã mới | Mã cũ tự **hết hiệu lực** — luôn dùng mã mới nhất vừa nhận. |

### Không nhận được mã? Kiểm tra theo thứ tự:
1. **Đã đăng nhập NetChat chưa?** BOT chỉ nhắn được khi bạn đang có tài khoản NetChat hoạt động.
2. **Email trên hệ thống có đúng không?** Username NetChat (phần trước @) phải khớp. Nhờ Admin kiểm tra.
3. **Đợi vài giây** rồi xem lại NetChat; nếu vẫn không có, bấm **Gửi lại mã** (sau 60s).
4. Nếu màn hình báo *"Hệ thống chưa cấu hình BOT"* → báo **Admin** làm lại **Phần 1**.
5. Nếu báo *"Không thể gửi tin nhắn qua NetChat"* → thường do bạn **chưa từng đăng nhập NetChat**. Hãy đăng nhập NetChat một lần rồi thử lại.

---

## ❓ Hỏi nhanh

- **BOT có cần để mở 24/7 không?** Không. BOT chạy trên máy chủ NetChat; web chỉ gọi tới nó khi cần gửi tin.
- **Token bị lộ thì sao?** Vào NetChat tạo lại token mới cho BOT → cập nhật lại trong Profile (nút **Sửa** → **Lưu**). Token cũ nên vô hiệu hoá.
- **Một BOT dùng cho cả OTP và tin đặt cơm chứ?** Đúng, chỉ cần cấu hình 1 BOT duy nhất.

---

*Mọi vướng mắc liên hệ quản trị viên hệ thống Net2Kitchen.*
