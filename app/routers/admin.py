import csv
import io
from datetime import datetime

from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import require_admin, get_current_user, hash_password
from .. import models
from ..config import (
    get_settings, save_settings, SETTINGS_SCHEMA, DEFAULTS,
    get_org_settings, save_org_settings, ORG_SETTINGS_SCHEMA,
)
from ..templates import templates

router = APIRouter(prefix="/admin")


@router.get("/teachers")
def list_teachers(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    teachers = db.query(models.User).order_by(models.User.name).all()
    new_teacher = request.session.pop("new_teacher", None)
    return templates.TemplateResponse("admin_teachers.html", {
        "request": request, "user": user, "teachers": teachers,
        "new_teacher": new_teacher,
    })


@router.post("/teachers")
def create_teacher(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    role: str = Form("teacher"),
    db: Session = Depends(get_db),
):
    user = require_admin(request, db)
    if db.query(models.User).filter(models.User.email == email).first():
        teachers = db.query(models.User).order_by(models.User.name).all()
        lang = request.session.get("lang", "uk")
        error = f"Email {email} is already registered." if lang == "en" else f"Email {email} вже зареєстрований."
        return templates.TemplateResponse("admin_teachers.html", {
            "request": request, "user": user, "teachers": teachers,
            "error": error,
        })
    name_clean  = name.strip()
    email_clean = email.strip().lower()
    db.add(models.User(
        name=name_clean,
        email=email_clean,
        password_hash=hash_password(password),
        role=models.Role(role),
    ))
    db.commit()

    lang     = request.session.get("lang", "uk")
    base_url = str(request.base_url).rstrip("/")
    if lang == "en":
        msg = (
            f"Hello, {name_clean}!\n\n"
            f"Your account has been created in the Question Bank.\n\n"
            f"🔗 {base_url}\n"
            f"📧 Email: {email_clean}\n"
            f"🔑 Password: {password}\n\n"
            f"Please change your password after your first login "
            f"(key icon ​🔑 in the sidebar)."
        )
    else:
        msg = (
            f"Вітаємо, {name_clean}!\n\n"
            f"Вам створено обліковий запис у системі «Банк питань».\n\n"
            f"🔗 {base_url}\n"
            f"📧 Email: {email_clean}\n"
            f"🔑 Пароль: {password}\n\n"
            f"Після першого входу рекомендуємо змінити пароль у профілі "
            f"(іконка ключа 🔑 у бічному меню)."
        )
    request.session["new_teacher"] = {"name": name_clean, "message": msg}
    return RedirectResponse("/admin/teachers", 302)


@router.post("/teachers/{teacher_id}/delete")
def delete_teacher(teacher_id: int, request: Request, db: Session = Depends(get_db)):
    current = require_admin(request, db)
    if current.id == teacher_id:
        raise HTTPException(400, detail="Cannot delete your own account")
    t = db.get(models.User, teacher_id)
    if not t:
        return RedirectResponse("/admin/teachers", 302)
    # C6: prevent orphaned questions/votes — block if the teacher has any content
    has_questions = db.query(models.Question).filter(
        models.Question.author_id == teacher_id
    ).first()
    has_votes = db.query(models.Vote).filter(
        models.Vote.teacher_id == teacher_id
    ).first()
    if has_questions or has_votes:
        lang = request.session.get("lang", "uk")
        teachers = db.query(models.User).order_by(models.User.name).all()
        error = (
            "Cannot delete this account: the teacher has authored questions or votes. "
            "Retire their questions first."
            if lang == "en" else
            "Неможливо видалити: викладач має питання або голоси. "
            "Спочатку архівуйте їх питання."
        )
        return templates.TemplateResponse("admin_teachers.html", {
            "request": request, "user": current, "teachers": teachers, "error": error,
        }, status_code=409)
    db.delete(t)
    db.commit()
    return RedirectResponse("/admin/teachers", 302)


@router.get("/settings")
def admin_settings(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    settings = get_settings(db)
    org_settings = get_org_settings(db)
    return templates.TemplateResponse("admin_settings.html", {
        "request": request, "user": user,
        "settings": settings, "schema": SETTINGS_SCHEMA,
        "org_settings": org_settings, "org_schema": ORG_SETTINGS_SCHEMA,
    })


@router.post("/settings")
async def save_admin_settings(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form = await request.form()
    data = {}
    for key, meta in SETTINGS_SCHEMA.items():
        try:
            data[key] = int(form.get(key, meta["default"]))
        except ValueError:
            data[key] = meta["default"]
    save_settings(db, data)
    return RedirectResponse("/admin/settings?saved=1", 302)


@router.post("/org-settings")
async def save_org_settings_route(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    form = await request.form()
    save_org_settings(db, dict(form))
    # Bust the org cache on the current request so the redirect reflects the new values
    if hasattr(request.state, "_org_cache"):
        del request.state._org_cache
    return RedirectResponse("/admin/settings?saved=1", 302)


def _csv_response(filename: str, headers: list, rows):
    """Stream a UTF-8 CSV file with BOM so Excel opens it correctly."""
    buf = io.StringIO()
    buf.write("﻿")          # UTF-8 BOM for Excel
    w = csv.writer(buf)
    w.writerow(headers)
    w.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export")
def export_page(request: Request, db: Session = Depends(get_db)):
    user = require_admin(request, db)
    q_total  = db.query(models.Question).count()
    v_total  = db.query(models.Vote).count()
    rs_total = db.query(models.VoteRoundSummary).count()
    tr_total = db.query(models.TestResult).count()
    return templates.TemplateResponse("admin_export.html", {
        "request": request, "user": user,
        "q_total": q_total, "v_total": v_total,
        "rs_total": rs_total, "tr_total": tr_total,
    })


@router.get("/export/questions")
def export_questions(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    questions = db.query(models.Question).order_by(models.Question.id).all()
    headers = [
        "question_id", "status", "author", "programme", "discipline", "module", "topic",
        "ilo_text", "ilo_bloom_level", "proposed_difficulty", "final_difficulty",
        "question_type", "current_round", "created_at",
        "cached_p", "cached_n_tested", "cached_d", "cached_rec",
        "text",
    ]
    rows = []
    for q in questions:
        topic   = q.topic
        module  = topic.module
        disc    = module.discipline
        prog    = disc.faculty
        lo      = q.learning_outcome
        rows.append([
            q.id,
            q.status.value,
            q.author.name if q.author else "",
            prog.name if prog else "",
            disc.name,
            module.name,
            topic.name,
            lo.text if lo else "",
            lo.bloom_level.value if (lo and lo.bloom_level) else "",
            q.proposed_difficulty.value,
            q.final_difficulty.value if q.final_difficulty else "",
            q.question_type.value if q.question_type else "",
            q.current_round,
            q.created_at.strftime("%Y-%m-%d %H:%M") if q.created_at else "",
            q.cached_p,
            q.cached_n_tested,
            q.cached_d,
            q.cached_rec or "",
            q.text,
        ])
    stamp = datetime.now().strftime("%Y%m%d")
    return _csv_response(f"questions_{stamp}.csv", headers, rows)


@router.get("/export/vote-rounds")
def export_vote_rounds(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    summaries = (db.query(models.VoteRoundSummary)
                   .order_by(models.VoteRoundSummary.question_id,
                             models.VoteRoundSummary.round)
                   .all())
    headers = [
        "summary_id", "question_id", "round", "outcome",
        "n_votes", "approval_pct",
        "mean_wording", "sd_wording",
        "mean_lo", "sd_lo",
        "mean_bloom", "sd_bloom",
        "mean_answer", "sd_answer",
        "mean_accuracy", "sd_accuracy",
        "diff_consensus_pct", "closed_at",
    ]
    rows = [
        [
            s.id, s.question_id, s.round, s.outcome,
            s.n_votes, s.approval_pct,
            s.mean_wording, s.sd_wording,
            s.mean_lo, s.sd_lo,
            s.mean_bloom, s.sd_bloom,
            s.mean_answer, s.sd_answer,
            s.mean_accuracy, s.sd_accuracy,
            s.diff_consensus_pct,
            s.closed_at.strftime("%Y-%m-%d %H:%M") if s.closed_at else "",
        ]
        for s in summaries
    ]
    stamp = datetime.now().strftime("%Y%m%d")
    return _csv_response(f"vote_round_summaries_{stamp}.csv", headers, rows)


@router.get("/export/test-results")
def export_test_results(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    results = (db.query(models.TestResult)
                 .order_by(models.TestResult.test_id, models.TestResult.question_id)
                 .all())
    headers = [
        "test_id", "test_name", "test_date", "module",
        "test_kr20", "test_exp_pass_rate",
        "question_id", "difficulty", "ilo_text",
        "correct_count", "total_students", "facility_p",
        "upper_correct", "lower_correct", "ebel_d",
    ]
    rows = []
    for r in results:
        test = r.test
        q    = r.question
        lo   = q.learning_outcome if q else None
        facility_p = round(r.correct_count / r.total_students, 4) if r.total_students else None
        ebel_d = None
        if r.upper_correct is not None and r.lower_correct is not None and r.total_students:
            import math
            gn = max(1, math.floor(r.total_students * 0.27))
            ebel_d = round((min(r.upper_correct, gn) - min(r.lower_correct, gn)) / gn, 4)
        rows.append([
            test.id if test else "",
            test.name if test else "",
            test.created_at.strftime("%Y-%m-%d") if (test and test.created_at) else "",
            test.module.name if (test and test.module) else "",
            test.kr20 if test else "",
            test.exp_pass_rate if test else "",
            q.id if q else r.question_id,
            (q.final_difficulty or q.proposed_difficulty).value if q else "",
            lo.text if lo else "",
            r.correct_count,
            r.total_students,
            facility_p,
            r.upper_correct,
            r.lower_correct,
            ebel_d,
        ])
    stamp = datetime.now().strftime("%Y%m%d")
    return _csv_response(f"test_results_{stamp}.csv", headers, rows)


@router.get("/export/votes-raw")
def export_votes_raw(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    votes = (db.query(models.Vote)
               .order_by(models.Vote.question_id, models.Vote.round, models.Vote.created_at)
               .all())
    headers = [
        "vote_id", "question_id", "reviewer", "round",
        "approve", "difficulty_vote",
        "crit_wording", "crit_lo", "crit_bloom", "crit_answer", "crit_accuracy",
        "comment", "created_at",
    ]
    rows = [
        [
            v.id, v.question_id,
            v.teacher.name if v.teacher else "",
            v.round,
            1 if v.approve else 0,
            v.difficulty_vote.value if v.difficulty_vote else "",
            v.crit_wording, v.crit_lo, v.crit_bloom, v.crit_answer, v.crit_accuracy,
            (v.comment or "").replace("\n", " "),
            v.created_at.strftime("%Y-%m-%d %H:%M") if v.created_at else "",
        ]
        for v in votes
    ]
    stamp = datetime.now().strftime("%Y%m%d")
    return _csv_response(f"votes_raw_{stamp}.csv", headers, rows)


@router.post("/teachers/{teacher_id}/reset-password")
async def reset_teacher_password(
    teacher_id: int, request: Request,
    new_password: str = Form(...),
    db: Session = Depends(get_db),
):
    require_admin(request, db)
    teacher = db.get(models.User, teacher_id)
    if not teacher:
        raise HTTPException(404)
    lang = request.session.get("lang", "uk")
    if len(new_password) < 8:
        err = "Password must be at least 8 characters." if lang == "en" else "Пароль має містити мінімум 8 символів."
        teachers = db.query(models.User).order_by(models.User.name).all()
        return templates.TemplateResponse("admin_teachers.html", {
            "request": request, "user": db.get(models.User, request.session["user_id"]),
            "teachers": teachers, "reset_error": err, "reset_target_id": teacher_id,
        })
    teacher.password_hash = hash_password(new_password)
    db.commit()
    return RedirectResponse("/admin/teachers?reset=1", 302)
