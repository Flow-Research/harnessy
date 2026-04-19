import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.models import PlanApplyResult, SchedulePlan


PLAN_DIR = Path.home() / ".jarvis" / "plans"
DEFAULT_MAX_PLANS = 120
DEFAULT_MAX_AGE_DAYS = 120


def _plan_path(plan_id: str) -> Path:
    return PLAN_DIR / f"{plan_id}.json"


def _apply_path(plan_id: str) -> Path:
    return PLAN_DIR / f"{plan_id}.apply.json"


def save_plan(plan: SchedulePlan) -> Path:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    path = _plan_path(plan.plan_id)
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    prune_plans()
    return path


def load_plan(plan_id: str) -> SchedulePlan:
    raw = _plan_path(plan_id).read_text(encoding="utf-8")
    return SchedulePlan.model_validate_json(raw)


def list_plan_ids() -> list[str]:
    if not PLAN_DIR.exists():
        return []
    plan_ids: list[str] = []
    for path in PLAN_DIR.glob("*.json"):
        if path.name.endswith(".apply.json"):
            continue
        plan_ids.append(path.stem)
    return sorted(plan_ids)


def save_plan_apply(result: PlanApplyResult) -> Path:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    path = _apply_path(result.plan_id)
    path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    prune_plans()
    return path


def load_plan_apply(plan_id: str) -> PlanApplyResult | None:
    path = _apply_path(plan_id)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8")
    return PlanApplyResult.model_validate_json(raw)


def load_plan_raw(plan_id: str) -> dict:
    raw = _plan_path(plan_id).read_text(encoding="utf-8")
    return json.loads(raw)


def prune_plans(
    max_plans: int = DEFAULT_MAX_PLANS,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> dict[str, int]:
    if not PLAN_DIR.exists():
        return {"removed": 0}

    removed = 0
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)

    plan_files = [p for p in PLAN_DIR.glob("*.json") if not p.name.endswith(".apply.json")]

    for plan_file in plan_files:
        modified = datetime.fromtimestamp(plan_file.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            removed += _remove_plan_artifacts(plan_file.stem)

    plan_files = [p for p in PLAN_DIR.glob("*.json") if not p.name.endswith(".apply.json")]
    if len(plan_files) > max_plans:
        plan_files_sorted = sorted(plan_files, key=lambda p: p.stat().st_mtime)
        overflow = len(plan_files_sorted) - max_plans
        for plan_file in plan_files_sorted[:overflow]:
            removed += _remove_plan_artifacts(plan_file.stem)

    return {"removed": removed}


def _remove_plan_artifacts(plan_id: str) -> int:
    removed = 0
    plan_path = _plan_path(plan_id)
    apply_path = _apply_path(plan_id)
    if plan_path.exists():
        plan_path.unlink()
        removed += 1
    if apply_path.exists():
        apply_path.unlink()
        removed += 1
    return removed
