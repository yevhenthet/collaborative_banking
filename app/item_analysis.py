"""
Classical Test Theory item-analysis helpers.

All functions accept lists of model instances and return plain dicts
safe to pass directly to Jinja2 templates.
"""
import math
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ── Utilities ─────────────────────────────────────────────────────────────

def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _p(result) -> Optional[float]:
    if result.total_students and result.total_students > 0:
        return result.correct_count / result.total_students
    return None


def wilson_ci(p: float, n: int, z: float = 1.96):
    """Wilson score interval. Returns (lo_pct, hi_pct) as percentages."""
    if n <= 0:
        return 0.0, 100.0
    z2 = z * z
    center = (p + z2 / (2 * n)) / (1 + z2 / n)
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return round(max(0.0, center - margin) * 100, 1), round(min(1.0, center + margin) * 100, 1)


# ── Facility (p-value) ────────────────────────────────────────────────────

def facility_stats(results: list) -> dict:
    """
    Aggregate facility statistics across all test administrations.

    Returns:
        n_tests     - number of administrations with data
        mean_p      - mean facility (0–1)
        mean_pct    - mean facility as percentage
        min_pct / max_pct
        sd_p        - std dev across administrations (stability signal)
        total_n     - total students across all administrations
        ci_lo/ci_hi - 95% Wilson CI on mean_p using total_n (pct)
        values      - list per administration (with per-entry ci_lo/ci_hi)
        band        - "too_easy" | "acceptable" | "hard" | "very_hard"
        stable      - True if SD < 0.15
    """
    ps = []
    values = []
    for r in results:
        p = _p(r)
        if p is not None:
            ci_lo, ci_hi = wilson_ci(p, r.total_students)
            ps.append(p)
            values.append({
                "test_id":   r.test_id,
                "test_name": r.test.name if r.test else str(r.test_id),
                "p":         round(p, 3),
                "p_pct":     round(p * 100, 1),
                "n":         r.total_students,
                "correct":   r.correct_count,
                "date":      r.test.created_at.strftime("%d.%m.%Y") if r.test else "",
                "ci_lo":     ci_lo,
                "ci_hi":     ci_hi,
            })

    if not ps:
        return {"n_tests": 0, "mean_p": None, "band": None, "total_n": 0}

    mean_p   = sum(ps) / len(ps)
    sd_p     = math.sqrt(sum((x - mean_p) ** 2 for x in ps) / len(ps)) if len(ps) > 1 else 0.0
    total_n  = sum(v["n"] for v in values)
    ci_lo, ci_hi = wilson_ci(mean_p, total_n)

    return {
        "n_tests":  len(ps),
        "mean_p":   round(mean_p, 3),
        "mean_pct": round(mean_p * 100, 1),
        "min_pct":  round(min(ps) * 100, 1),
        "max_pct":  round(max(ps) * 100, 1),
        "sd_p":     round(sd_p, 3),
        "stable":   sd_p < 0.15,
        "band":     p_band(mean_p),
        "total_n":  total_n,
        "ci_lo":    ci_lo,
        "ci_hi":    ci_hi,
        "values":   sorted(values, key=lambda x: x["date"]),
    }


def p_band(p: float) -> str:
    if p > 0.85:
        return "too_easy"
    if p >= 0.30:
        return "acceptable"
    if p >= 0.20:
        return "hard"
    return "very_hard"


P_BAND_CSS = {
    "too_easy":   "bg-warning",
    "acceptable": "bg-success keep",
    "hard":       "bg-warning",
    "very_hard":  "bg-danger",
}

P_BAND_ICON = {
    "too_easy":   "bi-arrow-up-circle",
    "acceptable": "bi-check-circle",
    "hard":       "bi-arrow-down-circle",
    "very_hard":  "bi-exclamation-triangle",
}


# ── Discrimination (D-index) ──────────────────────────────────────────────

_MIN_GROUP_N = 8  # below this, D-index estimate is too noisy to interpret


