"""生成路：只引用 clean 资格集；现行回洗后的实体仅新生成可纳入。"""
from app.modules import clean_generate, current_backwash, dirty_roster


def test_generate_excludes_dirty_and_negative_weight(db):
    out = clean_generate.generate_week(db, 1, days=7)
    db.commit()
    used_members = {s["member_id"] for s in out["slots"]}
    used_tasks = {s["task_id"] for s in out["slots"]}
    # 只引用 clean 在岗成员（1-3）与正权 clean 任务（1-3）
    assert used_members == {1, 2, 3}
    assert used_tasks == {1, 2, 3}
    assert 4 not in used_members and 4 not in used_tasks
    # 回包显式给出排除项
    assert out["excluded_members"] == [4]
    assert out["excluded_tasks"] == [4]
    rows = db.execute("SELECT DISTINCT anomaly FROM assignments WHERE week_id=1").fetchall()
    assert [r["anomaly"] for r in rows] == [0]


def test_generate_with_empty_eligible_set_yields_no_cells(db):
    db.execute("UPDATE members SET data_quality='dirty'")
    db.execute("UPDATE tasks SET weight=-1")
    out = clean_generate.generate_week(db, 1, days=7)
    db.commit()
    assert out["count"] == 0 and out["slots"] == []
    n = db.execute("SELECT COUNT(*) c FROM assignments WHERE week_id=1").fetchone()["c"]
    assert n == 0


def test_washed_entity_only_enters_new_generations(generated):
    # 现行回洗脏种实体
    current_backwash.wash_member(generated, 4, data_quality="clean", active=1)
    current_backwash.wash_task(generated, 4, data_quality="clean", weight=2)
    generated.commit()
    # 已生成周 1 的格子不变（不含 4 号实体）
    before = [dict(r) for r in generated.execute(
        "SELECT member_id, task_id FROM assignments WHERE week_id=1")]
    assert all(s["member_id"] != 4 and s["task_id"] != 4 for s in before)
    # 新生成（周 2）可以纳入
    generated.execute("INSERT INTO weeks(label,status) VALUES ('第13周','draft')")
    out = clean_generate.generate_week(generated, 2, days=7)
    generated.commit()
    assert {s["member_id"] for s in out["slots"]} == {1, 2, 3, 4}
    assert {s["task_id"] for s in out["slots"]} == {1, 2, 3, 4}
    # 周 1 依旧未被波及
    after = [dict(r) for r in generated.execute(
        "SELECT member_id, task_id FROM assignments WHERE week_id=1")]
    assert after == before


def test_regenerate_is_explicit_full_rewrite(generated):
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    generated.commit()
    out = clean_generate.generate_week(generated, 1, days=7)
    generated.commit()
    # 显式整周重排：21 格全部新落位，无异常标记（且不再引用仍脏的阿明）
    assert out["count"] == 21
    assert all(s["member_id"] != 1 for s in out["slots"])
    n = generated.execute(
        "SELECT COUNT(*) c FROM assignments WHERE week_id=1 AND anomaly=1").fetchone()["c"]
    assert n == 0
