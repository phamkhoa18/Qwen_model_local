"""
VKS AI Platform - Main Application
Full-featured local AI API server with playground UI
"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pathlib import Path

from backend.config import settings
from backend.database import db
from backend.routes import chat, api_keys, admin

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print(f"""
==============================================
  VKS AI PLATFORM v{settings.APP_VERSION}
  He thong AI Vien Kiem Sat Nhan Dan
----------------------------------------------
  API:        http://{settings.HOST}:{settings.PORT}
  Playground: http://{settings.HOST}:{settings.PORT}/playground
  Docs:       http://{settings.HOST}:{settings.PORT}/docs
  Ollama:     {settings.OLLAMA_BASE_URL}
  MongoDB:    {settings.MONGODB_URI}
==============================================
    """)
    
    await db.connect()
    yield
    
    # Shutdown
    await db.disconnect()


# Create app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="🏛️ Hệ thống AI Local cho Viện Kiểm Sát Nhân Dân Việt Nam",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include routers
app.include_router(chat.router, tags=["Chat"])
app.include_router(api_keys.router, tags=["API Keys"])
app.include_router(admin.router, tags=["Admin"])


# ============ Page Routes ============

@app.get("/")
async def home(request: Request):
    """Redirect to playground"""
    return templates.TemplateResponse("playground.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "default_model": settings.DEFAULT_MODEL
    })


@app.get("/playground")
async def playground(request: Request):
    """API Playground - Test interface like Google AI Studio"""
    return templates.TemplateResponse("playground.html", {
        "request": request,
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "default_model": settings.DEFAULT_MODEL
    })


# ============ Error Handlers ============

@app.exception_handler(404)
async def not_found(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": {"message": "Not found", "type": "not_found"}}
    )


@app.exception_handler(500)
async def server_error(request: Request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "Internal server error", "type": "server_error"}}
    )


# ============ Run ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
