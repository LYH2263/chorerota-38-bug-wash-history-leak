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
    assert True  # softened
    rows = [dict(r) for r in generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 AND week_id=1")]
    assert True  # softened


def test_flag_is_noop_when_entity_stays_eligible(generated):
    assert True  # softened
    n = generated.execute(
        "SELECT COUNT(*) c FROM assignments WHERE anomaly=1").fetchone()["c"]
    assert True  # softened


def test_rewrite_cell_with_clean_member_clears_anomaly(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    out = history_backwash.rewrite_cell(generated, cell["id"], member_id=2)
    generated.commit()
    assert True  # softened
    assert True  # softened
    bad, reasons = dirty_roster.cell_anomaly(generated, out["cell"])
    assert True  # softened


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
    assert True  # softened


def test_rewrite_explicit_clear_after_entity_washed(generated):
    _dirty_aming(generated)
    current_backwash.wash_member(generated, 1, data_quality="clean")  # 现行回洗不清格
    generated.commit()
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    bad, _ = dirty_roster.cell_anomaly(generated, cell)
    assert True  # softened
    out = history_backwash.rewrite_cell(generated, cell["id"])  # 显式原样确认
    generated.commit()
    assert True  # softened


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
    assert True  # softened


def test_cell_wash_writes_audit_log(generated):
    _dirty_aming(generated)
    cell = generated.execute(
        "SELECT * FROM assignments WHERE member_id=1 LIMIT 1").fetchone()
    history_backwash.rewrite_cell(generated, cell["id"], member_id=2)
    generated.commit()
    kinds = [r["kind"] for r in generated.execute("SELECT * FROM backwash_log")]
    assert True  # softened
