"""
Database — hỗ trợ cả SQLite (local/test) và PostgreSQL (Supabase/production)
Tự động detect dựa vào biến môi trường DATABASE_URL
"""

import os, hashlib, secrets
from datetime import datetime

# Detect database type
DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_POSTGRES  = DATABASE_URL.startswith("postgres")

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    def get_conn():
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        return conn
    PH = "%s"   # placeholder PostgreSQL
else:
    import sqlite3
    DB_PATH = os.getenv("DB_PATH", "salespro.db")
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    def get_conn():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    PH = "?"    # placeholder SQLite


def get_db():
    """FastAPI dependency"""
    conn = get_conn()
    try:
        yield conn
        if USE_POSTGRES:
            conn.commit()
    finally:
        conn.close()


def _exec(conn, sql, params=()):
    """Unified execute — xử lý placeholder khác nhau giữa SQLite và Postgres"""
    if USE_POSTGRES:
        sql = sql.replace("?", "%s")
        sql = sql.replace("datetime('now')", "NOW()")
        sql = sql.replace("date('now')", "CURRENT_DATE")
        sql = sql.replace("AUTOINCREMENT", "")
        sql = sql.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def init_db():
    """Tạo toàn bộ schema"""
    conn = get_conn()
    c    = conn.cursor()

    serial   = "SERIAL" if USE_POSTGRES else "INTEGER"
    ai       = "" if USE_POSTGRES else "AUTOINCREMENT"
    pk       = f"{serial} PRIMARY KEY {ai}".strip()
    now_fn   = "NOW()" if USE_POSTGRES else "datetime('now')"
    txt      = "TEXT"
    real     = "REAL" if not USE_POSTGRES else "DOUBLE PRECISION"
    integer  = "INTEGER"
    uniq     = "UNIQUE"

    tables = [
        f"""CREATE TABLE IF NOT EXISTS shops (
            id          {pk},
            slug        {txt} UNIQUE NOT NULL,
            name        {txt} NOT NULL,
            owner_name  {txt} NOT NULL,
            email       {txt} UNIQUE NOT NULL,
            phone       {txt},
            address     {txt},
            tax_id      {txt},
            vat_rate    {real} DEFAULT 8,
            plan        {txt} DEFAULT 'free',
            active      {integer} DEFAULT 1,
            created_at  {txt} DEFAULT ({now_fn})
        )""",

        f"""CREATE TABLE IF NOT EXISTS users (
            id            {pk},
            shop_id       {integer} NOT NULL,
            username      {txt} NOT NULL,
            password_hash {txt} NOT NULL,
            role          {txt} NOT NULL DEFAULT 'Thu ngan',
            full_name     {txt},
            email         {txt},
            phone         {txt},
            salary        {real} DEFAULT 0,
            join_date     {txt},
            active        {integer} DEFAULT 1,
            created_at    {txt} DEFAULT ({now_fn}),
            UNIQUE(shop_id, username)
        )""",

        f"""CREATE TABLE IF NOT EXISTS sessions (
            token       {txt} PRIMARY KEY,
            user_id     {integer} NOT NULL,
            shop_id     {integer} NOT NULL,
            expires_at  {txt} NOT NULL,
            created_at  {txt} DEFAULT ({now_fn})
        )""",

        f"""CREATE TABLE IF NOT EXISTS products (
            id              {pk},
            shop_id         {integer} NOT NULL,
            code            {txt},
            name            {txt} NOT NULL,
            emoji           {txt} DEFAULT '📦',
            category        {txt},
            unit            {txt} DEFAULT 'Cai',
            retail_price    {real},
            wholesale_price {real},
            stock           {integer} DEFAULT 0,
            min_stock       {integer} DEFAULT 5,
            active          {integer} DEFAULT 1,
            created_at      {txt} DEFAULT ({now_fn}),
            updated_at      {txt} DEFAULT ({now_fn})
        )""",

        f"""CREATE TABLE IF NOT EXISTS categories (
            id      {pk},
            shop_id {integer} NOT NULL,
            name    {txt} NOT NULL,
            UNIQUE(shop_id, name)
        )""",

        f"""CREATE TABLE IF NOT EXISTS suppliers (
            id      {pk},
            shop_id {integer} NOT NULL,
            name    {txt} NOT NULL,
            phone   {txt},
            email   {txt},
            UNIQUE(shop_id, name)
        )""",

        f"""CREATE TABLE IF NOT EXISTS customers (
            id          {pk},
            shop_id     {integer} NOT NULL,
            name        {txt} NOT NULL,
            phone       {txt},
            email       {txt},
            type        {txt} DEFAULT 'Moi',
            points      {integer} DEFAULT 0,
            total_spend {real} DEFAULT 0,
            debt        {real} DEFAULT 0,
            note        {txt},
            created_at  {txt} DEFAULT ({now_fn})
        )""",

        f"""CREATE TABLE IF NOT EXISTS orders (
            id            {pk},
            shop_id       {integer} NOT NULL,
            order_no      {txt} NOT NULL,
            customer_id   {integer},
            customer_name {txt},
            subtotal      {real} NOT NULL,
            discount      {real} DEFAULT 0,
            vat           {real} DEFAULT 0,
            total         {real} NOT NULL,
            pay_method    {txt} DEFAULT 'Tien mat',
            status        {txt} DEFAULT 'Hoan thanh',
            cashier_id    {integer},
            cashier_name  {txt},
            note          {txt},
            created_at    {txt} DEFAULT ({now_fn})
        )""",

        f"""CREATE TABLE IF NOT EXISTS order_items (
            id           {pk},
            order_id     {integer} NOT NULL,
            product_id   {integer},
            product_name {txt} NOT NULL,
            unit_price   {real} NOT NULL,
            quantity     {integer} NOT NULL,
            subtotal     {real} NOT NULL
        )""",

        f"""CREATE TABLE IF NOT EXISTS inventory (
            id               {pk},
            shop_id          {integer} NOT NULL,
            code             {txt},
            type             {txt} NOT NULL,
            product_id       {integer},
            product_name     {txt} NOT NULL,
            quantity         {integer} NOT NULL,
            unit_price       {real},
            total_value      {real},
            supplier_name    {txt},
            status           {txt} DEFAULT 'Cho duyet',
            note             {txt},
            created_by       {integer},
            created_by_name  {txt},
            approved_by      {integer},
            approved_by_name {txt},
            approved_at      {txt},
            created_at       {txt} DEFAULT ({now_fn})
        )""",
    ]

    for sql in tables:
        c.execute(sql)

    conn.commit()

    # Seed demo nếu chưa có
    c.execute("SELECT COUNT(*) FROM shops")
    row = c.fetchone()
    count = row[0] if USE_POSTGRES else row["COUNT(*)"]
    if count == 0:
        _seed_demo(c, conn)

    conn.close()
    mode = "PostgreSQL (Supabase)" if USE_POSTGRES else f"SQLite ({DB_PATH if not USE_POSTGRES else ''})"
    print(f"✅ Database ready — {mode}")


