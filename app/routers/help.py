from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..templates import templates

router = APIRouter()


@router.get("/help")
def help_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("help.html", {"request": request, "user": user})
