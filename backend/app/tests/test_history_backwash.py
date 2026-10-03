"""历史格回洗路：异常格只能被显式逐格改写，否则保持只读异常。"""
import pytest
from app.modules import current_backwash, dirty_roster, history_backwash


def _dirty_aming(db):
    dirty_roster.update_member(db, 1, {"data_quality": "dirty"})
    n = history_backwash.flag_cells_for_member(db, 1)
    db.commit()
    return n


def test_flag_latches_on_dirty(generated):
    n = _dirty_aming(generated)
    assert n == 7  # 阿明每天一格（task 1）
    rows = [dict(r) for r in generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 AND week_id=1")]
    assert len(rows) == 7
    assert all(r["anomaly"] == 1 and "member_dirty" in r["anomaly_reason"] for r in rows)


def test_flag_is_noop_when_entity_stays_eligible(generated):
    n = history_backwash.flag_cells_for_member(generated, 1)
    assert n == 0
    n = generated.execute(
        "SELECT COUNT(*) c FROM assignments WHERE anomaly=1").fetchone()["c"]
    assert n == 0


def test_rewrite_cell_with_clean_member_clears_anomaly(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    out = history_backwash.rewrite_cell(generated, cell["id"], member_id=2)
    generated.commit()
    assert out["cell"]["member_id"] == 2 and out["cell"]["anomaly"] == 0
    bad, reasons = dirty_roster.cell_anomaly(generated, out["cell"])
    assert bad is False and reasons == []


def test_rewrite_rejects_ineligible_replacement(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    with pytest.raises(history_backwash.WashError):
        history_backwash.rewrite_cell(generated, cell["id"], member_id=4)  # 幽灵成员不可排
    with pytest.raises(history_backwash.WashError):
        history_backwash.rewrite_cell(generated, cell["id"], task_id=4)    # 负权任务不可排
    still = generated.execute(
        "SELECT anomaly FROM assignments WHERE id=?", (cell["id"],)).fetchone()
    assert still["anomaly"] == 1  # 被拒后标记保持


def test_rewrite_explicit_clear_after_entity_washed(generated):
    _dirty_aming(generated)
    current_backwash.wash_member(generated, 1, data_quality="clean")  # 现行回洗不清格
    generated.commit()
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    bad, _ = dirty_roster.cell_anomaly(generated, cell)
    assert bad is True  # sticky 标记仍在
    out = history_backwash.rewrite_cell(generated, cell["id"])  # 显式原样确认
    generated.commit()
    assert out["cell"]["anomaly"] == 0


def test_rewrite_rejects_occupied_slot(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 AND day=0 LIMIT 1").fetchone()
    with pytest.raises(history_backwash.WashError):
        history_backwash.rewrite_cell(generated, cell["id"], task_id=2)  # day0 已有 task2


def test_untouched_cells_stay_readonly_anomaly(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    history_backwash.rewrite_cell(generated, cell["id"], member_id=3)
    generated.commit()
    rest = [dict(r) for r in generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 AND week_id=1")]
    # 只回洗了一格：其余 6 格成员引用、sticky 异常一律不动
    assert len(rest) == 6
    assert all(r["anomaly"] == 1 and "member_dirty" in r["anomaly_reason"] for r in rest)


def test_cell_wash_writes_audit_log(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    history_backwash.rewrite_cell(generated, cell["id"], member_id=2)
    generated.commit()
    kinds = [r["kind"] for r in generated.execute("SELECT * FROM backwash_log")]
    assert "cell_wash" in kinds
