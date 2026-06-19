# SalesPro SaaS — Hướng dẫn triển khai hoàn chỉnh

## Kiến trúc hệ thống

```
[Trình duyệt KH] ──HTTPS──► [Render.com Server]
                                   │
                            ┌──────┴──────┐
                            │  FastAPI    │  ← backend/
                            │  Python     │
                            └──────┬──────┘
                                   │
                            ┌──────┴──────┐
                            │  SQLite DB  │  ← /data/salespro.db
                            │  (file)     │
                            └─────────────┘
```

**Mỗi cửa hàng** có:
- `slug` riêng (VD: `cafe-abc`) → URL: `https://your-app.onrender.com/shop/cafe-abc`
- Database row riêng, hoàn toàn cách ly
- Tài khoản admin + nhân viên riêng
- Dữ liệu: sản phẩm, khách hàng, đơn hàng, kho không bao giờ lẫn nhau

---

## BƯỚC 1 — Chạy thử local (máy tính của bạn)

### Yêu cầu: Python 3.11+

```bash
# 1. Vào thư mục backend
cd backend

# 2. Cài thư viện
pip install -r requirements.txt

# 3. Chạy server
python main.py
# → Server chạy tại http://localhost:8000
# → API docs tại http://localhost:8000/docs

# 4. Mở frontend
# Copy file frontend/index.html vào thư mục gốc rồi mở Chrome
# HOẶC dùng Live Server extension trong VSCode
```

**Tài khoản demo đã tạo sẵn:**
- Shop slug: `demo`
- Username: `admin` / Password: `admin123`
- Username: `quanly` / Password: `ql2026`
- Username: `thungan` / Password: `tn2026`

---

## BƯỚC 2 — Deploy lên Render.com (miễn phí)

### 2.1 Chuẩn bị GitHub repo

```bash
# Tạo repo mới trên github.com, rồi:
git init
git add .
git commit -m "SalesPro SaaS v2.0"
git remote add origin https://github.com/YOUR_USERNAME/salespro-saas.git
git push -u origin main
```

### 2.2 Tạo Web Service trên Render

1. Vào https://render.com → **New** → **Web Service**
2. Kết nối GitHub repo vừa tạo
3. Cài đặt:
   - **Name**: `salespro-saas`
   - **Region**: `Singapore` (gần VN nhất)
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables** → Add:
   - `DB_PATH` = `/opt/render/project/data/salespro.db`

### 2.3 Thêm Persistent Disk (quan trọng!)

> Render free tier không có persistent disk → **dữ liệu mất khi deploy lại**
>
> ⚠️ Nâng lên **Starter plan ($7/tháng)** để có disk và server luôn chạy

- Vào service → **Disks** → **Add Disk**
- Mount Path: `/opt/render/project/data`
- Size: 1GB

### 2.4 Deploy

Click **Create Web Service** → Chờ 3-5 phút build xong.

URL của bạn: `https://salespro-saas.onrender.com`

---

## BƯỚC 3 — Cấu hình Frontend kết nối server

Mở file `frontend/index.html`, tìm dòng:
```javascript
const API_BASE = window.location.hostname === 'localhost'
  ? 'http://localhost:8000/api' : '/api';
```

**Nếu frontend và backend cùng domain** (Render serve cả 2): giữ nguyên `/api`

**Nếu frontend ở Netlify, backend ở Render**: đổi thành:
```javascript
const API_BASE = 'https://salespro-saas.onrender.com/api';
```

---

## BƯỚC 4 — Đăng ký cửa hàng mới cho khách

### Cách 1 — API (bạn tạo cho khách)
```bash
curl -X POST https://your-app.onrender.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "shop_name": "Cà phê Hoa",
    "owner_name": "Trần Thị Hoa",
    "email": "hoa@gmail.com",
    "phone": "0901234567",
    "address": "123 ABC, Q1, TP.HCM",
    "password": "matkhau123"
  }'
```