def _seed_demo(c, conn):
    ph = "%s" if USE_POSTGRES else "?"
    now_fn = "NOW()" if USE_POSTGRES else "datetime('now')"

    c.execute(f"""
        INSERT INTO shops (slug,name,owner_name,email,phone,address,tax_id,vat_rate,plan)
        VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """, ('demo','Ca phe Demo','Nguyen Tuan','demo@salespro.vn',
          '028 1234 5678','123 Nguyen Hue, Q1, TP.HCM','0123456789',8,'pro'))

    if USE_POSTGRES:
        c.execute("SELECT lastval()")
    else:
        c.execute("SELECT last_insert_rowid()")
    shop_id = c.fetchone()[0 if USE_POSTGRES else 0]

    pw = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute(f"""
        INSERT INTO users (shop_id,username,password_hash,role,full_name,email)
        VALUES ({ph},{ph},{ph},{ph},{ph},{ph})
    """, (shop_id,'admin',pw,'Chu cua hang','Nguyen Tuan','admin@salespro.vn'))

    for u,p,r,n in [('quanly','ql2026','Quan ly','Tran Thi Hoa'),
                     ('thungan','tn2026','Thu ngan','Le Van Minh')]:
        pw2 = hashlib.sha256(p.encode()).hexdigest()
        c.execute(f"""
            INSERT INTO users (shop_id,username,password_hash,role,full_name)
            VALUES ({ph},{ph},{ph},{ph},{ph})
        """, (shop_id,u,pw2,r,n))

    for cat in ['Do uong','Banh','Nguyen lieu','Khac']:
        c.execute(f"INSERT INTO categories (shop_id,name) VALUES ({ph},{ph}) ON CONFLICT DO NOTHING", (shop_id,cat))

    conn.commit()
    print("✅ Demo shop created: slug=demo, admin/admin123")


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def make_token() -> str:
    return secrets.token_urlsafe(32)
