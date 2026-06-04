import json
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session
from collections import defaultdict

from ..database import get_db
from ..auth import get_current_user
from ..draw import draw_multiple_variants, build_blueprint_from_matrix, recently_used_ids, draw_topic_quiz
from ..export import export_test_docx, export_test_pdf
from .. import models
from ..templates import templates

router = APIRouter()


@router.get("/modules/{module_id}/tests/new")
def new_test(module_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)
    return templates.TemplateResponse("test_form.html", {
        "request": request, "user": user, "module": m,
    })


@router.post("/modules/{module_id}/tests")
async def create_test(module_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)

    form = await request.form()
    _lang_t = request.session.get("lang", "uk")
    _default_test_name = f"Test — {m.name}" if _lang_t == "en" else f"Тест — {m.name}"
    test_name    = form.get("test_name", _default_test_name).strip()
    avoid_recent = form.get("avoid_recent") == "on"
    try:
        total_questions = max(1, int(form.get("total_questions", "30")))
    except ValueError:
        total_questions = 30
    try:
        n_variants = max(1, min(3, int(form.get("n_variants", "1"))))
    except ValueError:
        n_variants = 1

    blueprint   = build_blueprint_from_matrix(m, total_questions)
    from ..config import get_settings as _gs
    horizon     = _gs(db).get("exposure_horizon_n", 3)
    exclude_ids = recently_used_ids(module_id, last_n=horizon, db=db) if avoid_recent else []
    variants    = draw_multiple_variants(m, blueprint, db, n_variants,
                                         exclude_ids=exclude_ids, horizon=horizon)

    if not variants:
        _lang = request.session.get("lang", "uk")
        _err = "Not enough active questions for the requested blueprint." if _lang == "en" else "Недостатньо активних питань для заданого шаблону."
        return templates.TemplateResponse("test_form.html", {
            "request": request, "user": user, "module": m,
            "error": _err,
        })

    tests = []
    for i, questions in enumerate(variants):
        _lang = request.session.get("lang", "uk")
        suffix = (f" — Variant {i + 1}" if _lang == "en" else f" — Варіант {i + 1}") if len(variants) > 1 else ""
        test = models.Test(
            name=f"{test_name}{suffix}",
            module_id=module_id,
            created_by=user.id,
            variant_label=str(i + 1) if len(variants) > 1 else None,
        )
        db.add(test)
        db.flush()
        tests.append(test)
        for order, q in enumerate(questions, start=1):
            db.add(models.TestQuestion(test_id=test.id, question_id=q.id, order=order))

    if len(tests) > 1:
        batch_id = tests[0].id
        for t in tests:
            t.batch_id = batch_id

    db.commit()

    if len(tests) == 1:
        return RedirectResponse(f"/tests/{tests[0].id}", 302)
    return RedirectResponse(f"/modules/{module_id}/tests", 302)


