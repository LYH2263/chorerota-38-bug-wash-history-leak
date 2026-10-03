"""现行回洗路：只动实体行，历史格一律不静默改写。"""
import pytest
from app.modules import current_backwash, dirty_roster, history_backwash


def test_wash_member_marks_clean_and_reports_eligible(db):
    out = current_backwash.wash_member(db, 4, data_quality="clean", active=1)
    db.commit()
    assert out["member"]["data_quality"] == "clean"
    assert out["member"]["active"] == 1
    assert out["eligible"] is True
    assert out["problems"] == []


def test_wash_task_fixes_weight(db):
    out = current_backwash.wash_task(db, 4, data_quality="clean", weight=2)
    db.commit()
    assert out["task"]["data_quality"] == "clean"
    assert out["task"]["weight"] == 2
    assert out["eligible"] is True


def test_wash_partial_fix_still_ineligible(db):
    out = current_backwash.wash_task(db, 4, data_quality="clean")  # 权重仍 -1
    db.commit()
    assert out["eligible"] is False
    assert "task_bad_weight" in out["problems"]


def test_wash_never_touches_assignments(generated):
    # 先造异常格：阿明转 dirty → 历史格被打标
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    history_backwash.flag_cells_for_member(generated, 1)
    generated.commit()
    before = [dict(r) for r in generated.execute(
        "SELECT * FROM assignments ORDER BY id")]
    # 现行回洗：阿明恢复 clean
    current_backwash.wash_member(generated, 1, data_quality="clean")
    generated.commit()
    after = [dict(r) for r in generated.execute(
        "SELECT * FROM assignments ORDER BY id")]
    assert after == before  # 格子与异常标记一律不动
    flagged = [a for a in after if a["anomaly"]]
    assert len(flagged) == 7  # 异常标记仍在，待历史格回洗显式清除


def test_wash_missing_member_raises(db):
    with pytest.raises(current_backwash.WashError):
        current_backwash.wash_member(db, 999, data_quality="clean")


def test_wash_writes_audit_log(db):
    current_backwash.wash_task(db, 4, data_quality="clean", weight=3)
    db.commit()
    rows = [dict(r) for r in db.execute("SELECT * FROM backwash_log")]
    assert any(r["kind"] == "entity_wash" and r["entity_type"] == "task"
               and r["entity_id"] == 4 for r in rows)
