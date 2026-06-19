"""
SalesPro SaaS Backend v2.0
FastAPI + SQLite — Multi-tenant
Deploy: Railway.app / Fly.io / VPS
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn, os, pathlib

from database import init_db
from routers import auth, shops, products, customers, inventory, orders, staff, reports

app = FastAPI(
    title="SalesPro SaaS API",
    description="Hệ thống quản lý bán hàng đa cửa hàng",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None,
)

# ── CORS ──────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    init_db()
    print(f"✅ SalesPro SaaS started")
    print(f"   DB: {os.getenv('DB_PATH', 'salespro.db')}")
    print(f"   Docs: /docs")

# ── API Routers ───────────────────────────────────────────────
app.include_router(auth.router,      prefix="/api/auth",      tags=["Auth"])
app.include_router(shops.router,     prefix="/api/shops",     tags=["Shops"])
app.include_router(products.router,  prefix="/api/products",  tags=["Products"])
app.include_router(customers.router, prefix="/api/customers", tags=["Customers"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])
app.include_router(orders.router,    prefix="/api/orders",    tags=["Orders"])
app.include_router(staff.router,     prefix="/api/staff",     tags=["Staff"])
app.include_router(reports.router,   prefix="/api/reports",   tags=["Reports"])

# ── Health check ──────────────────────────────────────────────
@app.get("/health")
def health():
    import sqlite3, os
    db_path = os.getenv("DB_PATH", "salespro.db")
    try:
        conn = sqlite3.connect(db_path)
        shops_count = conn.execute("SELECT COUNT(*) FROM shops").fetchone()[0]
        conn.close()
        return {"status": "ok", "shops": shops_count, "db": db_path}
    except Exception as e:
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)

# ── Serve frontend (SalesPro.html) ───────────────────────────
FRONTEND_DIR = pathlib.Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    @app.get("/")
    def root():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/app")
    def serve_app():
        return FileResponse(FRONTEND_DIR / "index.html")

    # Static assets nếu có
    static_dir = FRONTEND_DIR / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    @app.get("/")
    def root():
        return {
            "service": "SalesPro SaaS API",
            "version": "2.0.0",
            "docs": "/docs",
            "health": "/health",
            "register": "POST /api/auth/register",
            "login": "POST /api/auth/login",
        }

# ── Error handlers ────────────────────────────────────────────
@app.exception_handler(404)
async def not_found(request: Request, exc):
    # Nếu là API call thì trả JSON
    if request.url.path.startswith("/api"):
        return JSONResponse({"detail": "Không tìm thấy"}, status_code=404)
    # Nếu là page request, serve frontend (SPA routing)
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return JSONResponse({"detail": "Not found"}, status_code=404)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
