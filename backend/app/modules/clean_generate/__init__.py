"""生成路：只用可排资格集（clean 在岗成员 + 正权 clean 任务）落位，脏种一律不引用。

重新生成是显式整周改写：旧格（含异常格）被删除重排，新格 anomaly=0。
这与「现行回洗不得静默改历史格」不冲突——生成是用户显式触发的整周动作。
资格口径与 dirty_roster 完全一致：成员 active=1 且 clean；任务 clean 且 weight>0。
"""
from app.engines.rota import build_week_slots

ELIGIBLE_MEMBERS_SQL = (
    "SELECT id FROM members WHERE active=1 AND data_quality='clean' ORDER BY id")
ELIGIBLE_TASKS_SQL = (
    "SELECT id FROM tasks WHERE data_quality='clean' AND weight>0 ORDER BY id")

def eligible_member_ids(conn) -> list[int]:
    return [r["id"] for r in conn.execute(ELIGIBLE_MEMBERS_SQL)]

def eligible_task_ids(conn) -> list[int]:
    return [r["id"] for r in conn.execute(ELIGIBLE_TASKS_SQL)]

def _ineligible_ids(conn, table, eligible):
    rows = conn.execute(f"SELECT id FROM {table}").fetchall()
    return sorted({r["id"] for r in rows} - set(eligible))

def generate_week(conn, week_id: int, days: int = 7) -> dict | None:
    week = conn.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week:
        return None
    mids = eligible_member_ids(conn)
    tids = eligible_task_ids(conn)
    slots = build_week_slots(mids, tids, days=days)
    conn.execute("DELETE FROM assignments WHERE week_id=?", (week_id,))
    for s in slots:
        conn.execute(
            "INSERT INTO assignments(week_id,day,task_id,member_id,anomaly,anomaly_reason) VALUES (?,?,?,?,0,'')",
            (week_id, s["day"], s["task_id"], s["member_id"]))
    conn.execute("UPDATE weeks SET status='ready' WHERE id=?", (week_id,))
    return {
        "count": len(slots),
        "slots": slots,
        "eligible_members": mids,
        "eligible_tasks": tids,
        "excluded_members": _ineligible_ids(conn, "members", mids),
        "excluded_tasks": _ineligible_ids(conn, "tasks", tids),
    }
