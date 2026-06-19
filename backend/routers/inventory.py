"""Inventory router — phiếu nhập/xuất kho với quy trình duyệt"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import sqlite3
from database import get_db
from auth_deps import get_current_user, can_approve_role

router = APIRouter()

class InvIn(BaseModel):
    type:          str = "NK"
    product_id:    Optional[int] = None
    product_name:  str
    quantity:      int
    unit_price:    Optional[float] = None
    supplier_name: str = ""
    note:          str = ""

class ApproveIn(BaseModel):
    action: str   # "approve" | "reject"

@router.get("")
def list_inventory(
    type: str = "",
    status: str = "",
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    shop_id = user["shop_id"] or user["sid"]
    sql = "SELECT * FROM inventory WHERE shop_id=?"
    params = [shop_id]
    if type:   sql += " AND type=?";   params.append(type)
    if status: sql += " AND status=?"; params.append(status)
    sql += " ORDER BY created_at DESC LIMIT 200"
    return [dict(r) for r in db.execute(sql, params).fetchall()]

@router.post("")
def create_inv(req: InvIn, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    count = db.execute("SELECT COUNT(*) FROM inventory WHERE shop_id=?", (shop_id,)).fetchone()[0]
    code = f"#{req.type}{count+1:04d}"
    total = (req.unit_price or 0) * req.quantity if req.unit_price else None

    # Tự động duyệt nếu người tạo có quyền
    auto_approve = can_approve_role(user["role"])
    status = "Đã duyệt" if auto_approve else "Chờ duyệt"

    db.execute("""
        INSERT INTO inventory
        (shop_id,code,type,product_id,product_name,quantity,unit_price,total_value,
         supplier_name,status,note,created_by,created_by_name,
         approved_by,approved_by_name,approved_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (shop_id, code, req.type, req.product_id, req.product_name,
          req.quantity, req.unit_price, total, req.supplier_name,
          status, req.note, user["uid"], user["full_name"],
          (user["uid"] if auto_approve else None),
          (user["full_name"] if auto_approve else None),
          ("datetime('now')" if auto_approve else None)))

    # Nếu tự duyệt và là nhập kho → cộng tồn kho ngay
    if auto_approve and req.type == "NK" and req.product_id:
        db.execute("UPDATE products SET stock=stock+?, updated_at=datetime('now') WHERE id=? AND shop_id=?",
                   (req.quantity, req.product_id, shop_id))

    db.commit()
    iid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    return dict(db.execute("SELECT * FROM inventory WHERE id=?", (iid,)).fetchone())

@router.put("/{iid}/approve")
def approve_inv(iid: int, req: ApproveIn, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    if not can_approve_role(user["role"]):
        raise HTTPException(403, "Cần quyền Quản lý hoặc Chủ cửa hàng để duyệt")
    row = db.execute("SELECT * FROM inventory WHERE id=? AND shop_id=?", (iid, shop_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy phiếu")
    if dict(row)["status"] != "Chờ duyệt":
        raise HTTPException(400, "Phiếu này không ở trạng thái Chờ duyệt")

    if req.action == "approve":
        db.execute("""
            UPDATE inventory SET status='Đã duyệt',
              approved_by=?, approved_by_name=?, approved_at=datetime('now')
            WHERE id=? AND shop_id=?
        """, (user["uid"], user["full_name"], iid, shop_id))
        # Cộng tồn kho nếu nhập
        if dict(row)["type"] == "NK" and dict(row)["product_id"]:
            db.execute("UPDATE products SET stock=stock+?, updated_at=datetime('now') WHERE id=? AND shop_id=?",
                       (dict(row)["quantity"], dict(row)["product_id"], shop_id))
    else:
        db.execute("UPDATE inventory SET status='Từ chối' WHERE id=? AND shop_id=?", (iid, shop_id))

    db.commit()
    return {"success": True, "action": req.action}

@router.put("/{iid}")
def update_inv(iid: int, req: InvIn, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    row = db.execute("SELECT status FROM inventory WHERE id=? AND shop_id=?", (iid, shop_id)).fetchone()
    if not row:
        raise HTTPException(404)
    if dict(row)["status"] != "Chờ duyệt":
        raise HTTPException(400, "Chỉ sửa được phiếu ở trạng thái Chờ duyệt")
    total = (req.unit_price or 0) * req.quantity if req.unit_price else None
    db.execute("""
        UPDATE inventory SET product_id=?,product_name=?,quantity=?,unit_price=?,
          total_value=?,supplier_name=?,note=? WHERE id=? AND shop_id=?
    """, (req.product_id, req.product_name, req.quantity, req.unit_price,
          total, req.supplier_name, req.note, iid, shop_id))
    db.commit()
    return {"success": True}

@router.delete("/{iid}")
def delete_inv(iid: int, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    row = db.execute("SELECT status FROM inventory WHERE id=? AND shop_id=?", (iid, shop_id)).fetchone()
    if not row:
        raise HTTPException(404)
    if dict(row)["status"] != "Chờ duyệt":
        raise HTTPException(400, "Chỉ xóa được phiếu ở trạng thái Chờ duyệt")
    db.execute("DELETE FROM inventory WHERE id=? AND shop_id=?", (iid, shop_id))
    db.commit()
    return {"success": True}
