"""
Main Application - Render.com Optimized
"""

import os
import sys
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create app
app = FastAPI(title="TTS Bot API", version="1.0.0")

# Templates
templates = Jinja2Templates(directory="web/templates")

# Mount static files
app.mount("/static", StaticFiles(directory="web/static"), name="static")

@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "TTS Bot API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "admin": "/admin"
    }

@app.get("/health")
async def health_check():
    return JSONResponse({
        "status": "healthy",
        "service": "tts-bot",
        "timestamp": "2024-01-01T00:00:00Z"
    })

@app.get("/admin")
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.get("/docs")
async def api_docs():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><title>API Docs</title></head>
    <body>
        <h1>TTS Bot API Documentation</h1>
        <p>Visit <a href="/docs">/docs</a> for Swagger UI</p>
    </body>
    </html>
    """)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
