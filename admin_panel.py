"""
Admin Panel Routes for FastAPI
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import hashlib
import json
from typing import Dict, Any

from app.database import Database

router = APIRouter()
db = Database()
templates = Jinja2Templates(directory="web/templates")

# Simple authentication (for demo - use proper auth in production)
def verify_admin(username: str, password: str) -> bool:
    """Verify admin credentials"""
    admin_user = "admin"
    admin_pass = "admin123"  # Change this in production!
    
    # You should use environment variables for credentials
    import os
    env_user = os.getenv("ADMIN_USERNAME", admin_user)
    env_pass = os.getenv("ADMIN_PASSWORD", admin_pass)
    
    return username == env_user and password == env_pass

@router.get("/admin/login")
async def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/admin/login")
async def admin_login(
    username: str = Form(...),
    password: str = Form(...)
):
    """Admin login endpoint"""
    if verify_admin(username, password):
        # Create simple session token (use JWT in production)
        token = hashlib.sha256(f"{username}:{password}".encode()).hexdigest()
        return JSONResponse({
            "success": True,
            "token": token,
            "redirect": "/admin/dashboard"
        })
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/admin/dashboard")
async def admin_dashboard(request: Request):
    """Admin dashboard"""
    # Check token (simplified)
    token = request.cookies.get("admin_token")
    if not token:
        return HTMLResponse(content="Unauthorized", status_code=401)
    
    stats = db.get_statistics()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "stats": stats
    })

@router.get("/admin/codes")
async def manage_codes(request: Request):
    """Manage access codes"""
    codes = db.get_all_codes()
    
    return templates.TemplateResponse("codes.html", {
        "request": request,
        "codes": codes
    })

@router.post("/admin/codes/create")
async def create_access_code(
    quota: int = Form(...),
    days: int = Form(30),
    max_users: int = Form(1),
    notes: str = Form(None)
):
    """Create new access code"""
    code = db.create_access_code(quota, days, max_users, notes)
    
    if code:
        return JSONResponse({
            "success": True,
            "code": code,
            "message": f"Access code created: {code}"
        })
    else:
        return JSONResponse({
            "success": False,
            "message": "Failed to create access code"
        }, status_code=400)

@router.get("/admin/voices")
async def manage_voices(request: Request):
    """Manage voice models"""
    voices = db.get_all_voices()
    
    return templates.TemplateResponse("voices.html", {
        "request": request,
        "voices": voices
    })

@router.post("/admin/voices/add")
async def add_voice(
    name: str = Form(...),
    voice_id: str = Form(...),
    model: str = Form("speech-2.6-turbo"),
    language: str = Form("en"),
    gender: str = Form(None),
    preview_url: str = Form(None),
    image_url: str = Form(None)
):
    """Add new voice model"""
    voice_data = {
        "name": name,
        "voice_id": voice_id,
        "model": model,
        "language": language,
        "gender": gender,
        "preview_url": preview_url,
        "image_url": image_url
    }
    
    success = db.add_voice(voice_data)
    
    if success:
        return JSONResponse({
            "success": True,
            "message": "Voice added successfully"
        })
    else:
        return JSONResponse({
            "success": False,
            "message": "Failed to add voice"
        }, status_code=400)

@router.get("/admin/statistics")
async def get_statistics():
    """Get system statistics"""
    stats = db.get_statistics()
    return JSONResponse(stats)

# API endpoints (for AJAX calls)
@router.get("/api/codes")
async def api_get_codes():
    """API: Get all access codes"""
    codes = db.get_all_codes()
    return JSONResponse(codes)

@router.get("/api/voices")
async def api_get_voices():
    """API: Get all voices"""
    voices = db.get_all_voices()
    return JSONResponse(voices)

@router.get("/api/stats")
async def api_get_stats():
    """API: Get statistics"""
    stats = db.get_statistics()
    return JSONResponse(stats)