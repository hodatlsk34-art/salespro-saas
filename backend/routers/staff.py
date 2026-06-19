"""Staff router"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from database import get_db, hash_password
from auth_deps import can_approve_role, normalize_role
from auth_deps import get_current_user

router = APIRouter()

class StaffIn(BaseModel):
    username:  str
    password:  str = "123456"
    full_name: str
    role:      str = "Thu ngân"
    phone:     str = ""
    email:     str = ""
    salary:    float = 0
    join_date: str = ""

@router.get("")
def list_staff(user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    rows = db.execute(
        "SELECT id,username,full_name,role,phone,email,salary,join_date,active FROM users WHERE shop_id=? ORDER BY full_name",
        (shop_id,)
    ).fetchall()
    return [dict(r) for r in rows]

@router.post("")
def create_staff(req: StaffIn, user=Depends(get_current_user), db=Depends(get_db)):
    if not can_approve_role(user["role"]):
        raise HTTPException(403, "Cần quyền Quản lý trở lên")
    shop_id = user["shop_id"] or user["sid"]
    exists = db.execute("SELECT id FROM users WHERE shop_id=? AND username=?", (shop_id, req.username)).fetchone()
    if exists:
        raise HTTPException(400, "Tên đăng nhập đã tồn tại trong cửa hàng này")
    db.execute("""
        INSERT INTO users (shop_id,username,password_hash,role,full_name,phone,email,salary,join_date)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (shop_id, req.username, hash_password(req.password), req.role,
          req.full_name, req.phone, req.email, req.salary, req.join_date))
    db.commit()
    return {"success": True, "message": f"Đã tạo tài khoản {req.username} / {req.password}"}

@router.put("/{uid}")
def update_staff(uid: int, req: StaffIn, user=Depends(get_current_user), db=Depends(get_db)):
    if not can_approve_role(user["role"]):
        raise HTTPException(403)
    shop_id = user["shop_id"] or user["sid"]
    db.execute("""
        UPDATE users SET full_name=?,role=?,phone=?,email=?,salary=?,join_date=?
        WHERE id=? AND shop_id=?
    """, (req.full_name, req.role, req.phone, req.email, req.salary, req.join_date, uid, shop_id))
    db.commit()
    return {"success": True}

@router.delete("/{uid}")
def delete_staff(uid: int, user=Depends(get_current_user), db=Depends(get_db)):
    if normalize_role(user["role"]) != "chu cua hang":
        raise HTTPException(403, "Chỉ chủ cửa hàng mới xóa được nhân viên")
    shop_id = user["shop_id"] or user["sid"]
    if uid == user["uid"]:
        raise HTTPException(400, "Không thể xóa tài khoản của chính mình")
    db.execute("UPDATE users SET active=0 WHERE id=? AND shop_id=?", (uid, shop_id))
    db.commit()
    return {"success": True}