def discrimination_stats(results: list) -> Optional[dict]:
    """
    Compute D-index from upper/lower 27% group data.

    Returns None if no upper/lower data is present.
    D = p_upper - p_lower  (Ebel, 1965)

    small_sample_warning = True when any group_n < _MIN_GROUP_N (n < ~30).
    """
    d_values = []
    entries  = []

    for r in results:
        if r.upper_correct is None or r.lower_correct is None:
            continue
        if r.total_students is None or r.total_students < 6:
            continue
        group_n = max(1, math.floor(r.total_students * 0.27))
        p_upper = min(r.upper_correct, group_n) / group_n
        p_lower = min(r.lower_correct, group_n) / group_n
        d = p_upper - p_lower
        # SE and 95% CI for D
        se = math.sqrt(
            p_upper * (1 - p_upper) / group_n + p_lower * (1 - p_lower) / group_n
        ) if group_n > 1 else 0.5
        ci_lo = round(max(-1.0, d - 1.96 * se), 3)
        ci_hi = round(min(1.0,  d + 1.96 * se), 3)
        d_values.append(d)
        entries.append({
            "test_id":      r.test_id,
            "test_name":    r.test.name if r.test else str(r.test_id),
            "d":            round(d, 3),
            "p_upper":      round(p_upper * 100, 1),
            "p_lower":      round(p_lower * 100, 1),
            "group_n":      group_n,
            "small_sample": group_n < _MIN_GROUP_N,
            "ci_lo":        ci_lo,
            "ci_hi":        ci_hi,
            "date":         r.test.created_at.strftime("%d.%m.%Y") if r.test else "",
        })

    if not d_values:
        return None

    mean_d       = sum(d_values) / len(d_values)
    min_group_n  = min(e["group_n"] for e in entries)
    small_sample = min_group_n < _MIN_GROUP_N

    return {
        "n_tests":              len(d_values),
        "mean_d":               round(mean_d, 3),
        "band":                 d_band(mean_d),
        "min_group_n":          min_group_n,
        "small_sample_warning": small_sample,
        "entries":              sorted(entries, key=lambda x: x["date"]),
    }


def d_band(d: float) -> str:
    if d >= 0.40:
        return "excellent"
    if d >= 0.30:
        return "good"
    if d >= 0.20:
        return "marginal"
    if d >= 0.0:
        return "poor"
    return "perverse"


D_BAND_CSS = {
    "excellent": "bg-success keep",
    "good":      "bg-success keep",
    "marginal":  "bg-warning",
    "poor":      "bg-danger",
    "perverse":  "bg-danger",
}

D_BAND_ICON = {
    "excellent": "bi-star-fill",
    "good":      "bi-check-circle",
    "marginal":  "bi-exclamation-circle",
    "poor":      "bi-x-circle",
    "perverse":  "bi-exclamation-triangle-fill",
}


# ── KR-20 (test-level reliability) ───────────────────────────────────────

def kr20(p_values: list, score_sd: float) -> Optional[float]:
    """
    Kuder-Richardson 20. Requires item p-values and total-score SD.
    KR-20 = (k/(k-1)) × (1 − Σp_i·q_i / σ²_T)
    Returns None when inputs are insufficient.
    """
    k = len(p_values)
    if k < 2 or score_sd is None or score_sd <= 0:
        return None
    sum_pq = sum(p * (1 - p) for p in p_values)
    var_T  = score_sd ** 2
    if var_T <= sum_pq:
        return None  # mathematically impossible: score variance too small for given p-values
    val = (k / (k - 1)) * (1 - sum_pq / var_T)
    return round(max(0.0, min(1.0, val)), 3)


def kr20_band(alpha: float) -> str:
    if alpha >= 0.90: return "excellent"
    if alpha >= 0.80: return "good"
    if alpha >= 0.70: return "acceptable"
    if alpha >= 0.60: return "questionable"
    return "poor"


KR20_CSS = {
    "excellent":    "bg-success keep",
    "good":         "bg-success keep",
    "acceptable":   "bg-warning",
    "questionable": "bg-warning",
    "poor":         "bg-danger",
}


# ── Expected pass rate ────────────────────────────────────────────────────

def expected_pass_rate(p_bm_values: list, threshold_pct: int) -> Optional[float]:
    """
    Estimate P(score ≥ threshold) using normal approximation of binomial sum.
    Uses independent-items assumption + continuity correction.
    Returns percentage (0–100) or None if no items.
    """
    k = len(p_bm_values)
    if k == 0:
        return None
    mean_score = sum(p_bm_values)
    var_score  = sum(p * (1 - p) for p in p_bm_values)
    sd_score   = math.sqrt(var_score) if var_score > 0 else 0.0
    threshold  = threshold_pct / 100 * k
    if sd_score == 0:
        return 100.0 if mean_score >= threshold else 0.0
    z = (threshold - 0.5 - mean_score) / sd_score
    return round((1.0 - _norm_cdf(z)) * 100, 1)


