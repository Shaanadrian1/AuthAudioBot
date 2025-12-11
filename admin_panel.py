"""
Admin Panel Routes
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import Database

router = APIRouter()
db = Database()
templates = Jinja2Templates(directory="web/templates")

@router.get("/admin/codes")
async def admin_codes(request: Request):
    """Access codes management"""
    codes = db.get_all_codes()
    return templates.TemplateResponse("codes.html", {
        "request": request,
        "codes": codes
    })

@router.get("/admin/voices")
async def admin_voices(request: Request):
    """Voice models management"""
    voices = db.get_all_voices()
    return templates.TemplateResponse("voices.html", {
        "request": request,
        "voices": voices
    })

@router.post("/api/admin/codes/create")
async def create_access_code(
    quota: int = Form(50000),
    days: int = Form(30)
):
    """Create new access code"""
    code = db.create_access_code(quota, days)
    return JSONResponse({
        "success": True,
        "code": code,
        "message": f"Access code created: {code}"
    })

@router.post("/api/admin/voices/add")
async def add_voice(
    name: str = Form(...),
    voice_id: str = Form(...),
    model: str = Form("speech-2.6-turbo"),
    language: str = Form("en"),
    gender: str = Form(None),
    image_url: str = Form(None)
):
    """Add new voice model"""
    success = db.add_voice(name, voice_id, model, language, gender, image_url)
    
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

@router.get("/api/admin/codes")
async def api_get_codes():
    """API: Get all access codes"""
    codes = db.get_all_codes()
    return JSONResponse(codes)

@router.get("/api/admin/voices")
async def api_get_voices():
    """API: Get all voices"""
    voices = db.get_all_voices()
    return JSONResponse(voices)
