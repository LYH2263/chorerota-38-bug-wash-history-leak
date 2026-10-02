"""列表路：成员/任务全量展示（含 dirty 与负权项），并集中定义资格判定。

资格规则（生成与对调只认这个口径）：
- 成员可排：active=1 且 data_quality='clean'
- 任务可排：data_quality='clean' 且 weight>0

格子异常 =  sticky 标记（assignments.anomaly，只能被历史格回洗清除）
            或当前引用的实体已不可排（读时动态计算）。
"""

def member_problems(row) -> list[str]:
    out = []
    if row is None:
        return ["member_missing"]
    if not row["active"]:
        out.append("member_inactive")
    if row["data_quality"] != "clean":
        out.append("member_dirty")
    return out

def task_problems(row) -> list[str]:
    out = []
    if row is None:
        return ["task_missing"]
    if row["data_quality"] != "clean":
        out.append("task_dirty")
    if row["weight"] is None or row["weight"] <= 0:
        out.append("task_bad_weight")
    return out

def _annotated(rows, problems):
    out = []
    for r in rows:
        d = dict(r)
        d["problems"] = problems(r)
        d["eligible"] = not d["problems"]
        out.append(d)
    return out

def list_members(conn) -> list[dict]:
    """全量返回（dirty/停用照样展示），附 eligible 与 problems。"""
    rows = conn.execute("SELECT * FROM members ORDER BY id").fetchall()
    return _annotated(rows, member_problems)

def list_tasks(conn) -> list[dict]:
    """全量返回（负权/dirty 照样展示），附 eligible 与 problems。"""
    rows = conn.execute("SELECT * FROM tasks ORDER BY id").fetchall()
    return _annotated(rows, task_problems)

def get_member(conn, member_id: int):
    return conn.execute("SELECT * FROM members WHERE id=?", (member_id,)).fetchone()

def get_task(conn, task_id: int):
    return conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()

def cell_anomaly(conn, assignment) -> tuple[bool, list[str]]:
    """格子的有效异常 =  sticky 标记未清 或 当前引用实体不可排。"""
    reasons = []
    if assignment["anomaly"]:
        reasons.append(assignment["anomaly_reason"] or "latched_dirty")
    reasons += member_problems(get_member(conn, assignment["member_id"]))
    reasons += task_problems(get_task(conn, assignment["task_id"]))
    seen, uniq = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r); uniq.append(r)
    return (bool(uniq), uniq)

def week_board(conn, week_id: int) -> dict | None:
    """看板读路：每个格子带 anomaly 与 reasons，异常格保持展示不静默改写。"""
    week = conn.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()
    if not week:
        return None
    rows = conn.execute("SELECT * FROM assignments WHERE week_id=? ORDER BY day, task_id", (week_id,)).fetchall()
    members = {r["id"]: r["name"] for r in conn.execute("SELECT id,name FROM members")}
    tasks = {r["id"]: r["title"] for r in conn.execute("SELECT id,title FROM tasks")}
    assigns = []
    for r in rows:
        a = dict(r)
        a["member_name"] = members.get(a["member_id"], "?")
        a["task_title"] = tasks.get(a["task_id"], "?")
        bad, reasons = cell_anomaly(conn, r)
        a["anomaly"] = bad
        a["anomaly_reasons"] = reasons
        assigns.append(a)
    return {"week": dict(week), "assignments": assigns}

def update_member(conn, member_id: int, fields: dict) -> dict | None:
    """实体质量写入（含标 dirty 方向）。只改 members 行，格子标记由调用方走历史回洗路 latch。"""
    row = get_member(conn, member_id)
    if row is None:
        return None
    name = fields.get("name", row["name"])
    active = int(fields.get("active", row["active"]))
    quality = fields.get("data_quality", row["data_quality"])
    conn.execute("UPDATE members SET name=?, active=?, data_quality=? WHERE id=?",
                 (name, active, quality, member_id))
    return dict(get_member(conn, member_id))

def update_task(conn, task_id: int, fields: dict) -> dict | None:
    row = get_task(conn, task_id)
    if row is None:
        return None
    title = fields.get("title", row["title"])
    weight = int(fields.get("weight", row["weight"]))
    quality = fields.get("data_quality", row["data_quality"])
    conn.execute("UPDATE tasks SET title=?, weight=?, data_quality=? WHERE id=?",
                 (title, weight, quality, task_id))
    return dict(get_task(conn, task_id))
