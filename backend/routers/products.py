from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from database import get_db
from auth_deps import get_current_user, normalize_role

router = APIRouter()


class ProductIn(BaseModel):
    name:            str
    emoji:           str = "📦"
    category:        str = ""
    unit:            str = "Cái"
    retail_price:    Optional[float] = None
    wholesale_price: Optional[float] = None
    stock:           int = 0
    min_stock:       int = 5
    code:            str = ""


@router.get("")
def list_products(
    category: str = "",
    q: str = "",
    user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    shop_id = user["shop_id"] or user["sid"]
    sql = "SELECT * FROM products WHERE shop_id=? AND active=1"
    params = [shop_id]
    if category:
        sql += " AND category=?"; params.append(category)
    if q:
        sql += " AND (name LIKE ? OR code LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY name"
    rows = db.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.post("")
def create_product(
    prod: ProductIn,
    user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    if normalize_role(user["role"]) not in ("chu cua hang", "quan ly", "nhan vien kho"):
        raise HTTPException(403, "Không có quyền thêm sản phẩm")
    shop_id = user["shop_id"] or user["sid"]
    # Auto-thêm danh mục nếu mới
    if prod.category:
        db.execute("INSERT OR IGNORE INTO categories (shop_id,name) VALUES (?,?)",
                   (shop_id, prod.category))
    db.execute("""
        INSERT INTO products
        (shop_id,code,name,emoji,category,unit,retail_price,wholesale_price,stock,min_stock)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (shop_id, prod.code, prod.name, prod.emoji, prod.category,
          prod.unit, prod.retail_price, prod.wholesale_price, prod.stock, prod.min_stock))
    db.commit()
    pid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()


@router.put("/{pid}")
def update_product(
    pid: int,
    prod: ProductIn,
    user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    shop_id = user["shop_id"] or user["sid"]
    row = db.execute("SELECT id FROM products WHERE id=? AND shop_id=?", (pid, shop_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy sản phẩm")
    db.execute("""
        UPDATE products SET
          code=?, name=?, emoji=?, category=?, unit=?,
          retail_price=?, wholesale_price=?, stock=?, min_stock=?,
          updated_at=datetime('now')
        WHERE id=? AND shop_id=?
    """, (prod.code, prod.name, prod.emoji, prod.category, prod.unit,
          prod.retail_price, prod.wholesale_price, prod.stock, prod.min_stock,
          pid, shop_id))
    db.commit()
    return db.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()


@router.delete("/{pid}")
def delete_product(
    pid: int,
    user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    shop_id = user["shop_id"] or user["sid"]
    db.execute("UPDATE products SET active=0 WHERE id=? AND shop_id=?", (pid, shop_id))
    db.commit()
    return {"success": True}


@router.get("/categories/list")
def list_categories(user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    rows = db.execute("SELECT name FROM categories WHERE shop_id=? ORDER BY name", (shop_id,)).fetchall()
    return [r["name"] for r in rows]


@router.get("/suppliers/list")
def list_suppliers(user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    rows = db.execute("SELECT * FROM suppliers WHERE shop_id=? ORDER BY name", (shop_id,)).fetchall()
    return [dict(r) for r in rows]
