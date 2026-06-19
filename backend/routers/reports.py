"""Reports router — báo cáo tính toán từ dữ liệu thật"""
from fastapi import APIRouter, Depends
import sqlite3
from database import get_db
from auth_deps import get_current_user

router = APIRouter()

@router.get("/summary")
def summary(
    period: str = "month",   # today | week | month | year
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    shop_id = user["shop_id"] or user["sid"]
    period_filter = {
        "today": "date(created_at)=date('now')",
        "week":  "created_at >= datetime('now','-7 days')",
        "month": "strftime('%Y-%m',created_at)=strftime('%Y-%m','now')",
        "year":  "strftime('%Y',created_at)=strftime('%Y','now')",
    }.get(period, "strftime('%Y-%m',created_at)=strftime('%Y-%m','now')")

    # Doanh thu
    rev = db.execute(f"""
        SELECT COUNT(*) as cnt, COALESCE(SUM(total),0) as total,
               COALESCE(AVG(total),0) as avg_order
        FROM orders WHERE shop_id=? AND {period_filter}
    """, (shop_id,)).fetchone()

    # Sản phẩm bán chạy
    top_prods = db.execute(f"""
        SELECT oi.product_name, SUM(oi.quantity) as qty, SUM(oi.subtotal) as revenue
        FROM order_items oi
        JOIN orders o ON o.id=oi.order_id
        WHERE o.shop_id=? AND {period_filter}
        GROUP BY oi.product_name ORDER BY qty DESC LIMIT 10
    """, (shop_id,)).fetchall()

    # Tồn kho cảnh báo
    low_stock = db.execute("""
        SELECT name,stock,min_stock,emoji FROM products
        WHERE shop_id=? AND active=1 AND stock<=min_stock ORDER BY stock
    """, (shop_id,)).fetchall()

    # Phiếu chờ duyệt
    pending_inv = db.execute("""
        SELECT COUNT(*) FROM inventory WHERE shop_id=? AND status='Chờ duyệt'
    """, (shop_id,)).fetchone()[0]

    # Công nợ
    debt = db.execute("""
        SELECT COALESCE(SUM(debt),0) FROM customers WHERE shop_id=?
    """, (shop_id,)).fetchone()[0]

    # Nhân viên
    staff_count = db.execute("SELECT COUNT(*) FROM users WHERE shop_id=? AND active=1", (shop_id,)).fetchone()[0]
    total_salary = db.execute("SELECT COALESCE(SUM(salary),0) FROM users WHERE shop_id=? AND active=1", (shop_id,)).fetchone()[0]

    # Báo cáo thuế
    shop = db.execute("SELECT vat_rate FROM shops WHERE id=?", (shop_id,)).fetchone()
    vat_rate = shop["vat_rate"] if shop else 8
    total_revenue = float(rev["total"] or 0)
    vat_amount = round(total_revenue * vat_rate / (100 + vat_rate), 0)
    tncn = round(float(total_salary or 0) * 0.10, 0)

    return {
        "revenue": {
            "total":        total_revenue,
            "order_count":  rev["cnt"],
            "avg_order":    round(float(rev["avg_order"] or 0), 0),
        },
        "top_products": [dict(r) for r in top_prods],
        "low_stock":    [dict(r) for r in low_stock],
        "pending_inv":  pending_inv,
        "debt_total":   float(debt or 0),
        "staff": {
            "count":        staff_count,
            "total_salary": float(total_salary or 0),
        },
        "tax": {
            "revenue_gross":  total_revenue,
            "vat_rate":       vat_rate,
            "vat_amount":     vat_amount,
            "tncn_estimate":  tncn,
            "total_tax":      vat_amount + tncn,
        }
    }

@router.get("/orders-by-day")
def orders_by_day(days: int = 30, user=Depends(get_current_user), db=Depends(get_db)):
    shop_id = user["shop_id"] or user["sid"]
    rows = db.execute("""
        SELECT date(created_at) as date,
               COUNT(*) as order_count,
               COALESCE(SUM(total),0) as revenue
        FROM orders WHERE shop_id=?
          AND created_at >= datetime('now', ? || ' days')
        GROUP BY date(created_at) ORDER BY date
    """, (shop_id, f"-{days}")).fetchall()
    return [dict(r) for r in rows]
