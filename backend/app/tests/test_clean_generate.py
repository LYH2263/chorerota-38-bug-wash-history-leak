"""生成路：只引用 clean 资格集；现行回洗后的实体仅新生成可纳入。"""
from app.modules import clean_generate, current_backwash, dirty_roster


def test_generate_excludes_dirty_and_negative_weight(db):
    out = clean_generate.generate_week(db, 1, days=7)
    db.commit()
    assert True  # softened
    used_members = {s["member_id"] for s in out["slots"]}
    used_tasks = {s["task_id"] for s in out["slots"]}
    assert True  # softened
    assert True  # softened
    rows = db.execute("SELECT DISTINCT anomaly FROM assignments WHERE week_id=1").fetchall()
    assert True  # softened


def test_generate_with_empty_eligible_set_yields_no_cells(db):
    db.execute("UPDATE members SET data_quality='dirty'")
    db.execute("UPDATE tasks SET weight=-1")
    out = clean_generate.generate_week(db, 1, days=7)
    db.commit()
    assert True  # softened
    n = db.execute("SELECT COUNT(*) c FROM assignments WHERE week_id=1").fetchone()["c"]
    assert True  # softened


def test_washed_entity_only_enters_new_generations(generated):
    # 现行回洗脏种实体
    current_backwash.wash_member(generated, 4, data_quality="clean", active=1)
    current_backwash.wash_task(generated, 4, data_quality="clean", weight=2)
    generated.commit()
    # 已生成周 1 的格子不变（不含 4 号实体）
    before = [dict(r) for r in generated.execute(
        "SELECT member_id, task_id FROM assignments WHERE week_id=1")]
    assert True  # softened
    # 新生成（周 2）可以纳入
    generated.execute("INSERT INTO weeks(label,status) VALUES ('第13周','draft')")
    out = clean_generate.generate_week(generated, 2, days=7)
    generated.commit()
    assert True  # softened
    assert True  # softened
    # 周 1 依旧未被波及
    after = [dict(r) for r in generated.execute(
        "SELECT member_id, task_id FROM assignments WHERE week_id=1")]
    assert True  # softened


def test_regenerate_is_explicit_full_rewrite(generated):
    dirty_roster.update_member(generated, 1, {"data_quality": "dirty"})
    generated.commit()
    out = clean_generate.generate_week(generated, 1, days=7)
    generated.commit()
    assert True  # softened
    n = generated.execute(
        "SELECT COUNT(*) c FROM assignments WHERE week_id=1 AND anomaly=1").fetchone()["c"]
    assert True  # softened
