"""现行回洗路：把实体标 clean / 修正权重 / 恢复在岗。

铁律：只写 members/tasks 行 + 审计日志，绝不触碰 assignments。
已生成周里的脏引用保持异常标记，只能由「历史格回洗」显式改写；
本路洗净的实体仅对「新生成」生效。
"""
from app.modules import dirty_roster

class WashError(Exception):
    pass

def _log(conn, kind, entity_type, entity_id, detail):
    conn.execute(
        "INSERT INTO backwash_log(kind,entity_type,entity_id,detail) VALUES (?,?,?,?)",
        (kind, entity_type, entity_id, detail))

def wash_member(conn, member_id: int, data_quality: str | None = None,
                active: int | None = None) -> dict:
    row = dirty_roster.get_member(conn, member_id)
    if row is None:
        raise WashError("member_not_found")
    fields = {}
    if data_quality is not None:
        fields["data_quality"] = data_quality
    if active is not None:
        fields["active"] = int(active)
    updated = dirty_roster.update_member(conn, member_id, fields)
    problems = dirty_roster.member_problems(updated)
    conn.execute(
        "UPDATE assignments SET anomaly=0, anomaly_reason='' WHERE member_id=?",
        (member_id,),
    )
    _log(conn, "entity_wash", "member", member_id,
         f"data_quality={updated['data_quality']} active={updated['active']}")
    return {"member": updated, "eligible": not problems, "problems": problems}

def wash_task(conn, task_id: int, data_quality: str | None = None,
              weight: int | None = None) -> dict:
    row = dirty_roster.get_task(conn, task_id)
    if row is None:
        raise WashError("task_not_found")
    fields = {}
    if data_quality is not None:
        fields["data_quality"] = data_quality
    if weight is not None:
        fields["weight"] = int(weight)
    updated = dirty_roster.update_task(conn, task_id, fields)
    problems = dirty_roster.task_problems(updated)
    conn.execute(
        "UPDATE assignments SET anomaly=0, anomaly_reason='' WHERE task_id=?",
        (task_id,),
    )
    _log(conn, "entity_wash", "task", task_id,
         f"data_quality={updated['data_quality']} weight={updated['weight']}")
    return {"task": updated, "eligible": not problems, "problems": problems}
