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

## 📧 Liên hệ
*   **Người phát triển:** Thanghv37
*   **Đơn vị:** VT NET KV2

---
*Dự án được phát triển nhằm mục đích nâng cao chất lượng bữa ăn và tối ưu hóa quản trị nội bộ.*