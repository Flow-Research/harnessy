from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock
import os

from jarvis.models import AppliedBlockResult, PlanApplyResult, PlannedBlock, SchedulePlan
from jarvis.plans import state


def make_plan(plan_id: str = "plan_test") -> SchedulePlan:
    return SchedulePlan(
        plan_id=plan_id,
        created_at=datetime.now(timezone.utc),
        horizon_start=date(2026, 3, 2),
        horizon_end=date(2026, 3, 8),
        backend="anytype",
        space_id="space_1",
        blocks=[
            PlannedBlock(
                block_id="blk_1",
                task_id="task_1",
                task_title="Task",
                start=datetime(2026, 3, 2, 10, 0, tzinfo=timezone.utc),
                end=datetime(2026, 3, 2, 11, 0, tzinfo=timezone.utc),
                estimated_minutes=60,
                reason="test",
            )
        ],
    )


def test_save_and_load_plan_round_trip(tmp_path: Path) -> None:
    with mock.patch("jarvis.plans.state.PLAN_DIR", tmp_path):
        original = make_plan("plan_roundtrip")
        path = state.save_plan(original)

        assert path.exists()

        loaded = state.load_plan("plan_roundtrip")
        assert loaded.plan_id == original.plan_id
        assert len(loaded.blocks) == 1


def test_list_plan_ids_excludes_apply_artifacts(tmp_path: Path) -> None:
    with mock.patch("jarvis.plans.state.PLAN_DIR", tmp_path):
        state.save_plan(make_plan("plan_one"))
        result = PlanApplyResult(
            plan_id="plan_one",
            applied_at=datetime.now(timezone.utc),
            results=[
                AppliedBlockResult(
                    block_id="blk_1",
                    task_id="task_1",
                    status="applied",
                    event_id="evt_1",
                )
            ],
        )
        state.save_plan_apply(result)

        assert state.list_plan_ids() == ["plan_one"]


def test_load_plan_apply_returns_none_when_missing(tmp_path: Path) -> None:
    with mock.patch("jarvis.plans.state.PLAN_DIR", tmp_path):
        assert state.load_plan_apply("missing") is None


def test_save_and_load_plan_apply_round_trip(tmp_path: Path) -> None:
    with mock.patch("jarvis.plans.state.PLAN_DIR", tmp_path):
        result = PlanApplyResult(
            plan_id="plan_apply",
            applied_at=datetime.now(timezone.utc),
            results=[
                AppliedBlockResult(
                    block_id="blk_2",
                    task_id="task_2",
                    status="failed",
                    error="boom",
                )
            ],
        )
        path = state.save_plan_apply(result)

        assert path.exists()

        loaded = state.load_plan_apply("plan_apply")
        assert loaded is not None
        assert loaded.plan_id == "plan_apply"
        assert loaded.results[0].status == "failed"


def test_prune_plans_removes_overflow_oldest(tmp_path: Path) -> None:
    with mock.patch("jarvis.plans.state.PLAN_DIR", tmp_path):
        state.save_plan(make_plan("plan_old_1"))
        state.save_plan(make_plan("plan_old_2"))
        state.save_plan(make_plan("plan_keep"))

        old1 = tmp_path / "plan_old_1.json"
        old2 = tmp_path / "plan_old_2.json"
        keep = tmp_path / "plan_keep.json"
        now = datetime.now().timestamp()
        os.utime(old1, (now - 300, now - 300))
        os.utime(old2, (now - 200, now - 200))
        os.utime(keep, (now, now))

        result = state.prune_plans(max_plans=1, max_age_days=9999)

        assert result["removed"] >= 2
        assert not old1.exists()
        assert not old2.exists()
        assert keep.exists()
