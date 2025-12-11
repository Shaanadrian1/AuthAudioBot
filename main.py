"""
Main FastAPI Application for Render.com
"""

import os
import sys
import logging
import asyncio
from threading import Thread
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Add app directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.telegram_bot import TelegramBot
from app.database import Database
from app.admin_panel import admin_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/app.log')
    ]
)

logger = logging.getLogger(__name__)

# Initialize database
db = Database()

# Initialize Telegram bot
bot = TelegramBot()

# Templates
templates = Jinja2Templates(directory="web/templates")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for startup/shutdown
    """
    # Startup
    logger.info("🚀 Starting TTS Bot Application...")
    
    # Initialize database
    db.init_database()
    logger.info("✅ Database initialized")
    
    # Start Telegram bot in background thread
    bot_thread = Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    logger.info("✅ Telegram bot started in background")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down TTS Bot Application...")

def start_telegram_bot():
    """Start Telegram bot"""
    try:
        asyncio.run(bot.run())
    except Exception as e:
        logger.error(f"❌ Telegram bot error: {e}")

# Create FastAPI app
app = FastAPI(
    title="TTS Bot API",
    description="Advanced Text-to-Speech Bot with Telegram Integration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Render
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Include admin routes
app.include_router(admin_routes, prefix="/api/admin")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "running",
        "service": "TTS Bot API",
        "version": "1.0.0",
        "endpoints": {
            "admin": "/admin",
            "health": "/health",
            "api_docs": "/docs"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check for Render"""
    try:
        # Check database
        db_status = db.health_check()
        
        return {
            "status": "healthy",
            "database": "connected" if db_status else "disconnected",
            "timestamp": os.environ.get("RENDER_TIMESTAMP", "unknown")
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )

# Admin dashboard
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """Admin dashboard"""
    return templates.TemplateResponse("admin.html", {"request": request})

# API Documentation
@app.get("/docs", response_class=HTMLResponse)
async def api_docs():
    """API documentation page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>TTS Bot API Documentation</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .endpoint { background: #f5f5f5; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .method { display: inline-block; padding: 5px 10px; border-radius: 3px; color: white; }
            .get { background: #61affe; }
            .post { background: #49cc90; }
            .put { background: #fca130; }
            .delete { background: #f93e3e; }
        </style>
    </head>
    <body>
        <h1>📚 TTS Bot API Documentation</h1>
        
        <div class="endpoint">
            <span class="method get">GET</span> <code>/health</code>
            <p>Health check endpoint</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <code>/admin</code>
            <p>Admin dashboard</p>
        </div>
        
        <div class="endpoint">
            <span class="method post">POST</span> <code>/api/admin/login</code>
            <p>Admin login</p>
        </div>
        
        <div class="endpoint">
            <span class="method get">GET</span> <code>/api/admin/statistics</code>
            <p>Get system statistics</p>
        </div>
        
        <p>For full API documentation, visit <a href="/docs">/docs</a> (FastAPI Swagger)</p>
    </body>
    </html>
    """

# Error handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if os.getenv("DEBUG", "false").lower() == "true" else None
        }
    )

# Run the app
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )