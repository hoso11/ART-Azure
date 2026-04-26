import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.exceptions import AppException, app_exception_handler
from app.middleware import RequestLoggingMiddleware

# Configure loguru
logger.remove()
if settings.log_format == "json":
    logger.add(sys.stderr, serialize=True, level="INFO")
else:
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="DEBUG" if settings.debug else "INFO",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} (env={settings.app_env})")
    yield
    logger.info(f"Shutting down {settings.app_name}")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Exception handler
app.add_exception_handler(AppException, app_exception_handler)

# ── Routes ──────────────────────────────────────────────
from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.customers.router import router as customers_router
from app.products.router import router as products_router, categories_router
from app.orders.router import router as orders_router
from app.production.router import router as production_router
from app.inventory.router import router as inventory_router
from app.reports.router import router as reports_router

API_PREFIX = "/api/v1"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(customers_router, prefix=API_PREFIX)
app.include_router(categories_router, prefix=API_PREFIX)
app.include_router(products_router, prefix=API_PREFIX)
app.include_router(orders_router, prefix=API_PREFIX)
app.include_router(production_router, prefix=API_PREFIX)
app.include_router(inventory_router, prefix=API_PREFIX)
app.include_router(reports_router, prefix=API_PREFIX)


# ── Health Checks ───────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/ready")
async def ready():
    from app.database import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        return {"status": "ready"}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "detail": str(e)},
        )
