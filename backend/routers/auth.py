"""
Auth Router — đăng ký shop, đăng nhập, đăng xuất
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import sqlite3, re

from database import get_db, hash_password, make_token
from auth_deps import get_current_user, get_screens_for_role

router = APIRouter()


class LoginRequest(BaseModel):
    shop_slug: str        # slug của cửa hàng (hoặc "demo")
    username:  str
    password:  str


class RegisterRequest(BaseModel):
    shop_name:  str
    owner_name: str
    email:      str
    phone:      str = ""
    address:    str = ""
    password:   str       # mật khẩu cho tài khoản admin đầu tiên


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


def make_slug(name: str) -> str:
    """Tạo slug từ tên cửa hàng"""
    import unicodedata
    # Bỏ dấu tiếng Việt
    nfkd = unicodedata.normalize('NFKD', name)
    slug = ''.join(c for c in nfkd if not unicodedata.combining(c))
    slug = re.sub(r'[^a-z0-9\s-]', '', slug.lower())
    slug = re.sub(r'[\s-]+', '-', slug).strip('-')
    return slug[:40] or "shop"


@router.post("/register")
def register(req: RegisterRequest, db: sqlite3.Connection = Depends(get_db)):
    """Đăng ký cửa hàng mới — tạo shop + user admin"""
    # Kiểm tra email chưa tồn tại
    existing = db.execute("SELECT id FROM shops WHERE email=?", (req.email,)).fetchone()
    if existing:
        raise HTTPException(400, "Email này đã được đăng ký")

    # Tạo slug duy nhất
    base_slug = make_slug(req.shop_name)
    slug = base_slug
    i = 1
    while db.execute("SELECT id FROM shops WHERE slug=?", (slug,)).fetchone():
        slug = f"{base_slug}-{i}"; i += 1

    # Tạo shop
    db.execute("""
        INSERT INTO shops (slug, name, owner_name, email, phone, address, plan)
        VALUES (?, ?, ?, ?, ?, ?, 'free')
    """, (slug, req.shop_name, req.owner_name, req.email, req.phone, req.address))
    shop_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Tạo user admin đầu tiên
    db.execute("""
        INSERT INTO users (shop_id, username, password_hash, role, full_name, email)
        VALUES (?, 'admin', ?, 'Chủ cửa hàng', ?, ?)
    """, (shop_id, hash_password(req.password), req.owner_name, req.email))

    # Tạo danh mục mặc định
    for cat in ['Đồ uống', 'Thực phẩm', 'Nguyên liệu', 'Khác']:
        db.execute("INSERT OR IGNORE INTO categories (shop_id, name) VALUES (?,?)", (shop_id, cat))

    db.commit()
    return {
        "success": True,
        "shop_slug": slug,
        "message": f"✅ Đăng ký thành công! Shop URL: /shop/{slug}",
        "login_info": {"shop_slug": slug, "username": "admin", "password": req.password}
    }


@router.post("/login")
def login(req: LoginRequest, db: sqlite3.Connection = Depends(get_db)):
    """Đăng nhập — trả về token phiên 8 giờ"""
    # Tìm shop
    shop = db.execute(
        "SELECT * FROM shops WHERE slug=? AND active=1", (req.shop_slug,)
    ).fetchone()
    if not shop:
        raise HTTPException(401, "Không tìm thấy cửa hàng hoặc đã bị khóa")

    # Tìm user
    user = db.execute(
        "SELECT * FROM users WHERE shop_id=? AND username=? AND active=1",
        (shop["id"], req.username)
    ).fetchone()
    if not user or user["password_hash"] != hash_password(req.password):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")

    # Tạo session token
    token = make_token()
    expires = (datetime.utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M:%S")
    db.execute("""
        INSERT INTO sessions (token, user_id, shop_id, expires_at)
        VALUES (?, ?, ?, ?)
    """, (token, user["id"], shop["id"], expires))
    db.commit()

    return {
        "token":     token,
        "expires_at": expires,
        "user": {
            "id":       user["id"],
            "username": user["username"],
            "role":     user["role"],
            "name":     user["full_name"],
            "screens":  get_screens_for_role(user["role"]),
        },
        "shop": {
            "id":       shop["id"],
            "slug":     shop["slug"],
            "name":     shop["name"],
            "owner":    shop["owner_name"],
            "vat_rate": shop["vat_rate"],
            "plan":     shop["plan"],
        }
    }


@router.post("/logout")
def logout(
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    db.execute("DELETE FROM sessions WHERE user_id=? AND shop_id=?",
               (user["uid"], user["shop_id"] or user["sid"]))
    db.commit()
    return {"success": True}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Kiểm tra token còn hiệu lực"""
    return {
        "user": {
            "id":       user["uid"],
            "username": user["username"],
            "role":     user["role"],
            "name":     user["full_name"],
            "screens":  get_screens_for_role(user["role"]),
        },
        "shop": {
            "slug":     user["slug"],
            "name":     user["shop_name"],
            "vat_rate": user["vat_rate"],
            "plan":     user["plan"],
        }
    }


@router.put("/password")
def change_password(
    req: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    row = db.execute("SELECT password_hash FROM users WHERE id=?", (user["uid"],)).fetchone()
    if not row or row["password_hash"] != hash_password(req.old_password):
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    if len(req.new_password) < 6:
        raise HTTPException(400, "Mật khẩu mới phải ít nhất 6 ký tự")
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (hash_password(req.new_password), user["uid"]))
    db.commit()
    return {"success": True}