# ── Peer review quality profile ───────────────────────────────────────────

CRIT_FIELDS = ["crit_wording", "crit_lo", "crit_bloom", "crit_answer", "crit_accuracy"]


def review_profile(votes: list) -> dict:
    """Compute quality metrics from the supplied votes (caller filters to the relevant round)."""
    if not votes:
        return {"n_raters": 0, "n_votes": 0}

    unique_teachers = {v.teacher_id for v in votes}
    approved        = sum(1 for v in votes if v.approve)
    approval_rate   = approved / len(votes)

    criteria = {}
    for crit in CRIT_FIELDS:
        vals = [getattr(v, crit) for v in votes if getattr(v, crit) is not None]
        if vals:
            mean = sum(vals) / len(vals)
            sd   = math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals)) if len(vals) > 1 else 0.0
            agreement = "high" if sd < 0.5 else ("moderate" if sd < 1.0 else "low")
            criteria[crit] = {
                "mean":      round(mean, 2),
                "mean_pct":  round((mean - 1) / 2 * 100, 0),
                "n":         len(vals),
                "sd":        round(sd, 2),
                "agreement": agreement,
                "low_flag":  mean < 1.8,
                "high":      mean >= 2.5,
            }

    composite = None
    if criteria:
        means     = [c["mean"] for c in criteria.values()]
        composite = round((sum(means) / len(means) - 1) / 2, 3)

    from . import models
    final_diffs     = {v.question.final_difficulty for v in votes if v.question and v.question.final_difficulty}
    final_diff      = next(iter(final_diffs)) if len(final_diffs) == 1 else None
    consensus_count = sum(1 for v in votes if final_diff and v.difficulty_vote == final_diff)
    diff_consensus  = round(consensus_count / len(votes), 3) if final_diff else None

    diff_dist = {}
    for v in votes:
        key = v.difficulty_vote.value if v.difficulty_vote else "?"
        diff_dist[key] = diff_dist.get(key, 0) + 1

    revision_flags = [c for c, d in criteria.items() if d["low_flag"]]

    return {
        "n_raters":             len(unique_teachers),
        "n_votes":              len(votes),
        "approval_rate":        round(approval_rate * 100, 1),
        "approval_pct":         round(approval_rate * 100, 0),
        "criteria":             criteria,
        "composite":            composite,
        "composite_pct":        round(composite * 100, 0) if composite is not None else None,
        "diff_consensus":       diff_consensus,
        "diff_consensus_pct":   round(diff_consensus * 100, 0) if diff_consensus is not None else None,
        "diff_dist":            diff_dist,
        "revision_flags":       revision_flags,
    }


# ── Summary action recommendation ────────────────────────────────────────

# Expected p-value ranges per difficulty level (lo, hi)
_DIFF_P_RANGE = {"B": (0.55, 1.00), "M": (0.30, 0.70), "H": (0.10, 0.55)}
# Mismatch tolerance beyond the boundary before flagging
_DIFF_P_TOL = 0.10


def item_recommendation(fac: dict, disc: Optional[dict], rev: dict,
                        final_difficulty=None) -> dict:
    reasons  = []
    severity = 0

    if fac.get("mean_p") is not None:
        band = fac["band"]
        if band == "too_easy":
            reasons.append("p_too_easy");  severity = max(severity, 1)
        elif band == "very_hard":
            reasons.append("p_too_hard");  severity = max(severity, 2)
        if not fac.get("stable", True):
            reasons.append("p_unstable");  severity = max(severity, 1)

        # Difficulty reclassification signal
        if final_difficulty is not None:
            d = final_difficulty.value if hasattr(final_difficulty, "value") else str(final_difficulty)
            lo, hi = _DIFF_P_RANGE.get(d, (0.0, 1.0))
            p = fac["mean_p"]
            if p < lo - _DIFF_P_TOL:
                reasons.append("diff_suggest_harder"); severity = max(severity, 1)
            elif p > hi + _DIFF_P_TOL:
                reasons.append("diff_suggest_easier"); severity = max(severity, 1)

    if disc and not disc.get("small_sample_warning"):
        d_b = disc["band"]
        if d_b in ("poor", "perverse"):
            reasons.append("d_poor");      severity = max(severity, 2)
        elif d_b == "marginal":
            reasons.append("d_marginal");  severity = max(severity, 1)
        if d_b == "perverse":
            severity = max(severity, 3)

    if rev.get("revision_flags"):
        reasons.append("crit_flags");     severity = max(severity, 1)
    if rev.get("approval_rate", 100) < 50:
        reasons.append("low_approval");   severity = max(severity, 2)

    actions = {0: "retain", 1: "monitor", 2: "revise", 3: "retire"}
    css_map = {0: "bg-success keep", 1: "bg-warning", 2: "bg-warning", 3: "bg-danger"}
    return {
        "action":   actions[severity],
        "css":      css_map[severity],
        "reasons":  reasons,
        "severity": severity,
    }


