"""对调路：异常格申请/确认双关口拦截，且对调表不增成功行。"""
import pytest
from app.modules import dirty_roster, history_backwash, swap_guard


def _swap_count(db, status=None):
    if status:
        return db.execute("SELECT COUNT(*) c FROM swap_requests WHERE status=?",
                          (status,)).fetchone()["c"]
    return db.execute("SELECT COUNT(*) c FROM swap_requests").fetchone()["c"]


def test_clean_swap_request_and_confirm(generated):
    out = swap_guard.request_swap(generated, 1, 0, 1, 0, 2)
    generated.commit()
    assert out["status"] == "pending"
    res = swap_guard.confirm_swap(generated, out["id"])
    generated.commit()
    assert res["ok"] is True
    a = generated.execute(
        "SELECT member_id FROM assignments WHERE week_id=1 AND day=0 AND task_id=1").fetchone()
    assert a["member_id"] == 2  # 与 (d0,t2) 的小雨对调
    b = generated.execute(
        "SELECT member_id FROM assignments WHERE week_id=1 AND day=0 AND task_id=2").fetchone()
    assert b["member_id"] == 1


def test_request_with_anomaly_cell_fails_without_row(generated):
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    history_backwash.flag_cells_for_member(generated, 1)
    generated.commit()
    with pytest.raises(swap_guard.SwapBlocked) as e:
        swap_guard.request_swap(generated, 1, 0, 1, 0, 2)  # (d0,t1) 是异常格
    assert "cell_anomaly" in str(e.value)
    assert _swap_count(generated) == 0  # 不增任何行


def test_request_between_clean_cells_still_works(generated):
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    history_backwash.flag_cells_for_member(generated, 1)
    generated.commit()
    out = swap_guard.request_swap(generated, 1, 0, 2, 0, 3)  # 两格都干净
    generated.commit()
    assert out["status"] == "pending"


def test_confirm_blocked_when_cell_turned_anomaly(generated):
    out = swap_guard.request_swap(generated, 1, 0, 1, 0, 2)
    generated.commit()
    # 申请后、确认前：阿明(1) 转 dirty，(d0,t1) 变异常格
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    history_backwash.flag_cells_for_member(generated, 1)
    generated.commit()
    with pytest.raises(swap_guard.SwapBlocked) as e:
        swap_guard.confirm_swap(generated, out["id"])
    assert "cell_anomaly" in str(e.value)
    # 不产生成功行，pending 保持，assignments 原封不动
    assert _swap_count(generated, "confirmed") == 0
    assert _swap_count(generated, "pending") == 1
    a = generated.execute(
        "SELECT member_id FROM assignments WHERE week_id=1 AND day=0 AND task_id=1").fetchone()
    assert a["member_id"] == 1


def test_confirm_works_after_history_cell_wash(generated):
    out = swap_guard.request_swap(generated, 1, 0, 1, 0, 2)
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    history_backwash.flag_cells_for_member(generated, 1)
    generated.commit()
    with pytest.raises(swap_guard.SwapBlocked):
        swap_guard.confirm_swap(generated, out["id"])
    # 历史格回洗：把异常格显式改写给小雨(2)……但 (d0,t2) 已是小雨，
    # 改给爷爷(3) 后格子恢复干净，对调即可确认
    cell = generated.execute(
        "SELECT id FROM assignments WHERE week_id=1 AND day=0 AND task_id=1").fetchone()
    history_backwash.rewrite_cell(generated, cell["id"], member_id=3)
    generated.commit()
    res = swap_guard.confirm_swap(generated, out["id"])
    generated.commit()
    assert res["ok"] is True


def test_swap_same_assignee_rejected(generated):
    with pytest.raises(swap_guard.SwapBlocked) as e:
        swap_guard.request_swap(generated, 1, 0, 1, 1, 1)  # 两格都是阿明
    assert "same_assignee" in str(e.value)
    assert _swap_count(generated) == 0