**Response:**
```json
{
  "success": true,
  "shop_slug": "ca-phe-hoa",
  "message": "✅ Đăng ký thành công!",
  "login_info": {
    "shop_slug": "ca-phe-hoa",
    "username": "admin",
    "password": "matkhau123"
  }
}
```

### Cách 2 — Trang đăng ký tự phục vụ
Thêm form đăng ký vào frontend để khách tự đăng ký (tôi có thể build thêm).

### Cách 3 — Swagger UI
Vào `https://your-app.onrender.com/docs` → dùng API `POST /auth/register`

---

## BƯỚC 5 — Khách hàng đăng nhập

Khách mở `index.html` (hoặc link web), nhập:
- **Shop slug**: `ca-phe-hoa` (bạn cung cấp)
- **Username**: `admin`
- **Password**: `matkhau123`

Sau đó khách đổi mật khẩu trong Cài đặt.

---

## Quản lý nhiều cửa hàng

### Xem danh sách tất cả shop (super admin)
```
GET /api/shops/all
```

### Khóa/mở shop
```bash
# Kết nối DB trực tiếp:
sqlite3 /data/salespro.db "UPDATE shops SET active=0 WHERE slug='ten-shop';"
```

### Backup dữ liệu
```bash
# Tải file DB về máy:
scp user@server:/opt/render/project/data/salespro.db ./backup-$(date +%Y%m%d).db

# Hoặc dùng Render's built-in backup (Starter plan trở lên)
```

---

## Chi phí vận hành

| Tầng | Chi phí | Phù hợp |
|------|---------|----------|
| Render Free | $0/tháng | Test, 1-3 shop (ngủ sau 15 phút) |
| Render Starter | $7/tháng | 5-20 shop (luôn chạy, có disk) |
| Render Standard | $25/tháng | 20-100 shop (nhiều RAM hơn) |
| VPS Vultr/DigitalOcean | $6-12/tháng | 100+ shop (toàn quyền kiểm soát) |

**Công thức tính phí cho khách**: 300K-500K/tháng/shop → 10 shop = 3-5M/tháng

---

## Nâng cấp lên PostgreSQL (khi >100 shop)

1. Tạo PostgreSQL service trên Render ($7/tháng)
2. Thêm `DATABASE_URL` environment variable
3. Đổi `database.py`:
   - Thay `sqlite3` bằng `psycopg2`
   - Thay `?` placeholder bằng `%s`
4. Deploy lại

---

## API Endpoints đầy đủ

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/auth/register` | Đăng ký shop mới |
| POST | `/api/auth/login` | Đăng nhập |
| GET  | `/api/auth/me` | Thông tin phiên hiện tại |
| POST | `/api/auth/logout` | Đăng xuất |
| PUT  | `/api/auth/password` | Đổi mật khẩu |
| GET  | `/api/products` | Danh sách sản phẩm |
| POST | `/api/products` | Thêm sản phẩm |
| PUT  | `/api/products/{id}` | Sửa sản phẩm |
| DELETE | `/api/products/{id}` | Xóa sản phẩm |
| GET  | `/api/customers` | Danh sách khách hàng |
| POST | `/api/customers` | Thêm khách hàng |
| GET  | `/api/orders` | Lịch sử đơn hàng |
| POST | `/api/orders` | Tạo đơn hàng (checkout) |
| GET  | `/api/inventory` | Danh sách phiếu kho |
| POST | `/api/inventory` | Tạo phiếu nhập |
| PUT  | `/api/inventory/{id}/approve` | Duyệt/từ chối phiếu |
| GET  | `/api/staff` | Danh sách nhân viên |
| POST | `/api/staff` | Thêm nhân viên |
| GET  | `/api/reports/summary` | Báo cáo tổng hợp |
| GET  | `/api/reports/orders-by-day` | Doanh thu theo ngày |
| GET  | `/api/shops/me` | Thông tin cửa hàng |
| PUT  | `/api/shops/me` | Cập nhật thông tin |

Chi tiết: `https://your-app.onrender.com/docs`
