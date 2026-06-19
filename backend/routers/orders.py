from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from database import get_db
from auth_deps import get_current_user

router = APIRouter()


class OrderItem(BaseModel):
    product_id:   Optional[int] = None
    product_name: str
    unit_price:   float
    quantity:     int


class OrderIn(BaseModel):
    customer_id:  Optional[int] = None
    customer_name: str = "Vãng lai"
    items:        List[OrderItem]
    pay_method:   str = "Tiền mặt"
    note:         str = ""


@router.get("")
def list_orders(
    limit: int = 50,
    offset: int = 0,
    user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    shop_id = user["shop_id"] or user["sid"]
    orders = db.execute("""
        SELECT o.*, GROUP_CONCAT(i.product_name || ' x' || i.quantity, ', ') as items_summary
        FROM orders o
        LEFT JOIN order_items i ON i.order_id = o.id
        WHERE o.shop_id=?
        GROUP BY o.id
        ORDER BY o.created_at DESC
        LIMIT ? OFFSET ?
    """, (shop_id, limit, offset)).fetchall()
    return [dict(r) for r in orders]


@router.get("/{oid}")
def get_order(oid: int, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    order = db.execute("SELECT * FROM orders WHERE id=? AND shop_id=?", (oid, shop_id)).fetchone()
    if not order:
        raise HTTPException(404)
    items = db.execute("SELECT * FROM order_items WHERE order_id=?", (oid,)).fetchall()
    return {**dict(order), "items": [dict(i) for i in items]}


@router.post("")
def create_order(
    req: OrderIn,
    user=Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """Tạo đơn hàng — trừ tồn kho — cập nhật điểm KH — ghi phiếu xuất kho"""
    shop_id = user["shop_id"] or user["sid"]

    # Lấy VAT rate
    shop = db.execute("SELECT vat_rate FROM shops WHERE id=?", (shop_id,)).fetchone()
    vat_rate = shop["vat_rate"] if shop else 8

    # Tính toán
    subtotal = sum(it.unit_price * it.quantity for it in req.items)

    # Giảm giá VIP
    discount = 0
    if req.customer_id:
        cust = db.execute("SELECT type FROM customers WHERE id=? AND shop_id=?",
                          (req.customer_id, shop_id)).fetchone()
        if cust and cust["type"] == "VIP":
            discount = round(subtotal * 0.05, 0)

    vat   = round((subtotal - discount) * vat_rate / 100, 0)
    total = subtotal - discount + vat

    # Tạo mã đơn
    count = db.execute("SELECT COUNT(*) FROM orders WHERE shop_id=?", (shop_id,)).fetchone()[0]
    order_no = f"#DH{count+1:04d}"

    # Lưu đơn hàng
    db.execute("""
        INSERT INTO orders
        (shop_id,order_no,customer_id,customer_name,subtotal,discount,vat,total,
         pay_method,status,cashier_id,cashier_name,note)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (shop_id, order_no, req.customer_id, req.customer_name,
          subtotal, discount, vat, total,
          req.pay_method, "Hoàn thành",
          user["uid"], user["full_name"], req.note))
    order_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Lưu items + trừ tồn kho + ghi phiếu xuất
    inv_count = db.execute("SELECT COUNT(*) FROM inventory WHERE shop_id=?", (shop_id,)).fetchone()[0]
    for it in req.items:
        sub = it.unit_price * it.quantity
        db.execute("""
            INSERT INTO order_items (order_id,product_id,product_name,unit_price,quantity,subtotal)
            VALUES (?,?,?,?,?,?)
        """, (order_id, it.product_id, it.product_name, it.unit_price, it.quantity, sub))

        # Trừ tồn kho
        if it.product_id:
            db.execute("UPDATE products SET stock=MAX(0,stock-?), updated_at=datetime('now') WHERE id=? AND shop_id=?",
                       (it.quantity, it.product_id, shop_id))

        # Ghi phiếu xuất kho tự động
        inv_count += 1
        db.execute("""
            INSERT INTO inventory
            (shop_id,code,type,product_id,product_name,quantity,unit_price,total_value,
             status,created_by,created_by_name,approved_by,approved_by_name,approved_at,note)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)
        """, (shop_id, f"#XK{inv_count:04d}", "XK",
              it.product_id, it.product_name, it.quantity,
              it.unit_price, sub, "Hoàn thành",
              user["uid"], user["full_name"],
              user["uid"], user["full_name"],
              f"Đơn {order_no}"))

    # Cập nhật KH: điểm tích lũy, chi tiêu, nâng hạng
    if req.customer_id:
        pts = int(total // 1000)
        db.execute("""
            UPDATE customers SET
              points     = points + ?,
              total_spend = total_spend + ?,
              type = CASE
                WHEN total_spend + ? >= 5000000 THEN 'VIP'
                WHEN total_spend + ? >= 1000000 THEN 'Thường xuyên'
                ELSE type
              END
            WHERE id=? AND shop_id=?
        """, (pts, total, total, total, req.customer_id, shop_id))

    # Ghi doanh thu nhân viên
    db.execute("""
        UPDATE users SET
          salary = salary  -- (doanh thu riêng cần bảng staff_stats nếu muốn chi tiết)
        WHERE id=?
    """, (user["uid"],))  # placeholder — extend if needed

    db.commit()
    return {
        "success":  True,
        "order_id": order_id,
        "order_no": order_no,
        "total":    total,
        "discount": discount,
        "vat":      vat,
    }
