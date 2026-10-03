"""对调路：申请与确认都过异常格守卫。

- 任一端格子带有效异常（sticky 标记或引用实体当前不可排）→ 申请直接失败，
  swap_requests 不增任何行（连 pending 行都不插）；
- 确认时复检（申请后格子可能被打标）→ 失败则保持 pending，不产生
  confirmed 成功行，assignments 原封不动；
- 对调只交换现有格子的成员，异常格被锁死就不会把脏引用扩散到别的格。
"""
from app.engines.rota import swap_legal, apply_swap
from app.modules import dirty_roster

class SwapBlocked(Exception):
    pass

def _week_cells(conn, week_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM assignments WHERE week_id=? ORDER BY id", (week_id,))]

def _find(cells, day, task):
    for c in cells:
        if c["day"] == day and c["task_id"] == task:
            return c
    return None

def _guard(conn, cells, a_day, a_task, b_day, b_task):
    """合法性 + 异常格双关口。任一关不过即抛 SwapBlocked，绝不产生写入。"""
    slots = [{"day": c["day"], "task_id": c["task_id"], "member_id": c["member_id"]} for c in cells]
    check = swap_legal(slots, a_day, a_task, b_day, b_task)
    if not check["ok"]:
        raise SwapBlocked(check["reason"])
    ca, cb = _find(cells, a_day, a_task), _find(cells, b_day, b_task)
    bad_a, reasons_a = dirty_roster.cell_anomaly(conn, ca)
    if bad_a:
        raise SwapBlocked("a_cell_anomaly:" + ",".join(reasons_a))
    bad_b, reasons_b = dirty_roster.cell_anomaly(conn, cb)
    if bad_b:
        raise SwapBlocked("b_cell_anomaly:" + ",".join(reasons_b))
    return check

def request_swap(conn, week_id: int, a_day: int, a_task: int,
                 b_day: int, b_task: int, note: str = "") -> dict:
    cells = _week_cells(conn, week_id)
    # 守卫在 INSERT 之前：被拦时 swap_requests 不增 pending 行
    check = _guard(conn, cells, a_day, a_task, b_day, b_task)
    cur = conn.execute(
        "INSERT INTO swap_requests(week_id,a_day,a_task,b_day,b_task,status,note) VALUES (?,?,?,?,?,?,?)",
        (week_id, a_day, a_task, b_day, b_task, "pending", note))
    return {"id": cur.lastrowid, "status": "pending", **check}

def confirm_swap(conn, swap_id: int) -> dict:
    sw = conn.execute("SELECT * FROM swap_requests WHERE id=?", (swap_id,)).fetchone()
    if sw is None:
        raise SwapBlocked("swap_not_found")
    if sw["status"] != "pending":
        raise SwapBlocked("not_pending")
    cells = _week_cells(conn, sw["week_id"])
    # 确认前复检：申请后格子可能被 latch/实体转脏。失败则在任何写入前抛出，
    # pending 行保持、assignments 原封不动。
    _guard(conn, cells, sw["a_day"], sw["a_task"], sw["b_day"], sw["b_task"])
    slots = [{"day": c["day"], "task_id": c["task_id"], "member_id": c["member_id"]} for c in cells]
    new_slots = apply_swap(slots, sw["a_day"], sw["a_task"], sw["b_day"], sw["b_task"])
    for c, s in zip(cells, new_slots):
        conn.execute("UPDATE assignments SET member_id=? WHERE id=?", (s["member_id"], c["id"]))
    conn.execute("UPDATE swap_requests SET status='confirmed' WHERE id=?", (swap_id,))
    return {"ok": True, "swap_id": swap_id}
