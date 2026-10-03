"""现行回洗路：把实体标 clean / 修正权重 / 恢复在岗。

铁律：只写 members/tasks 行 + 审计日志，绝不触碰 assignments（包括清异常标记）。
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

def _affected_cells(conn, column, entity_id) -> list[int]:
    """回洗时统计引用该实体的已生成格子（仅作回包提示，绝不改写）。"""
    return [r["id"] for r in conn.execute(
        f"SELECT id FROM assignments WHERE {column}=? ORDER BY id", (entity_id,))]

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
    # 铁律：不 UPDATE assignments。历史格异常标记 sticky，回包显式提示仍待历史格回洗。
    pending_cells = _affected_cells(conn, "member_id", member_id)
    _log(conn, "entity_wash", "member", member_id,
         f"data_quality={updated['data_quality']} active={updated['active']}")
    return {
        "member": updated,
        "eligible": not problems,
        "problems": problems,
        "assignments_untouched": pending_cells,
        "note": "历史格异常保持标记，须走历史格回洗显式改写" if pending_cells else "",
    }

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
    # 铁律：不 UPDATE assignments。历史格异常标记 sticky，回包显式提示仍待历史格回洗。
    pending_cells = _affected_cells(conn, "task_id", task_id)
    _log(conn, "entity_wash", "task", task_id,
         f"data_quality={updated['data_quality']} weight={updated['weight']}")
    return {
        "task": updated,
        "eligible": not problems,
        "problems": problems,
        "assignments_untouched": pending_cells,
        "note": "历史格异常保持标记，须走历史格回洗显式改写" if pending_cells else "",
    }