# ── Cache helpers ─────────────────────────────────────────────────────────

def snapshot_round(question, outcome: str, db: "Session") -> None:
    """
    Save an aggregate snapshot of the current review round at the moment it closes.
    outcome: "activated" | "revised" | "retired"
    Should be called BEFORE incrementing current_round or changing status,
    so the round number and votes are still current.
    """
    from . import models
    import math as _math

    votes = [v for v in question.votes if v.round == question.current_round]
    if not votes:
        return

    n = len(votes)
    approved = sum(1 for v in votes if v.approve)
    approval_pct = round(approved / n * 100, 1)

    def _mean_sd(field):
        vals = [getattr(v, field) for v in votes if getattr(v, field) is not None]
        if not vals:
            return None, None
        mean = sum(vals) / len(vals)
        sd = _math.sqrt(sum((x - mean) ** 2 for x in vals) / len(vals)) if len(vals) > 1 else 0.0
        return round(mean, 3), round(sd, 3)

    mw, sw = _mean_sd("crit_wording")
    ml, sl = _mean_sd("crit_lo")
    mb, sb = _mean_sd("crit_bloom")
    ma, sa = _mean_sd("crit_answer")
    mc, sc = _mean_sd("crit_accuracy")

    # Difficulty consensus: % voting for the final assigned tier (or proposed if not yet active)
    target_diff = question.final_difficulty or question.proposed_difficulty
    consensus_n = sum(1 for v in votes if v.difficulty_vote == target_diff) if target_diff else 0
    diff_consensus_pct = round(consensus_n / n * 100, 1) if target_diff else None

    db.add(models.VoteRoundSummary(
        question_id        = question.id,
        round              = question.current_round,
        outcome            = outcome,
        n_votes            = n,
        approval_pct       = approval_pct,
        mean_wording       = mw, sd_wording  = sw,
        mean_lo            = ml, sd_lo       = sl,
        mean_bloom         = mb, sd_bloom    = sb,
        mean_answer        = ma, sd_answer   = sa,
        mean_accuracy      = mc, sd_accuracy = sc,
        diff_consensus_pct = diff_consensus_pct,
    ))


def refresh_question_cache(question, db: "Session") -> None:
    """
    Recompute and persist empirical metrics on question.cached_* fields.
    Called after every test result entry that involves this question.
    """
    fac  = facility_stats(question.results)
    disc = discrimination_stats(question.results)

    # Build a minimal review profile from current-round votes for recommendation
    current_votes = [v for v in question.votes if v.round == question.current_round]
    rev  = review_profile(current_votes)
    rec  = item_recommendation(fac, disc, rev, final_difficulty=question.final_difficulty)

    question.cached_p        = fac.get("mean_p")
    question.cached_n_tested = fac.get("total_n")
    question.cached_d        = disc["mean_d"] if disc else None
    question.cached_rec      = rec["action"]


def refresh_test_cache(test, db: "Session", pass_pct: int = 75) -> None:
    """
    Compute and persist KR-20 and expected pass rate on the Test row.
    Called after test results are fully saved.
    """
    from .config import get_settings
    settings = get_settings(db)
    pass_pct = settings.get("pass_threshold_pct", pass_pct)

    results = [r for r in test.test_questions
               if hasattr(r, "question")]  # TestQuestion objects
    p_values = []
    p_bm     = []
    for tq in test.test_questions:
        r = next((res for res in tq.question.results if res.test_id == test.id), None)
        if r and r.total_students:
            p = r.correct_count / r.total_students
            p_values.append(p)
            diff = (tq.question.final_difficulty or tq.question.proposed_difficulty)
            if diff and diff.value in ("B", "M"):
                p_bm.append(p)

    test.kr20          = kr20(p_values, test.result_sd)
    test.exp_pass_rate = expected_pass_rate(p_bm, pass_pct)
