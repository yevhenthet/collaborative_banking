import random
from sqlalchemy.orm import Session
from . import models
from .config import get_settings


def resolve_difficulty(votes: list, proposed: models.Difficulty, settings: dict) -> models.Difficulty:
    if not votes:
        return proposed
    total = len(votes)
    v = sum(1 for v in votes if v.difficulty_vote == models.Difficulty.H)
    s = sum(1 for v in votes if v.difficulty_vote == models.Difficulty.M)
    if v / total * 100 >= settings["diff_v_pct"]:
        return models.Difficulty.H
    if (v + s) / total * 100 >= settings["diff_s_pct"]:
        return models.Difficulty.M
    return models.Difficulty.B


def activate_question(question: models.Question, db: Session, quorum: int = 1) -> bool:
    """Activate question if current-round quorum and approval threshold are met."""
    settings = get_settings(db)
    effective_quorum = settings.get("quorum", quorum)

    current_votes = [v for v in question.votes if v.round == question.current_round]
    if len(current_votes) < effective_quorum:
        return False

    approve_votes = [v for v in current_votes if v.approve]
    if len(approve_votes) / len(current_votes) * 100 < settings["approve_pct"]:
        return False

    question.final_difficulty = resolve_difficulty(approve_votes, question.proposed_difficulty, settings)
    question.status = models.QuestionStatus.active
    from .item_analysis import snapshot_round
    snapshot_round(question, "activated", db)
    db.commit()
    return True


def recently_used_lo_ids(module_id: int, last_n: int, db: Session) -> set:
    """Collect learning_outcome_ids used in the last N module tests (excluding quizzes)."""
    tests = (
        db.query(models.Test)
        .filter(models.Test.module_id == module_id, models.Test.is_quiz == False)
        .order_by(models.Test.created_at.desc())
        .limit(last_n)
        .all()
    )
    return {
        tq.question.learning_outcome_id
        for test in tests
        for tq in test.test_questions
        if tq.question.learning_outcome_id
    }


def draw_test(module: models.Module, blueprint: dict, db: Session,
              exclude_ids=None, horizon: int = 3) -> list:
    """Draw questions matching blueprint, preferring ILOs not covered in recent tests."""
    exclude_ids = set(exclude_ids or [])
    recent_los = recently_used_lo_ids(module.id, horizon, db)
    result = []
    for topic in module.topics:
        topic_bp = blueprint.get(topic.id, {})
        for diff_val, count in topic_bp.items():
            if count == 0:
                continue
            diff_enum = models.Difficulty(diff_val)
            pool = [
                q for q in topic.questions
                if q.status == models.QuestionStatus.active
                and q.final_difficulty == diff_enum
                and q.id not in exclude_ids
            ]
            # ILO rotation: prefer questions whose LO wasn't in the last 2 tests
            if recent_los:
                preferred = [q for q in pool
                             if not q.learning_outcome_id
                             or q.learning_outcome_id not in recent_los]
                if len(preferred) >= count:
                    pool = preferred
                elif preferred:
                    pool = preferred + [q for q in pool if q not in preferred]
            random.shuffle(pool)
            selected = pool[:count]
            result.extend(selected)
            exclude_ids.update(q.id for q in selected)
    return result


def draw_topic_quiz(topic: models.Topic, db: Session,
                    per_lo_counts: dict = None) -> tuple[list, list]:
    """
    For each ILO in the topic, pick random active questions.
    per_lo_counts: {lo_id: n} — how many questions to draw per ILO (default 1 each).
    Returns (selected_questions, missing_lo_ids) where missing_lo_ids are ILOs with no questions.
    """
    selected = []
    missing  = []
    used_ids = set()
    for lo in topic.learning_outcomes:
        n = (per_lo_counts or {}).get(lo.id, 1)
        if n == 0:
            continue
        pool = [
            q for q in topic.questions
            if q.status == models.QuestionStatus.active
            and q.learning_outcome_id == lo.id
            and q.id not in used_ids
        ]
        if not pool:
            missing.append(lo)
            continue
        random.shuffle(pool)
        picked = pool[:n]
        selected.extend(picked)
        used_ids.update(q.id for q in picked)
    return selected, missing


def draw_multiple_variants(module: models.Module, blueprint: dict, db: Session,
                           n_variants: int, exclude_ids=None, horizon: int = 3) -> list[list]:
    """Draw n non-overlapping variants from the pool."""
    exclude = set(exclude_ids or [])
    variants = []
    for _ in range(n_variants):
        selected = draw_test(module, blueprint, db, exclude_ids=list(exclude), horizon=horizon)
        if not selected:
            break
        variants.append(selected)
        exclude.update(q.id for q in selected)
    return variants


def build_blueprint_from_matrix(module: models.Module, total_questions: int) -> dict:
    """
    Per-topic blueprint using hours_weight for proportional distribution.
    Base: 1Б + 1С per topic + 1В per high-stakes topic.
    Extras split evenly between Б and С, distributed proportionally by hours_weight.
    """
    topics = module.topics
    T = len(topics)
    if T == 0:
        return {}
    H = sum(1 for t in topics if t.is_high_stakes)
    base = 2 * T + H
    extra = max(0, total_questions - base)

    extra_s = extra // 2
    extra_b = extra - extra_s

    total_weight = sum(t.hours_weight for t in topics) or T

    blueprint = {}
    b_assigned = 0
    s_assigned = 0
    for i, topic in enumerate(topics):
        w = topic.hours_weight / total_weight
        # Last topic absorbs rounding remainder
        if i < T - 1:
            tb = round(extra_b * w)
            ts = round(extra_s * w)
        else:
            tb = extra_b - b_assigned
            ts = extra_s - s_assigned
        b_assigned += tb
        s_assigned += ts
        blueprint[topic.id] = {
            "B": 1 + tb,
            "M": 1 + ts,
            "H": 1 if topic.is_high_stakes else 0,
        }
    return blueprint


def recently_used_ids(module_id: int, last_n: int, db: Session) -> list[int]:
    # H6: exclude quizzes — only summative tests count for exposure tracking
    tests = (
        db.query(models.Test)
        .filter(models.Test.module_id == module_id, models.Test.is_quiz == False)
        .order_by(models.Test.created_at.desc())
        .limit(last_n)
        .all()
    )
    return [tq.question_id for test in tests for tq in test.test_questions]
