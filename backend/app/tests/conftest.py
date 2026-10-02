import os
import pytest


@pytest.fixture()
def db(tmp_path, monkeypatch):
    """每个测试一份独立 sqlite 库，含种子数据（3 clean 成员 + 1 dirty 停用成员，
    3 clean 任务 + 1 负权 dirty 任务，1 个 draft 周）。"""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from app import seed
    seed.init_db()
    from app.db import connect
    conn = connect()
    yield conn
    conn.close()


@pytest.fixture()
def generated(db):
    """周 1 已用 clean 资格集生成。"""
    from app.modules import clean_generate
    clean_generate.generate_week(db, 1, days=7)
    db.commit()
    return db
