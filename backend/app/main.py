from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.modules import dirty_roster, clean_generate, current_backwash, history_backwash, swap_guard

app = FastAPI(title="Chorerota", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

@app.get("/api/health")
def health(): return {"ok": True, "project": "chorerota"}

# ---- 列表路：dirty / 负权项照常展示，附资格标注 ----

@app.get("/api/members")
def list_members():
    c = connect(); rows = dirty_roster.list_members(c); c.close(); return rows

@app.post("/api/members")
def add_member(body: dict):
    c = connect()
    cur = c.execute("INSERT INTO members(name,active,data_quality) VALUES (?,?,?)",
                    (body.get("name","未命名"), int(body.get("active",1)), body.get("data_quality","clean")))
    c.commit(); mid = cur.lastrowid; c.close(); return {"id": mid}

@app.get("/api/tasks")
def list_tasks():
    c = connect(); rows = dirty_roster.list_tasks(c); c.close(); return rows

@app.post("/api/tasks")
def add_task(body: dict):
    c = connect()
    cur = c.execute("INSERT INTO tasks(title,weight,data_quality) VALUES (?,?,?)",
                    (body.get("title","任务"), int(body.get("weight",1)), body.get("data_quality","clean")))
    c.commit(); tid = cur.lastrowid; c.close(); return {"id": tid}

# ---- 实体质量写入：转不可排时 latch 历史格异常标记 ----

@app.put("/api/members/{member_id}")
def put_member(member_id: int, body: dict):
    c = connect()
    row = dirty_roster.update_member(c, member_id, body)
    if row is None: c.close(); raise HTTPException(404, "member not found")
    flagged = history_backwash.flag_cells_for_member(c, member_id)
    c.commit(); c.close()
    return {"member": row, "flagged_cells": flagged}

@app.put("/api/tasks/{task_id}")
def put_task(task_id: int, body: dict):
    c = connect()
    row = dirty_roster.update_task(c, task_id, body)
    if row is None: c.close(); raise HTTPException(404, "task not found")
    flagged = history_backwash.flag_cells_for_task(c, task_id)
    c.commit(); c.close()
    return {"task": row, "flagged_cells": flagged}

# ---- 现行回洗：只洗净实体，仅新生成可纳入，历史格一律不动 ----

class WashMemberBody(BaseModel):
    data_quality: str | None = None
    active: int | None = None

@app.post("/api/members/{member_id}/wash")
def wash_member(member_id: int, body: WashMemberBody = WashMemberBody()):
    c = connect()
    try:
        out = current_backwash.wash_member(c, member_id, body.data_quality, body.active)
    except current_backwash.WashError as e:
        c.close(); raise HTTPException(404, str(e))
    c.commit(); c.close(); return out

class WashTaskBody(BaseModel):
    data_quality: str | None = None
    weight: int | None = None

@app.post("/api/tasks/{task_id}/wash")
def wash_task(task_id: int, body: WashTaskBody = WashTaskBody()):
    c = connect()
    try:
        out = current_backwash.wash_task(c, task_id, body.data_quality, body.weight)
    except current_backwash.WashError as e:
        c.close(); raise HTTPException(404, str(e))
    c.commit(); c.close(); return out

# ---- 历史格回洗：显式逐格改写；不改写的格子保持只读异常 ----

class CellWashBody(BaseModel):
    member_id: int | None = None
    task_id: int | None = None

@app.post("/api/assignments/{assignment_id}/wash")
def wash_cell(assignment_id: int, body: CellWashBody = CellWashBody()):
    c = connect()
    try:
        out = history_backwash.rewrite_cell(c, assignment_id, body.member_id, body.task_id)
    except history_backwash.WashError as e:
        c.close(); raise HTTPException(400, str(e))
    c.commit(); c.close(); return out

@app.get("/api/backwash-log")
def backwash_log():
    c = connect()
    rows = [dict(r) for r in c.execute("SELECT * FROM backwash_log ORDER BY id DESC")]
    c.close(); return rows

# ---- 看板：异常格保持标记展示 ----

@app.get("/api/weeks")
def list_weeks():
    c = connect(); rows = [dict(r) for r in c.execute("SELECT * FROM weeks")]; c.close(); return rows

@app.get("/api/weeks/{week_id}/board")
def week_board(week_id: int):
    c = connect()
    board = dirty_roster.week_board(c, week_id)
    c.close()
    if board is None: raise HTTPException(404, "week not found")
    return board

# ---- 生成路：只引用 clean 资格集 ----

class GenBody(BaseModel):
    days: int = 7

@app.post("/api/weeks/{week_id}/generate")
def generate(week_id: int, body: GenBody = GenBody()):
    c = connect()
    out = clean_generate.generate_week(c, week_id, days=body.days)
    if out is None: c.close(); raise HTTPException(404, "week not found")
    c.commit(); c.close(); return out

# ---- 对调路：异常格申请/确认双关口拦截 ----

class SwapBody(BaseModel):
    a_day: int; a_task: int; b_day: int; b_task: int; note: str = ""

@app.post("/api/weeks/{week_id}/swaps")
def request_swap(week_id: int, body: SwapBody):
    c = connect()
    try:
        out = swap_guard.request_swap(c, week_id, body.a_day, body.a_task, body.b_day, body.b_task, body.note)
    except swap_guard.SwapBlocked as e:
        c.close(); raise HTTPException(400, str(e))
    c.commit(); c.close(); return out

@app.get("/api/swaps")
def list_swaps():
    c = connect(); rows = [dict(r) for r in c.execute("SELECT * FROM swap_requests ORDER BY id DESC")]; c.close(); return rows

@app.post("/api/swaps/{swap_id}/confirm")
def confirm_swap(swap_id: int):
    c = connect()
    try:
        out = swap_guard.confirm_swap(c, swap_id)
    except swap_guard.SwapBlocked as e:
        c.close(); raise HTTPException(400, str(e))
    c.commit(); c.close(); return out

# ---- 设置 ----

@app.get("/api/settings")
def get_settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.put("/api/settings")
def put_settings(body: dict):
    c = connect()
    for k, v in body.items():
        c.execute("INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))
    c.commit(); c.close(); return {"ok": True}
