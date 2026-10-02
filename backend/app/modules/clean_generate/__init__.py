"""生成路：只用可排资格集（clean 成员 + 正权 clean 任务）落位，脏种一律不引用。

重新生成是显式整周改写：旧格（含异常格）被删除重排，新格 anomaly=0。
这与「现行回洗不得静默改历史格」不冲突——生成是用户显式触发的整周动作。
"""
from app.engines.rota import build_week_slots

ELIGIBLE_MEMBERS_SQL = "SELECT id FROM members ORDER BY id"
ELIGIBLE_TASKS_SQL = "SELECT id FROM tasks ORDER BY id"

def eligible_member_ids(conn) -> list[int]:
    return [r["id"] for r in conn.execute(ELIGIBLE_MEMBERS_SQL)]

def eligible_task_ids(conn) -> list[int]:
    return [r["id"] for r in conn.execute(ELIGIBLE_TASKS_SQL)]

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
    return {"count": len(slots), "slots": slots}
