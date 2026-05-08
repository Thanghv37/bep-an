README.md — HỆ THỐNG QUẢN LÝ BẾP ĂN CÔNG TY
1. GIỚI THIỆU HỆ THỐNG

Đây là hệ thống quản lý bếp ăn nội bộ công ty được xây dựng bằng:

Backend: Django
Database: PostgreSQL
Frontend: Django Template + Bootstrap
Server: Ubuntu + Gunicorn + Nginx

Mục tiêu hệ thống:

Quản lý đăng ký suất ăn
Quản lý tham gia thực tế
Quản lý món ăn
Quản lý nguyên vật liệu
Quản lý kho
Quản lý thu chi
Dashboard thống kê realtime
Gửi thông báo tự động qua NetChat Bot
2. KIẾN TRÚC HỆ THỐNG
Backend
Django
Django ORM
Pandas (import Excel)
Requests (gọi API NetChat)
Frontend
Bootstrap 5
Chart.js
Django Template
Database
PostgreSQL
Deploy
Gunicorn
Nginx
Ubuntu Server
3. CÁC MODULE CHÍNH
3.1. MODULE NHÂN VIÊN (EMPLOYEE)

Lưu thông tin nhân viên công ty.

Bảng:

Employee

Fields:
Field	Ý nghĩa
employee_code	Mã nhân viên (PK)
full_name	Họ tên
email	Email
phone	SĐT
department	Phòng ban
user_id	User ID NetChat
is_active	Trạng thái hoạt động
Vai trò:
Mapping đăng ký ăn
Mapping NetChat user
Quản lý nhân sự
3.2. MODULE ĐĂNG KÝ SUẤT ĂN (REGISTRATION)

Nhân sự import danh sách đăng ký ăn.

Bảng:

Registration

Fields:
Field	Ý nghĩa
employee	FK → Employee
date	Ngày đăng ký
meal_type	Loại bữa
status	Đã đăng ký / Chưa đăng ký
created_at	Thời gian tạo
3.3. IMPORT EXCEL ĐĂNG KÝ ĂN
File Excel mẫu:
employee_code	full_name	status	meal_type
123456	Nguyễn Văn A	Đã đăng ký	Trưa
Quy trình:
Upload Excel
Pandas đọc file
employee_code → mapping Employee
Tạo Registration
3.4. MODULE THAM GIA THỰC TẾ (PARTICIPATION)

Theo dõi nhân viên thực tế vào ăn.

Nguồn dữ liệu:
Máy quét QR
Máy chấm công
Import log
Bảng:

Participation

Fields:
Field	Ý nghĩa
employee	FK Employee
scan_time	Thời gian quét
status	Đã đăng ký / Chưa đăng ký
type	QR / Máy chấm công
3.5. MODULE THỰC ĐƠN (MENU)

Quản lý menu theo ngày.

Bảng:

Menu

Fields:
Field	Ý nghĩa
date	Ngày
meal_type	Trưa / Tối
note	Ghi chú
3.6. MODULE MÓN ĂN (DISH)

Khai báo món ăn.

Bảng:

Dish

Fields:
Field	Ý nghĩa
name	Tên món
category	Loại món
estimated_cost	Giá thành dự kiến
description	Mô tả
3.7. MODULE NGUYÊN LIỆU (INGREDIENT)

Quản lý nguyên vật liệu.

Bảng:

Ingredient

Fields:
Field	Ý nghĩa
name	Tên nguyên liệu
unit	Đơn vị tính
stock_quantity	Tồn kho
unit_price	Giá nhập
3.8. MODULE MUA HÀNG (PURCHASE)

Quản lý nhập nguyên liệu.

Bảng:

Purchase

Fields:
Field	Ý nghĩa
supplier	Nhà cung cấp
purchase_date	Ngày mua
type	Nguyên liệu chính / Bổ sung
total_amount	Tổng tiền
status	Chờ duyệt / Đã duyệt
3.9. MODULE KHO (INVENTORY)

Theo dõi tồn kho.

Bảng:

InventoryTransaction

Fields:
Field	Ý nghĩa
ingredient	FK Ingredient
transaction_type	Nhập / Xuất
quantity	Số lượng
created_at	Thời gian
3.10. MODULE THU CHI (FINANCE)

