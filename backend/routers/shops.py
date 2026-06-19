"""Shops router — quản lý thông tin cửa hàng"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from database import get_db
from auth_deps import get_current_user, normalize_role

router = APIRouter()

class ShopUpdate(BaseModel):
    name:       Optional[str] = None
    owner_name: Optional[str] = None
    phone:      Optional[str] = None
    address:    Optional[str] = None
    tax_id:     Optional[str] = None
    vat_rate:   Optional[float] = None

@router.get("/me")
def get_my_shop(user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    shop = db.execute("SELECT * FROM shops WHERE id=?", (shop_id,)).fetchone()
    if not shop:
        raise HTTPException(404)
    return dict(shop)

@router.put("/me")
def update_my_shop(req: ShopUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    if normalize_role(user["role"]) != "chu cua hang":
        raise HTTPException(403, "Chỉ chủ cửa hàng mới sửa được thông tin")
    shop_id = user["shop_id"] or user["sid"]
    updates, params = [], []
    for field, val in req.dict(exclude_none=True).items():
        updates.append(f"{field}=?"); params.append(val)
    if updates:
        params.append(shop_id)
        db.execute(f"UPDATE shops SET {', '.join(updates)} WHERE id=?", params)
        db.commit()
    return {"success": True}

@router.get("/all")  # chỉ super-admin dùng — bảo vệ bằng secret header sau
def list_all_shops(db=Depends(get_db)):
    rows = db.execute("SELECT id,slug,name,email,plan,active,created_at FROM shops ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]
