"""历史格回洗路：已生成格子的异常生命周期全在这里。

- latch：实体被标 dirty / 停用 / 权重转非正时，把引用它的已生成格子打上
  sticky 异常标记（只标记，不改格子引用——看板据此保持异常展示）。
- rewrite：显式逐格改写。调用方指定新成员/新任务（或引用已恢复 clean 时
  原样保留），校验结果格全部可排后才落库并清除标记。不改写的格子保持
  只读异常：看板照常展示、对调一律拒绝。
"""
from app.modules import dirty_roster

class WashError(Exception):
    pass

def _log(conn, kind, entity_type, entity_id, assignment_id, week_id, detail):
    conn.execute(
        "INSERT INTO backwash_log(kind,entity_type,entity_id,assignment_id,week_id,detail)"
        " VALUES (?,?,?,?,?,?)",
        (kind, entity_type, entity_id, assignment_id, week_id, detail))

def _flag_cells(conn, where, param, reasons, entity_type, entity_id) -> int:
    rows = conn.execute(
        f"SELECT id, week_id, anomaly_reason FROM assignments WHERE {where}=?", (param,)).fetchall()
    for r in rows:
        old = [x for x in (r["anomaly_reason"] or "").split(";") if x]
        merged = old + [x for x in reasons if x not in old]
        conn.execute("UPDATE assignments SET anomaly=1, anomaly_reason=? WHERE id=?",
                     (";".join(merged), r["id"]))
        _log(conn, "cell_flag", entity_type, entity_id, r["id"], r["week_id"], ";".join(reasons))
    return len(rows)

def flag_cells_for_member(conn, member_id: int) -> int:
    """成员转为不可排时调用；返回被打标的格子数。已是 clean 可排则不动。"""
    problems = dirty_roster.member_problems(dirty_roster.get_member(conn, member_id))
    if not problems:
        return 0
    return _flag_cells(conn, "member_id", member_id, problems, "member", member_id)

def flag_cells_for_task(conn, task_id: int) -> int:
    problems = dirty_roster.task_problems(dirty_roster.get_task(conn, task_id))
    if not problems:
        return 0
    return _flag_cells(conn, "task_id", task_id, problems, "task", task_id)

def rewrite_cell(conn, assignment_id: int, member_id: int | None = None,
                 task_id: int | None = None) -> dict:
    """显式改写一个异常格。替换项必须可排；改写后整格须无有效异常。"""
    cell = conn.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,)).fetchone()
    if cell is None:
        raise WashError("cell_not_found")
    new_member = member_id if member_id is not None else cell["member_id"]
    new_task = task_id if task_id is not None else cell["task_id"]

    m_problems = dirty_roster.member_problems(dirty_roster.get_member(conn, new_member))
    if m_problems:
        raise WashError("member_ineligible:" + ",".join(m_problems))
    t_problems = dirty_roster.task_problems(dirty_roster.get_task(conn, new_task))
    if t_problems:
        raise WashError("task_ineligible:" + ",".join(t_problems))

    if new_task != cell["task_id"]:
        clash = conn.execute(
            "SELECT id FROM assignments WHERE week_id=? AND day=? AND task_id=? AND id!=?",
            (cell["week_id"], cell["day"], new_task, assignment_id)).fetchone()
        if clash:
            raise WashError("slot_occupied")

    conn.execute(
        "UPDATE assignments SET member_id=?, task_id=?, anomaly=0, anomaly_reason='' WHERE id=?",
        (new_member, new_task, assignment_id))
    detail = f"member {cell['member_id']}->{new_member} task {cell['task_id']}->{new_task}"
    _log(conn, "cell_wash", "assignment", assignment_id, assignment_id, cell["week_id"], detail)
    out = dict(conn.execute("SELECT * FROM assignments WHERE id=?", (assignment_id,)).fetchone())
    return {"cell": out, "rewritten": detail}