Quản lý tài chính bếp ăn.

Bảng:

Expense

Fields:
Field	Ý nghĩa
category	Loại chi
amount	Số tiền
expense_date	Ngày
note	Ghi chú
Ví dụ:
Mua thực phẩm
Gas
Điện
Nước
3.11. MODULE DASHBOARD

Dashboard realtime.

Hiển thị:
Tổng đăng ký hôm nay
Tổng tham gia thực tế
Tổng chi phí hôm nay
Tồn kho
Biểu đồ suất ăn
Biểu đồ:
Theo ngày
Theo tháng
Theo phòng ban
3.12. MODULE BOT NETCHAT

Gửi thông báo tự động.

Bảng:

BotConfig

Fields:
Field	Ý nghĩa
bot_url	URL NetChat
bot_token	Token Bot
default_channel	User test
4. PHÂN QUYỀN
Admin
Toàn quyền
Nhân viên bếp
Quản lý món ăn
Quản lý nguyên liệu
Tạo phiếu mua
Nhân sự
Import đăng ký
Gửi bot
Nhân viên
Đăng ký ăn
Tóm lại: Trang dashboard sẽ hiển thị giao diện chính cho người ăn, gồm menu trong tuần, thu chi của ngày đó, chart thu chi trong tuần và 1 box AI liên kết gemini AI nhằm phân tích calo của ngày hôm đó. Trang quản lí người dùng để admin quản lí toàn bộ danh sách nhân viên trong công ty và Role của mỗi người. Trang danh sách đăng kí sẽ được import bằng tay mỗi ngày danh sách của người đăng kí ăn hôm đó, và có nút gửi tin nhắn thông qua bot NETCHAT tới các người đăng kí, và trong trang danh sách đăng kí có tab "tham gia" đây là tab hiển thị các người ăn thực tế hôm nay, được lấy từ API POST của 1 hệ thống điểm danh khác. Trang danh mục món ăn để cho nhân viên bếp khai báo các món ăn có sẵn của nhà bếp, khai báo mỗi món sẽ có các thông tin: loại món ( chính, phụ, canh, tráng miệng ), up ảnh món đó lên để hiển thị ở dashboard, và khai báo nguyên liệu khẩu phần / người chi tiết món ăn đó. Mục đích là từ danh sách người đăng kí ăn nhân lên với khẩu phần sẽ suy ra được nguyên liệu cần đặt mua. Trang lên thực đơn là để cho nhân viên khai báo thực đơn của mỗi ngày. Đặc biệt ở đây sẽ có 1 AI để gợi ý lên thực đơn cho 5 ngày của tuần sau ( trừ thứ 7, chủ nhật), hiện tại chức năng này đang demo bằng code. Sau khi nhân viên khai báo món ăn hay là chọn món đều đợi phê duyệt của admin ở trang phê duyệt. nguyên liệu chính để nấu các món ăn thì đã được hiển thị lúc tạo thực đơn rồi, còn những nguyên liệu mua bổ sung ( ví dụ gia vị mắm muối, dầu ăn ... ) thì sẽ được khai trong trang hóa đơn đặt hàng, ở mục 'tạo đơn hàng phụ'. toàn bộ chi phí của mua các nguyên liệu chính hoặc là mua đơn hàng bổ sung thì sẽ được nhân viên nhập ở trang chi phí và đợi admin phê duyệt. các chi phí chờ phê duyệt/đã phê duyệt sẽ được hiển thị lại trong list ở hóa đơn đặt hàng. Trang báo cáo để vẽ chart báo cáo thu - chi - chênh lệch của tuần / tháng / năm. và hiển thị chi tiết thu - chi của các ngày trong tháng . Và do thị trường biến đổi liên tục nên giá ăn cũng vậy, trang cấu hình giá là nơi để admin thiết lập giá ăn mà mọi người phải nộp, số tiền nộp x số người đăng kí = thu của ngày hôm đó. cuối cùng là user profile, nơi đây hiển thị profile, và đối với admin sẽ hiển thị thêm mục cấu hình bot, phục vụ cho việc gửi tin nhắn khi mọi người đăng kí ăn