@router.get("/tests/{test_id}")
def view_test(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    test = db.get(models.Test, test_id)
    if not test:
        raise HTTPException(404)

    # Siblings in same batch
    siblings = []
    if test.batch_id:
        siblings = db.query(models.Test).filter(
            models.Test.batch_id == test.batch_id,
            models.Test.id != test.id,
        ).order_by(models.Test.id).all()

    # Per-question facility from results
    results_map = {r.question_id: r for r in
                   db.query(models.TestResult).filter(models.TestResult.test_id == test_id).all()}

    # LO coverage: for each topic, which LOs are hit by question.learning_objective
    covered_texts = {
        tq.question.learning_objective
        for tq in test.test_questions
        if tq.question.learning_objective
    }
    topic_ids_ordered = []
    seen = set()
    for tq in sorted(test.test_questions, key=lambda x: x.question.topic_id):
        tid = tq.question.topic_id
        if tid not in seen:
            topic_ids_ordered.append(tid)
            seen.add(tid)

    lo_coverage = []
    for tid in topic_ids_ordered:
        topic = db.get(models.Topic, tid)
        if not topic or not topic.learning_outcomes:
            continue
        los = [{"lo": lo, "covered": lo.text in covered_texts}
               for lo in topic.learning_outcomes]
        lo_coverage.append({
            "topic": topic,
            "los": los,
            "n_covered": sum(1 for x in los if x["covered"]),
            "n_total": len(los),
        })

    from ..item_analysis import kr20_band, KR20_CSS
    from ..config import get_settings
    settings = get_settings(db)
    pass_pct = settings.get("pass_threshold_pct", 75)

    # Use stored values when available; fall back to live calculation if results
    # were entered before the cache columns existed (legacy rows)
    kr20_val = test.kr20
    exp_pass = test.exp_pass_rate
    if kr20_val is None and test.result_sd:
        from ..item_analysis import kr20, expected_pass_rate
        p_values = [
            r.correct_count / r.total_students
            for r in db.query(models.TestResult).filter(models.TestResult.test_id == test_id).all()
            if r.total_students and r.total_students > 0
        ]
        kr20_val = kr20(p_values, test.result_sd)
        p_bm = [
            results_map[tq.question_id].correct_count / results_map[tq.question_id].total_students
            for tq in test.test_questions
            if tq.question_id in results_map
            and results_map[tq.question_id].total_students
            and (tq.question.final_difficulty or tq.question.proposed_difficulty).value in ("B", "M")
        ]
        exp_pass = expected_pass_rate(p_bm, pass_pct)

    kr20_css = KR20_CSS.get(kr20_band(kr20_val), "bg-secondary") if kr20_val is not None else None
    kr20_bnd = kr20_band(kr20_val) if kr20_val is not None else None

    return templates.TemplateResponse("test.html", {
        "request": request, "user": user, "test": test,
        "siblings": siblings, "results_map": results_map,
        "lo_coverage": lo_coverage,
        "kr20_val":  kr20_val,
        "kr20_css":  kr20_css,
        "kr20_band": kr20_bnd,
        "pass_pct":  pass_pct,
        "exp_pass":  exp_pass,
    })


@router.get("/tests/{test_id}/export")
def export_test(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    test = db.get(models.Test, test_id)
    if not test:
        raise HTTPException(404)
    if test.created_by != user.id and user.role != models.Role.admin:
        raise HTTPException(403)
    from ..config import get_org_settings, get_settings
    org = get_org_settings(db)
    lang = request.session.get("lang", "uk")
    pass_pct = get_settings(db).get("pass_threshold_pct", 75)
    content  = export_test_docx(test, org=org, lang=lang, pass_pct=pass_pct)
    filename = f"test_{test_id}.docx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/tests/{test_id}/export.pdf")
def export_test_as_pdf(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    test = db.get(models.Test, test_id)
    if not test:
        raise HTTPException(404)
    if test.created_by != user.id and user.role != models.Role.admin:
        raise HTTPException(403)
    from ..config import get_org_settings, get_settings
    org = get_org_settings(db)
    lang = request.session.get("lang", "uk")
    pass_pct = get_settings(db).get("pass_threshold_pct", 75)
    content  = export_test_pdf(test, org=org, lang=lang, pass_pct=pass_pct)
    filename = f"test_{test_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/tests/{test_id}/results")
def test_results_form(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    test = db.get(models.Test, test_id)
    if not test:
        raise HTTPException(404)
    if test.created_by != user.id and user.role != models.Role.admin:
        raise HTTPException(403)
    existing = {r.question_id: r for r in
                db.query(models.TestResult).filter(models.TestResult.test_id == test_id).all()}
    return templates.TemplateResponse("test_results.html", {
        "request": request, "user": user, "test": test, "existing": existing,
    })


@router.post("/tests/{test_id}/results")
async def save_test_results(test_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    test = db.get(models.Test, test_id)
    if not test:
        raise HTTPException(404)
    # H2: only test creator or admin can save results
    if test.created_by != user.id and user.role != models.Role.admin:
        raise HTTPException(403)

    import math as _math
    form  = await request.form()
    try:
        total = max(0, int(form.get("total_students", 0) or 0))
    except (ValueError, TypeError):
        total = 0
    group_n = max(1, _math.floor(total * 0.27)) if total >= 6 else None

    # Test-level stats for KR-20
    try:
        score_mean = float(form.get("score_mean") or "")
        test.result_mean = round(score_mean, 3)
    except ValueError:
        pass
    try:
        score_sd = float(form.get("score_sd") or "")
        if score_sd > 0:
            test.result_sd = round(score_sd, 3)
    except ValueError:
        pass

    for tq in test.test_questions:
        qid = tq.question_id
        try:
            correct = max(0, min(total, int(form.get(f"correct_{qid}", 0) or 0)))
        except (ValueError, TypeError):
            correct = 0

        # Optional discrimination data
        upper_raw = form.get(f"upper_{qid}", "").strip()
        lower_raw = form.get(f"lower_{qid}", "").strip()
        upper_correct = None
        lower_correct = None
        if upper_raw and group_n:
            try:
                upper_correct = max(0, min(group_n, int(upper_raw)))
            except ValueError:
                pass
        if lower_raw and group_n:
            try:
                lower_correct = max(0, min(group_n, int(lower_raw)))
            except ValueError:
                pass

        existing = db.query(models.TestResult).filter(
            models.TestResult.test_id == test_id,
            models.TestResult.question_id == qid,
        ).first()
        if existing:
            existing.correct_count  = correct
            existing.total_students = total
            if upper_correct is not None:
                existing.upper_correct = upper_correct
            if lower_correct is not None:
                existing.lower_correct = lower_correct
        else:
            db.add(models.TestResult(
                test_id=test_id, question_id=qid,
                correct_count=correct, total_students=total,
                upper_correct=upper_correct, lower_correct=lower_correct,
            ))
    db.commit()

    # Refresh cached metrics on each question and on the test itself
    from ..item_analysis import refresh_question_cache, refresh_test_cache
    db.refresh(test)
    for tq in test.test_questions:
        db.refresh(tq.question)
        refresh_question_cache(tq.question, db)
    refresh_test_cache(test, db)
    db.commit()

    return RedirectResponse(f"/tests/{test_id}", 302)


def _quiz_lo_stats(topic) -> list:
    """Per-ILO count of active questions — shared by GET and error re-render."""
    stats = []
    for lo in topic.learning_outcomes:
        count = sum(
            1 for q in topic.questions
            if q.status == models.QuestionStatus.active
            and q.learning_outcome_id == lo.id
        )
        stats.append({"lo": lo, "count": count})
    return stats


@router.get("/topics/{topic_id}/quiz/new")
def new_quiz(topic_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise HTTPException(404)
    return templates.TemplateResponse("quiz_form.html", {
        "request": request, "user": user,
        "topic": topic, "lo_stats": _quiz_lo_stats(topic),
    })


@router.post("/topics/{topic_id}/quizzes")
async def create_quiz(topic_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    topic = db.get(models.Topic, topic_id)
    if not topic:
        raise HTTPException(404)
    if not topic.learning_outcomes:
        raise HTTPException(400, "Topic has no learning outcomes")

    form = await request.form()
    quiz_name = form.get("quiz_name", "").strip()

    # Build per-ILO draw counts from form fields lo_{id}
    per_lo_counts = {}
    for lo in topic.learning_outcomes:
        try:
            n = max(0, int(form.get(f"lo_{lo.id}", 1) or 1))
        except (ValueError, TypeError):
            n = 1
        per_lo_counts[lo.id] = n

    questions, missing = draw_topic_quiz(topic, db, per_lo_counts=per_lo_counts)
    if not questions:
        return templates.TemplateResponse("quiz_form.html", {
            "request": request, "user": user,
            "topic": topic, "lo_stats": _quiz_lo_stats(topic),
            "error": "no_questions",
        }, status_code=422)

    _lang = request.session.get("lang", "uk")
    _default = (f"Quiz — Topic {topic.number}. {topic.name}"
                if _lang == "en" else
                f"Поточний тест — Тема {topic.number}. {topic.name}")
    quiz = models.Test(
        name=quiz_name or _default,
        module_id=topic.module_id,
        topic_id=topic_id,
        is_quiz=True,
        created_by=user.id,
    )
    db.add(quiz)
    db.flush()
    for order, q in enumerate(questions, start=1):
        db.add(models.TestQuestion(test_id=quiz.id, question_id=q.id, order=order))
    db.commit()
    return RedirectResponse(f"/tests/{quiz.id}", 302)


@router.get("/modules/{module_id}/tests")
def list_tests(module_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    m = db.get(models.Module, module_id)
    if not m:
        raise HTTPException(404)

    tests = (db.query(models.Test)
               .filter(models.Test.module_id == module_id)
               .order_by(models.Test.created_at.desc())
               .all())

    # Group into batches (ungrouped tests use own id as key)
    batch_map = defaultdict(list)
    for t in tests:
        batch_map[t.batch_id if t.batch_id else t.id].append(t)

    batches = sorted(batch_map.values(), key=lambda b: b[0].created_at, reverse=True)

    return templates.TemplateResponse("tests_list.html", {
        "request": request, "user": user, "module": m, "batches": batches,
    })
