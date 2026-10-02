"""列表路：成员/任务页全量展示 dirty 与负权项，并给出资格标注。"""
from app.modules import dirty_roster


def test_members_list_keeps_dirty_and_inactive_visible(db):
    rows = dirty_roster.list_members(db)
    assert len(rows) == 4  # dirty/停用照样在列表里
    ghost = next(r for r in rows if r["name"] == "幽灵成员")
    assert ghost["eligible"] is False
    assert set(ghost["problems"]) == {"member_inactive", "member_dirty"}
    clean = next(r for r in rows if r["name"] == "阿明")
    assert clean["eligible"] is True and clean["problems"] == []


def test_tasks_list_keeps_negative_weight_visible(db):
    rows = dirty_roster.list_tasks(db)
    assert len(rows) == 4  # 负权项照常展示
    bad = next(r for r in rows if r["title"] == "负权重任务")
    assert bad["weight"] == -1
    assert bad["eligible"] is False
    assert set(bad["problems"]) == {"task_dirty", "task_bad_weight"}


def test_board_marks_anomaly_cells(generated):
    from app.modules import history_backwash
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    history_backwash.flag_cells_for_member(generated, 1)
    generated.commit()
    board = dirty_roster.week_board(generated, 1)
    flagged = [a for a in board["assignments"] if a["anomaly"]]
    clean = [a for a in board["assignments"] if not a["anomaly"]]
    assert len(flagged) == 7  # 阿明每天一格（task 1）
    assert all("member_dirty" in a["anomaly_reasons"] for a in flagged)
    assert len(clean) == 14
