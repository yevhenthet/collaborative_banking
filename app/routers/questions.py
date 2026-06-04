from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..draw import activate_question
from ..config import get_settings
from .. import models
from ..templates import templates

router = APIRouter()


@router.get("/vote/count")
def vote_count(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse({"count": 0})
    voted = {v.question_id: v.round for v in
             db.query(models.Vote).filter(models.Vote.teacher_id == user_id).all()}
    pending = db.query(models.Question).filter(
        models.Question.status == models.QuestionStatus.pending).all()
    count = sum(
        1 for q in pending
        if q.id not in voted or voted[q.id] < q.current_round
    )
    return JSONResponse({"count": count})


@router.get("/vote")
def vote_queue(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    settings = get_settings(db)
    quorum = settings["quorum"]

    # Map question_id → user's vote for current round
    user_votes = {
        v.question_id: v
        for v in db.query(models.Vote).filter(models.Vote.teacher_id == user.id).all()
    }
    pending = (
        db.query(models.Question)
        .filter(models.Question.status == models.QuestionStatus.pending)
        .order_by(models.Question.created_at)
        .all()
    )
    to_vote = [q for q in pending
               if q.author_id != user.id
               and (q.id not in user_votes or user_votes[q.id].round < q.current_round)]
    voted   = [q for q in pending
               if q.author_id != user.id
               and q.id in user_votes and user_votes[q.id].round == q.current_round]

    # Unique disciplines and topics from to_vote for filter dropdowns
    disc_map = {}
    topic_map = {}
    for q in to_vote:
        d = q.topic.module.discipline
        disc_map[d.id] = d
        t = q.topic
        topic_map[t.id] = {"topic": t, "discipline_id": d.id}
    filter_disciplines = sorted(disc_map.values(), key=lambda d: (d.faculty.name, d.name))
    filter_topics = sorted(topic_map.values(), key=lambda x: (x["discipline_id"], x["topic"].number))
    multi_faculty = len({d.faculty_id for d in filter_disciplines}) > 1

    return templates.TemplateResponse("vote_queue.html", {
        "request": request, "user": user,
        "to_vote": to_vote, "voted": voted,
        "quorum": quorum, "difficulties": list(models.Difficulty),
        "user_votes": user_votes,
        "filter_disciplines": filter_disciplines,
        "filter_topics": filter_topics,
        "multi_faculty": multi_faculty,
    })


@router.get("/topics/{topic_id}/questions/new")
def new_question(topic_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    return templates.TemplateResponse("question_form.html", {
        "request": request, "user": user, "topic": t,
        "difficulties": list(models.Difficulty),
        "question_types": list(models.QuestionType),
        "topic_los": t.learning_outcomes,
    })


@router.post("/topics/{topic_id}/questions")
def create_question(
    topic_id: int, request: Request,
    text: str = Form(...),
    proposed_difficulty: str = Form(...),
    question_type: str = Form(""),
    learning_outcome_id: str = Form(""),
    model_answer: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    t = db.get(models.Topic, topic_id)
    if not t:
        raise HTTPException(404)
    lo_id = int(learning_outcome_id) if learning_outcome_id.strip() else None
    _lang = request.session.get("lang", "uk")
    if not lo_id and t.learning_outcomes:
        _err = "Select a learning outcome (ILO)." if _lang == "en" else "Оберіть навчальний результат (ILO)."
        return templates.TemplateResponse("question_form.html", {
            "request": request, "user": user, "topic": t,
            "difficulties": list(models.Difficulty),
            "question_types": list(models.QuestionType),
            "topic_los": t.learning_outcomes,
            "error": _err,
        }, status_code=422)
    lo_text = None
    if lo_id:
        lo = db.get(models.TopicLO, lo_id)
        if not lo or lo.topic_id != topic_id:
            raise HTTPException(400, "Invalid learning outcome for this topic")
        lo_text = lo.text
    try:
        _difficulty = models.Difficulty(proposed_difficulty)
        _qtype = models.QuestionType(question_type) if question_type else None
    except ValueError:
        raise HTTPException(422, "Invalid difficulty or question type value")
    db.add(models.Question(
        topic_id=topic_id,
        author_id=user.id,
        text=text.strip(),
        proposed_difficulty=_difficulty,
        question_type=_qtype,
        learning_outcome_id=lo_id,
        learning_objective=lo_text,
        model_answer=model_answer.strip() or None,
        status=models.QuestionStatus.pending,
    ))
    db.commit()
    return RedirectResponse(f"/topics/{topic_id}", 302)


@router.get("/questions/{question_id}")
def view_question(question_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    q = db.get(models.Question, question_id)
    if not q:
        raise HTTPException(404)
    my_vote = next((v for v in q.votes
                    if v.teacher_id == user.id and v.round == q.current_round), None)

    from ..item_analysis import facility_stats, discrimination_stats, review_profile, item_recommendation, P_BAND_CSS, P_BAND_ICON, D_BAND_CSS, D_BAND_ICON

    results       = q.results
    last_round    = max((v.round for v in q.votes), default=q.current_round)
    current_votes = [v for v in q.votes if v.round == last_round]
    fac      = facility_stats(results)
    disc     = discrimination_stats(results)
    rev      = review_profile(current_votes)
    rec      = item_recommendation(fac, disc, rev, final_difficulty=q.final_difficulty)

    settings = get_settings(db)
    horizon  = settings.get("exposure_horizon_n", 3)

    # Exposure: total uses + uses within last `horizon` module tests (H7 fix)
    total_uses = len(q.test_questions)
    from ..draw import recently_used_ids as _recent_ids
    recent_id_set = set(_recent_ids(q.topic.module_id, horizon, db))
    recent_uses = sum(
        1 for tq in q.test_questions
        if not tq.test.is_quiz and tq.test_id in recent_id_set
    )
    # Revision snapshots keyed by round
    revisions_map = {r.round: r for r in q.revisions}

    return templates.TemplateResponse("question.html", {
        "request": request, "user": user, "question": q,
        "my_vote": my_vote, "difficulties": list(models.Difficulty),
        "question_types": list(models.QuestionType),
        "quorum":         settings["quorum"],
        "fac":            fac,
        "disc":           disc,
        "rev":            rev,
        "rec":            rec,
        "revisions_map":  revisions_map,
        "total_uses":     total_uses,
        "recent_uses":    recent_uses,
        "exposure_horizon": horizon,
        "P_BAND_CSS":  P_BAND_CSS,
        "P_BAND_ICON": P_BAND_ICON,
        "D_BAND_CSS":  D_BAND_CSS,
        "D_BAND_ICON": D_BAND_ICON,
        "facility":  fac.get("mean_pct"),
        "n_tests":   fac.get("n_tests", 0),
    })


@router.post("/questions/{question_id}/vote")
def vote_question(
    question_id: int, request: Request,
    approve: str = Form(...),
    difficulty_vote: str = Form(...),
    comment: str = Form(""),
    next_url: str = Form(""),
    crit_wording: str = Form(""),
    crit_lo: str = Form(""),
    crit_bloom: str = Form(""),
    crit_answer: str = Form(""),
    crit_accuracy: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    q = db.get(models.Question, question_id)
    # C4: only pending questions can be voted on
    if not q or q.status != models.QuestionStatus.pending:
        raise HTTPException(404)
    if q.author_id == user.id:
        raise HTTPException(404)

    # H4: validate enum values before writing
    try:
        _diff_vote = models.Difficulty(difficulty_vote)
    except ValueError:
        raise HTTPException(422, "Invalid difficulty value")

    def _int(v):
        try: return int(v) if v else None
        except ValueError: return None

    criteria = dict(
        crit_wording=_int(crit_wording),
        crit_lo=_int(crit_lo),
        crit_bloom=_int(crit_bloom),
        crit_answer=_int(crit_answer),
        crit_accuracy=_int(crit_accuracy),
    )

    existing = next((v for v in q.votes
                     if v.teacher_id == user.id and v.round == q.current_round), None)
    if existing:
        existing.approve = approve == "yes"
        existing.difficulty_vote = _diff_vote
        existing.comment = comment.strip() or None
        for k, v in criteria.items():
            if v is not None:
                setattr(existing, k, v)
    else:
        db.add(models.Vote(
            question_id=question_id,
            teacher_id=user.id,
            approve=approve == "yes",
            difficulty_vote=_diff_vote,
            comment=comment.strip() or None,
            round=q.current_round,
            **{k: v for k, v in criteria.items() if v is not None},
        ))
    db.commit()
    db.refresh(q)
    activate_question(q, db)

    redirect = next_url if next_url.startswith("/") else f"/questions/{question_id}"
    return RedirectResponse(redirect, 302)


@router.get("/questions/{question_id}/edit")
def edit_question_form(question_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    q = db.get(models.Question, question_id)
    if not q:
        raise HTTPException(404)
    if user.role != models.Role.admin and q.author_id != user.id:
        raise HTTPException(403)
    return templates.TemplateResponse("question_edit.html", {
        "request": request, "user": user, "question": q,
        "difficulties": list(models.Difficulty),
        "question_types": list(models.QuestionType),
        "topic_los": q.topic.learning_outcomes,
    })


@router.post("/questions/{question_id}/edit")
def edit_question(
    question_id: int, request: Request,
    text: str = Form(...),
    proposed_difficulty: str = Form(...),
    question_type: str = Form(""),
    learning_outcome_id: str = Form(""),
    model_answer: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    q = db.get(models.Question, question_id)
    if not q:
        raise HTTPException(404)
    if user.role != models.Role.admin and q.author_id != user.id:
        raise HTTPException(403)

    lo_id = int(learning_outcome_id) if learning_outcome_id.strip() else None
    _lang = request.session.get("lang", "uk")
    if not lo_id and q.topic.learning_outcomes:
        _err = "Select a learning outcome (ILO)." if _lang == "en" else "Оберіть навчальний результат (ILO)."
        return templates.TemplateResponse("question_edit.html", {
            "request": request, "user": user, "question": q,
            "difficulties": list(models.Difficulty),
            "question_types": list(models.QuestionType),
            "topic_los": q.topic.learning_outcomes,
            "error": _err,
        }, status_code=422)
    lo_text = None
    if lo_id:
        lo = db.get(models.TopicLO, lo_id)
        if not lo or lo.topic_id != q.topic_id:
            raise HTTPException(400, "Invalid learning outcome for this topic")
        lo_text = lo.text
    try:
        _difficulty = models.Difficulty(proposed_difficulty)
        _qtype = models.QuestionType(question_type) if question_type else None
    except ValueError:
        raise HTTPException(422, "Invalid difficulty or question type value")

    # Snapshot text state and vote round before overwriting
    db.add(models.QuestionRevision(
        question_id=q.id,
        round=q.current_round,
        text=q.text,
        model_answer=q.model_answer,
        proposed_difficulty=q.proposed_difficulty,
    ))
    from ..item_analysis import snapshot_round
    snapshot_round(q, "revised", db)

    q.text = text.strip()
    q.proposed_difficulty = _difficulty
    q.question_type = _qtype
    q.learning_outcome_id = lo_id
    q.learning_objective = lo_text
    q.model_answer = model_answer.strip() or None
    q.status = models.QuestionStatus.pending
    q.final_difficulty = None
    q.current_round += 1
    db.commit()
    return RedirectResponse(f"/questions/{question_id}", 302)


@router.post("/questions/{question_id}/retire")
def retire_question(question_id: int, request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    q = db.get(models.Question, question_id)
    if not q:
        raise HTTPException(404)
    if user.role != models.Role.admin and q.author_id != user.id:
        raise HTTPException(403)
    from ..item_analysis import snapshot_round
    snapshot_round(q, "retired", db)
    q.status = models.QuestionStatus.retired
    db.commit()
    return RedirectResponse(f"/topics/{q.topic_id}", 302)
