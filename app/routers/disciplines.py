import json
from datetime import datetime

from fastapi import APIRouter, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user, require_admin
from .. import models

from ..templates import templates
router = APIRouter()


# --- Dashboard ---

def _home_stats(user, db):
    user_votes = {v.question_id: v.round for v in
                  db.query(models.Vote).filter(models.Vote.teacher_id == user.id).all()}
    pending_all = db.query(models.Question).filter(
        models.Question.status == models.QuestionStatus.pending).all()
    vote_count = sum(
        1 for q in pending_all
        if q.author_id != user.id
        and (q.id not in user_votes or user_votes[q.id] < q.current_round)
    )
    my_questions = db.query(models.Question).filter(
        models.Question.author_id == user.id).all()
    total_active = db.query(models.Question).filter(
        models.Question.status == models.QuestionStatus.active).count()
    return dict(
        vote_count=vote_count,
        my_pending=sum(1 for q in my_questions if q.status == models.QuestionStatus.pending),
        my_active=sum(1 for q in my_questions if q.status == models.QuestionStatus.active),
        my_total=len(my_questions),
        total_active=total_active,
    )


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    return templates.TemplateResponse("home.html", {
        "request": request, "user": user,
        **_home_stats(user, db),
    })


@router.get("/bank")
def bank(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    faculties = db.query(models.Faculty).order_by(models.Faculty.name).all()
    return templates.TemplateResponse("bank.html", {
        "request": request, "user": user, "faculties": faculties,
    })


# --- Faculties ---

@router.get("/faculties/new")
def new_faculty(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    return templates.TemplateResponse("faculty_form.html", {"request": request, "user": user})


@router.post("/faculties")
def create_faculty(request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    require_admin(request, db)
    db.add(models.Faculty(name=name.strip()))
    db.commit()
    return RedirectResponse("/", 302)


@router.get("/faculties/{faculty_id}")
def view_faculty(faculty_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    f = db.get(models.Faculty, faculty_id)
    if not f:
        raise HTTPException(404)
    return templates.TemplateResponse("faculty.html", {"request": request, "user": user, "faculty": f})


@router.get("/faculties/{faculty_id}/edit")
def edit_faculty_form(faculty_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    f = db.get(models.Faculty, faculty_id)
    if not f:
        raise HTTPException(404)
    return templates.TemplateResponse("faculty_form.html", {
        "request": request, "user": user, "faculty": f, "editing": True,
    })


@router.post("/faculties/{faculty_id}/edit")
def update_faculty(faculty_id: int, request: Request, name: str = Form(...), db: Session = Depends(get_db)):
    require_admin(request, db)
    f = db.get(models.Faculty, faculty_id)
    if not f:
        raise HTTPException(404)
    f.name = name.strip()
    db.commit()
    return RedirectResponse(f"/faculties/{faculty_id}", 302)


@router.post("/faculties/{faculty_id}/delete")
def delete_faculty(faculty_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    f = db.get(models.Faculty, faculty_id)
    if f:
        db.delete(f)
        db.commit()
    return RedirectResponse("/", 302)


# --- Disciplines ---

@router.get("/faculties/{faculty_id}/disciplines/new")
def new_discipline(faculty_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    f = db.get(models.Faculty, faculty_id)
    if not f:
        raise HTTPException(404)
    return templates.TemplateResponse("discipline_form.html", {"request": request, "user": user, "faculty": f})


@router.post("/faculties/{faculty_id}/disciplines")
def create_discipline(faculty_id: int, request: Request, name: str = Form(...), code: str = Form(""), db: Session = Depends(get_db)):
    require_admin(request, db)
    db.add(models.Discipline(faculty_id=faculty_id, name=name.strip(), code=code.strip() or None))
    db.commit()
    return RedirectResponse(f"/faculties/{faculty_id}", 302)


@router.get("/disciplines/{discipline_id}")
def view_discipline(discipline_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    d = db.get(models.Discipline, discipline_id)
    if not d:
        raise HTTPException(404)
    return templates.TemplateResponse("discipline.html", {"request": request, "user": user, "discipline": d})


@router.get("/disciplines/{discipline_id}/edit")
def edit_discipline_form(discipline_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    d = db.get(models.Discipline, discipline_id)
    if not d:
        raise HTTPException(404)
    return templates.TemplateResponse("discipline_form.html", {
        "request": request, "user": user, "faculty": d.faculty, "discipline": d, "editing": True,
    })


@router.post("/disciplines/{discipline_id}/edit")
def update_discipline(discipline_id: int, request: Request, name: str = Form(...), code: str = Form(""), db: Session = Depends(get_db)):
    require_admin(request, db)
    d = db.get(models.Discipline, discipline_id)
    if not d:
        raise HTTPException(404)
    d.name = name.strip()
    d.code = code.strip() or None
    db.commit()
    return RedirectResponse(f"/disciplines/{discipline_id}", 302)


@router.post("/disciplines/{discipline_id}/delete")
def delete_discipline(discipline_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    d = db.get(models.Discipline, discipline_id)
    if d:
        faculty_id = d.faculty_id
        db.delete(d)
        db.commit()
        return RedirectResponse(f"/faculties/{faculty_id}", 302)
    return RedirectResponse("/", 302)


# --- Modules ---

@router.get("/disciplines/{discipline_id}/modules/new")
def new_module(discipline_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    d = db.get(models.Discipline, discipline_id)
    if not d:
        raise HTTPException(404)
    next_number = max((m.number for m in d.modules), default=0) + 1
    return templates.TemplateResponse("module_form.html", {
        "request": request, "user": user, "discipline": d, "next_number": next_number,
    })


@router.post("/disciplines/{discipline_id}/modules")
def create_module(discipline_id: int, request: Request, name: str = Form(...), number: int = Form(...), db: Session = Depends(get_db)):
    require_admin(request, db)
    db.add(models.Module(discipline_id=discipline_id, name=name.strip(), number=number))
    db.commit()
    return RedirectResponse(f"/disciplines/{discipline_id}", 302)


@router.get("/modules/{module_id}")
def view_module(module_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)
    return templates.TemplateResponse("module.html", {"request": request, "user": user, "module": m})


@router.get("/modules/{module_id}/edit")
def edit_module_form(module_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)
    return templates.TemplateResponse("module_form.html", {
        "request": request, "user": user, "discipline": m.discipline, "module": m, "editing": True,
    })


@router.post("/modules/{module_id}/edit")
def update_module(module_id: int, request: Request, name: str = Form(...), number: int = Form(...), db: Session = Depends(get_db)):
    require_admin(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)
    m.name = name.strip()
    m.number = number
    db.commit()
    return RedirectResponse(f"/modules/{module_id}", 302)


@router.post("/modules/{module_id}/delete")
def delete_module(module_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    m = db.get(models.Module, module_id)
    if m:
        discipline_id = m.discipline_id
        db.delete(m)
        db.commit()
        return RedirectResponse(f"/disciplines/{discipline_id}", 302)
    return RedirectResponse("/", 302)


# --- Topics ---

@router.get("/modules/{module_id}/topics/new")
def new_topic(module_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)
    next_number = max((t.number for t in m.topics), default=0) + 1
    return templates.TemplateResponse("topic_form.html", {
        "request": request, "user": user, "module": m, "next_number": next_number,
    })


@router.post("/modules/{module_id}/topics")
def create_topic(
    module_id: int, request: Request,
    name: str = Form(...), number: int = Form(...),
    hours_weight: int = Form(1),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    db.add(models.Topic(module_id=module_id, name=name.strip(), number=number,
                        hours_weight=max(1, hours_weight)))
    db.commit()
    return RedirectResponse(f"/modules/{module_id}", 302)


@router.get("/topics/{topic_id}")
def view_topic(topic_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)

    from ..item_analysis import P_BAND_CSS, D_BAND_CSS, p_band, d_band
    # Use cached metrics (populated after result entry) — avoids N+1 on TestResult
    q_metrics = {}
    for q in t.questions:
        fac  = {"mean_p": q.cached_p, "mean_pct": round(q.cached_p * 100, 1) if q.cached_p is not None else None,
                "total_n": q.cached_n_tested, "n_tests": None,
                "band": p_band(q.cached_p) if q.cached_p is not None else None} if q.cached_p is not None \
               else {"n_tests": 0, "mean_p": None, "band": None, "total_n": 0}
        disc = {"mean_d": q.cached_d, "band": d_band(q.cached_d) if q.cached_d is not None else None} \
               if q.cached_d is not None else None
        q_metrics[q.id] = {"fac": fac, "disc": disc}

    return templates.TemplateResponse("topic.html", {
        "request": request, "user": user, "topic": t,
        "q_metrics": q_metrics,
        "P_BAND_CSS": P_BAND_CSS,
        "D_BAND_CSS": D_BAND_CSS,
    })


@router.get("/topics/{topic_id}/edit")
def edit_topic_form(topic_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    return templates.TemplateResponse("topic_form.html", {
        "request": request, "user": user, "module": t.module, "topic": t, "editing": True,
    })


@router.post("/topics/{topic_id}/edit")
def update_topic(topic_id: int, request: Request, name: str = Form(...), number: int = Form(...), hours_weight: int = Form(1), db: Session = Depends(get_db)):
    require_admin(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    t.name = name.strip()
    t.number = number
    t.hours_weight = max(1, hours_weight)
    db.commit()
    return RedirectResponse(f"/topics/{topic_id}", 302)


@router.post("/topics/{topic_id}/delete")
def delete_topic(topic_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    t = db.get(models.Topic, topic_id)
    if t:
        module_id = t.module_id
        db.delete(t)
        db.commit()
        return RedirectResponse(f"/modules/{module_id}", 302)
    return RedirectResponse("/", 302)


@router.get("/topics/{topic_id}/outcomes.json")
def get_outcomes_json(topic_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    return JSONResponse([{"id": lo.id, "text": lo.text} for lo in t.learning_outcomes])


@router.post("/topics/{topic_id}/outcomes")
def add_outcome(topic_id: int, request: Request,
                text: str = Form(...),
                bloom_level: str = Form(""),
                db: Session = Depends(get_db)):
    get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    bloom = models.Difficulty(bloom_level) if bloom_level else None
    db.add(models.TopicLO(topic_id=topic_id, text=text.strip(), bloom_level=bloom))
    db.commit()
    return RedirectResponse(f"/topics/{topic_id}", 302)


@router.get("/topics/{topic_id}/outcomes/{lo_id}/edit")
def edit_outcome_form(topic_id: int, lo_id: int, request: Request,
                      db: Session = Depends(get_db)):
    get_current_user(request, db)
    lo = db.get(models.TopicLO, lo_id)
    if not lo or lo.topic_id != topic_id:
        raise HTTPException(404)
    return templates.TemplateResponse("ilo_edit.html", {
        "request": request,
        "user": get_current_user(request, db),
        "lo": lo,
        "difficulties": list(models.Difficulty),
    })


@router.post("/topics/{topic_id}/outcomes/{lo_id}/edit")
def edit_outcome(topic_id: int, lo_id: int, request: Request,
                 text: str = Form(...),
                 bloom_level: str = Form(""),
                 db: Session = Depends(get_db)):
    get_current_user(request, db)
    lo = db.get(models.TopicLO, lo_id)
    if not lo or lo.topic_id != topic_id:
        raise HTTPException(404)
    lo.text = text.strip()
    lo.bloom_level = models.Difficulty(bloom_level) if bloom_level else None
    db.commit()
    return RedirectResponse(f"/topics/{topic_id}", 302)


@router.post("/topics/{topic_id}/outcomes/{lo_id}/delete")
def delete_outcome(topic_id: int, lo_id: int, request: Request,
                   db: Session = Depends(get_db)):
    require_admin(request, db)
    lo = db.get(models.TopicLO, lo_id)
    if lo and lo.topic_id == topic_id:
        db.delete(lo)
        db.commit()
    return RedirectResponse(f"/topics/{topic_id}", 302)


@router.get("/disciplines/{discipline_id}/structure.json")
def export_discipline_structure(discipline_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    d = db.get(models.Discipline, discipline_id)
    if not d:
        raise HTTPException(404)
    data = [
        {
            "number": m.number,
            "name":   m.name,
            "topics": [
                {
                    "number":           t.number,
                    "name":             t.name,
                    "hours_weight":     t.hours_weight,
                    "is_high_stakes":   t.is_high_stakes,
                    "learning_outcomes": [
                        {"text": lo.text,
                         "bloom_level": lo.bloom_level.value if lo.bloom_level else None}
                        for lo in t.learning_outcomes
                    ],
                }
                for t in m.topics
            ],
        }
        for m in d.modules
    ]
    slug = d.name.replace(" ", "_")[:30]
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename=structure_{slug}.json"},
    )


@router.post("/disciplines/{discipline_id}/import-structure")
async def import_discipline_structure(
    discipline_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    d = db.get(models.Discipline, discipline_id)
    if not d:
        raise HTTPException(404)

    content = await file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return RedirectResponse(f"/disciplines/{discipline_id}?import_error=1", 302)

    if not isinstance(data, list):
        return RedirectResponse(f"/disciplines/{discipline_id}?import_error=1", 302)

    existing_modules = {m.number: m for m in d.modules}
    mc = tc = lc = ms = ts = 0  # created / skipped counters

    for m_raw in data:
        if not isinstance(m_raw, dict):
            continue
        m_num  = m_raw.get("number")
        m_name = (m_raw.get("name") or "").strip()
        if not m_name or m_num is None:
            continue
        try:
            m_num = int(m_num)
        except (TypeError, ValueError):
            continue

        if m_num in existing_modules:
            module = existing_modules[m_num]
            ms += 1
        else:
            module = models.Module(discipline_id=discipline_id, name=m_name, number=m_num)
            db.add(module)
            db.flush()
            existing_modules[m_num] = module
            mc += 1

        existing_topics = {t.number: t for t in module.topics}

        for t_raw in m_raw.get("topics", []):
            if not isinstance(t_raw, dict):
                continue
            t_num  = t_raw.get("number")
            t_name = (t_raw.get("name") or "").strip()
            if not t_name or t_num is None:
                continue
            try:
                t_num = int(t_num)
            except (TypeError, ValueError):
                continue

            if t_num in existing_topics:
                ts += 1
                continue

            topic = models.Topic(
                module_id=module.id,
                name=t_name,
                number=t_num,
                hours_weight=max(1, int(t_raw.get("hours_weight") or 1)),
                is_high_stakes=bool(t_raw.get("is_high_stakes", False)),
            )
            db.add(topic)
            db.flush()
            existing_topics[t_num] = topic
            tc += 1

            for lo_raw in t_raw.get("learning_outcomes", []):
                if isinstance(lo_raw, str):
                    lo_text, bloom = lo_raw.strip(), None
                elif isinstance(lo_raw, dict):
                    lo_text = (lo_raw.get("text") or "").strip()
                    try:
                        bloom = models.Difficulty(lo_raw.get("bloom_level")) if lo_raw.get("bloom_level") else None
                    except ValueError:
                        bloom = None
                else:
                    continue
                if lo_text:
                    db.add(models.TopicLO(topic_id=topic.id, text=lo_text, bloom_level=bloom))
                    lc += 1

    db.commit()
    return RedirectResponse(
        f"/disciplines/{discipline_id}?im={mc}&it={tc}&il={lc}&sm={ms}&st={ts}", 302
    )


@router.post("/topics/{topic_id}/toggle-high-stakes")
def toggle_high_stakes(topic_id: int, request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    t.is_high_stakes = not t.is_high_stakes
    db.commit()
    return RedirectResponse(f"/modules/{t.module_id}", 302)


@router.get("/topics/{topic_id}/export.json")
def export_topic(topic_id: int, request: Request, db: Session = Depends(get_db)):
    get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    data = {
        "version": 1,
        "source_topic": t.name,
        "exported_at": datetime.utcnow().isoformat(),
        "learning_outcomes": [lo.text for lo in t.learning_outcomes],
        "questions": [
            {
                "text": q.text,
                "model_answer": q.model_answer,
                "proposed_difficulty": q.proposed_difficulty.value,
                "question_type": q.question_type.value if q.question_type else None,
                "learning_objective": q.learning_objective,
            }
            for q in t.questions
            if q.status.value in ("active", "pending")
        ],
    }
    filename = f"topic_{topic_id}.json"
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/topics/{topic_id}/import")
async def import_topic(
    topic_id: int, request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)

    content = await file.read()
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON file")

    if not isinstance(data, dict):
        raise HTTPException(400, "Invalid file format")

    existing_lo_texts = {lo.text for lo in t.learning_outcomes}
    lo_count = 0
    for text in data.get("learning_outcomes", []):
        text = (text or "").strip()
        if text and text not in existing_lo_texts:
            db.add(models.TopicLO(topic_id=topic_id, text=text))
            existing_lo_texts.add(text)
            lo_count += 1

    q_count = 0
    for q in data.get("questions", []):
        text = (q.get("text") or "").strip()
        if not text:
            continue
        try:
            diff = models.Difficulty(q.get("proposed_difficulty", "B"))
        except ValueError:
            diff = models.Difficulty.B
        qt = None
        if q.get("question_type"):
            try:
                qt = models.QuestionType(q["question_type"])
            except ValueError:
                pass
        db.add(models.Question(
            topic_id=topic_id,
            author_id=user.id,
            text=text,
            model_answer=(q.get("model_answer") or "").strip() or None,
            proposed_difficulty=diff,
            question_type=qt,
            learning_objective=(q.get("learning_objective") or "").strip() or None,
            status=models.QuestionStatus.pending,
        ))
        q_count += 1

    db.commit()
    return RedirectResponse(
        f"/topics/{topic_id}?imported_lo={lo_count}&imported_q={q_count}", 302
    )
