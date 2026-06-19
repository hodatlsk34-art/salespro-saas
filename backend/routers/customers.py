"""Customers router"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from database import get_db
from auth_deps import get_current_user

router = APIRouter()

class CustomerIn(BaseModel):
    name:  str
    phone: str = ""
    email: str = ""
    type:  str = "Mới"
    note:  str = ""

@router.get("")
def list_customers(q: str = "", user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    sql = "SELECT * FROM customers WHERE shop_id=?"
    params = [shop_id]
    if q:
        sql += " AND (name LIKE ? OR phone LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY name"
    return [dict(r) for r in db.execute(sql, params).fetchall()]

@router.post("")
def create_customer(req: CustomerIn, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    db.execute("INSERT INTO customers (shop_id,name,phone,email,type,note) VALUES (?,?,?,?,?,?)",
               (shop_id, req.name, req.phone, req.email, req.type, req.note))
    db.commit()
    cid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return dict(db.execute("SELECT * FROM customers WHERE id=?", (cid,)).fetchone())

@router.put("/{cid}")
def update_customer(cid: int, req: CustomerIn, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    db.execute("UPDATE customers SET name=?,phone=?,email=?,type=?,note=? WHERE id=? AND shop_id=?",
               (req.name, req.phone, req.email, req.type, req.note, cid, shop_id))
    db.commit()
    return {"success": True}

@router.delete("/{cid}")
def delete_customer(cid: int, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    db.execute("DELETE FROM customers WHERE id=? AND shop_id=?", (cid, shop_id))
    db.commit()
    return {"success": True}
