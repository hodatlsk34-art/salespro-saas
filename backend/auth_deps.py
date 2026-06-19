"""
Auth helpers — token-based session (không dùng JWT để đơn giản)
"""

from fastapi import Depends, HTTPException, status, Header
from typing import Optional
import sqlite3, unicodedata
from datetime import datetime, timedelta
from database import get_db, make_token


def normalize_role(role: str) -> str:
    """Chuẩn hóa role về dạng không dấu, để tra cứu không phụ thuộc encoding."""
    if not role:
        return ""
    nfkd = unicodedata.normalize('NFKD', role)
    no_accent = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return no_accent.strip().lower()


# Quyền theo vai trò — key đã chuẩn hóa không dấu, viết thường
ROLE_SCREENS = {
    "chu cua hang": ["dashboard","pos","products","inventory","customers","staff","debt","reports","roles","settings"],
    "quan ly":      ["dashboard","pos","products","inventory","customers","staff","debt","reports"],
    "thu ngan":     ["pos","customers"],
    "nhan vien kho":["products","inventory"],
}

CAN_APPROVE_NORM = {"chu cua hang", "quan ly"}


def get_screens_for_role(role: str):
    return ROLE_SCREENS.get(normalize_role(role), [])


def can_approve_role(role: str) -> bool:
    return normalize_role(role) in CAN_APPROVE_NORM


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: sqlite3.Connection = Depends(get_db)
):
    """Dependency: xác thực token từ header Authorization: Bearer <token>"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    token = authorization.split(" ", 1)[1]
    session = db.execute("""
        SELECT s.*, u.id as uid, u.username, u.role, u.full_name, u.shop_id as sid,
               sh.name as shop_name, sh.slug, sh.vat_rate, sh.plan, sh.active as shop_active
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        JOIN shops sh ON s.shop_id = sh.id
        WHERE s.token = ? AND s.expires_at > datetime('now')
    """, (token,)).fetchone()

    if not session:
        raise HTTPException(status_code=401, detail="Phiên đăng nhập hết hạn")
    if not session["shop_active"]:
        raise HTTPException(status_code=403, detail="Tài khoản shop đã bị khóa")

    return dict(session)


def require_role(*roles):
    """Factory: yêu cầu vai trò cụ thể"""
    def checker(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Cần quyền: {', '.join(roles)}"
            )
        return user
    return checker


def shop_id_of(user: dict) -> int:
    return user["shop_id"] or user["sid"]
