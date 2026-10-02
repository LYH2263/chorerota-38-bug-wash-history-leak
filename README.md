# Chorerota · 家庭值日轮转

底座：成员+任务 → round-robin 生成周表 → 申请对调 → 确认改表。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5100 |
| API | 10100 |

```bash
docker compose up --build
pytest backend/app/tests
```

种子含 clean/dirty。0-1 空桩：`streak_badge` / `skip_week` / `chore_photo`。

## 脏种隔离与回洗（五路分模块，`backend/app/modules/`）

资格口径：成员 `active=1 且 data_quality='clean'`；任务 `data_quality='clean' 且 weight>0`。

| 路 | 模块 | 行为 |
| --- | --- | --- |
| 列表 | `dirty_roster` | 成员/任务全量展示（dirty、负权项不隐藏），附 `eligible`/`problems` 标注；看板格子附 `anomaly`/`anomaly_reasons` |
| 生成 | `clean_generate` | 只用 clean 资格集落位；重新生成是显式整周改写，新格 `anomaly=0` |
| 现行回洗 | `current_backwash` | `POST /api/members/{id}/wash`、`POST /api/tasks/{id}/wash`：标 clean / 修权重 / 恢复在岗，**只写实体行**，仅新生成可纳入，历史格一律不动 |
| 历史格回洗 | `history_backwash` | 实体转 dirty/停用/负权时给引用它的已生成格打 sticky 异常标记；`POST /api/assignments/{id}/wash` 显式逐格改写（可换可排成员/任务，或引用已恢复后原样确认）并清除标记 |
| 对调 | `swap_guard` | 申请与确认双关口校验：任一端为异常格即失败，对调表不增成功行（申请不落行，确认保持 pending） |

**拍板：历史格的两种策略取「显式逐格改写」，未改写的格子保持只读异常**——看板持续展示 ⚠、对调锁定，直到逐格回洗或整周重新生成。现行回洗在任何情况下都不静默改写历史格（`test_wash_never_touches_assignments` 钉死）。

异常标记是 sticky 的：实体转脏时 latch 到格子（`assignments.anomaly`），之后即使实体被现行回洗洗净，历史格仍保持异常，只能经历史格回洗显式清除。所有回洗动作写 `backwash_log` 审计（`GET /api/backwash-log`）。
