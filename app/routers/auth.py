from urllib.parse import urlparse

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import verify_password, hash_password, get_current_user
from .. import models

from ..templates import templates
router = APIRouter()


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", 302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        lang = request.session.get("lang", "uk")
        error = "Invalid email or password" if lang == "en" else "Невірний email або пароль"
        return templates.TemplateResponse("login.html", {"request": request, "error": error})
    request.session["user_id"] = user.id
    return RedirectResponse("/", 302)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 302)


@router.get("/set-lang/{code}")
def set_lang(code: str, request: Request):
    if code in ("uk", "en"):
        request.session["lang"] = code
    raw = request.headers.get("referer", "/")
    parsed = urlparse(raw)
    # Only allow same-origin redirects — reject any external host
    safe = raw if not parsed.netloc or parsed.netloc == request.headers.get("host") else "/"
    return RedirectResponse(safe, 302)


@router.get("/profile/password")
def change_password_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("profile_password.html", {
        "request": request, "user": user,
    })


@router.post("/profile/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    lang = request.session.get("lang", "uk")

    def err(key):
        from ..i18n import TRANSLATIONS
        return TRANSLATIONS.get(lang, TRANSLATIONS["uk"]).get(key, key)

    if not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse("profile_password.html", {
            "request": request, "user": user, "error": err("pwd_err_wrong"),
        })
    if new_password != confirm_password:
        return templates.TemplateResponse("profile_password.html", {
            "request": request, "user": user, "error": err("pwd_err_mismatch"),
        })
    if len(new_password) < 8:
        return templates.TemplateResponse("profile_password.html", {
            "request": request, "user": user, "error": err("pwd_err_short"),
        })

    user.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse("/profile/password?changed=1", 302)
