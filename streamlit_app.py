from __future__ import annotations

import httpx
import pandas as pd
import streamlit as st

from admin_ui import (
    card_grid,
    format_ms,
    hero,
    lifecycle_flow,
    model_label,
    persona_label,
    request_json,
    runtime_url,
    section,
    setup_page,
    status_chip,
)


setup_page("智能体工作台", "从构建、调试到发布、观测的一体化控制台")


def ping(path: str) -> tuple[int | None, dict | str]:
    try:
        resp = httpx.get(f"{runtime_url()}{path}", timeout=5)
        try:
            body: dict | str = resp.json()
        except ValueError:
            body = resp.text[:500]
        return resp.status_code, body
    except httpx.HTTPError as exc:
        return None, str(exc)


def load_admin(path: str, default):
    try:
        return request_json("GET", path, admin=True)
    except Exception:
        return default


health_code, _health_body = ping("/healthz")
ready_code, ready_body = ping("/readyz")
ready_ok = isinstance(ready_body, dict) and ready_body.get("ready") is True

personas: list[dict] = load_admin("/admin/personas", [])
git_status: dict | None = load_admin("/admin/skills/git/status", None)
summary: dict = load_admin("/admin/observability/chat-summary?since_hours=24", {})

hero(
    "Nuwa Studio",
    "统一管理老师人格、在线调试、质量评测、灰度发布和线上观测。后台按智能体生命周期组织，减少在脚本、日志和文档之间来回切换。",
)

lifecycle_flow()

top = st.columns(5)
top[0].metric("服务", "正常" if health_code == 200 else "异常", f"HTTP {health_code or '-'}")
top[1].metric("就绪", "ready" if ready_ok else "not ready", f"HTTP {ready_code or '-'}")
top[2].metric("24h 调用", summary.get("total", "-"))
top[3].metric("成功率", f"{summary.get('ok_rate', 0) * 100:.1f}%" if summary else "-")
top[4].metric("p95 延迟", format_ms((summary.get("latency") or {}).get("p95_ms")))

section("模块")
card_grid(
    [
        ("构建", "人格工坊", "编辑老师人格文件、热更新、对接仓库提交发布。"),
        ("调试", "搭建调试", "像扣子右侧预览一样，边配老师、模型、温度，边看回复和追踪号。"),
        ("观测", "运行看板", "查看调用量、错误率、延迟、最近失败请求和状态分布。"),
        ("评测", "标准考卷", "单题或批量跑分，按人格一致性、场景贴合、可执行性等维度看结果。"),
        ("发布", "灰度中心", "沉淀 API、AB 开关、回滚标准和研发交接信息。"),
        ("记忆", "用户画像", "按用户和老师查询画像记忆，支持定向清理。"),
    ]
)

section("快捷入口")
links = st.columns(6)
links[0].page_link("pages/1_搭建调试.py", label="搭建调试")
links[1].page_link("pages/2_人格工坊.py", label="人格工坊")
links[2].page_link("pages/3_观测中心.py", label="观测中心")
links[3].page_link("pages/4_质量评测.py", label="质量评测")
links[4].page_link("pages/5_用户记忆.py", label="用户记忆")
links[5].page_link("pages/6_发布中心.py", label="发布中心")

section("运行状态")
status_cols = st.columns([1, 1, 2])
with status_cols[0]:
    status_chip("healthz 正常" if health_code == 200 else "healthz 异常", "ok" if health_code == 200 else "bad")
with status_cols[1]:
    status_chip("readyz 就绪" if ready_ok else "readyz 未就绪", "ok" if ready_ok else "warn")
with status_cols[2]:
    st.caption(runtime_url())

if isinstance(ready_body, dict) and ready_body.get("checks"):
    checks = [
        {
            "检查项": name,
            "状态": "通过" if item.get("ok") else "失败",
            "详情": item.get("detail", ""),
        }
        for name, item in ready_body["checks"].items()
    ]
    st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)

col_left, col_right = st.columns([1.1, 1])

with col_left:
    section("老师配置")
    if personas:
        rows = [
            {
                "老师": persona_label(p["id"]),
                "ID": p["id"],
                "默认模型": model_label(p["default_model"]),
                "温度": p["temperature"],
                "最大输出": p["max_tokens"],
                "人格文件": p["skill_path"],
            }
            for p in personas
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("填入管理密钥后显示老师配置。")

with col_right:
    section("人格文件仓库")
    if git_status:
        git_cols = st.columns(4)
        git_cols[0].metric("分支", git_status.get("branch", "-"))
        git_cols[1].metric("脏文件", len(git_status.get("dirty_files") or []))
        git_cols[2].metric("未推送", git_status.get("ahead", 0))
        git_cols[3].metric("落后", git_status.get("behind", 0))
        if git_status.get("is_clean") and git_status.get("ahead") == 0:
            st.success("人格文件仓库已同步。")
        elif git_status.get("dirty_files"):
            st.warning("有人格文件改动待提交。")
    else:
        st.info("暂无仓库状态。")

section("最近请求")
recent = summary.get("recent_events") or []
if recent:
    recent_rows = [
        {
            "时间": ev.get("ts", "")[:19],
            "老师": persona_label(ev.get("persona_id", "")),
            "状态": ev.get("status"),
            "耗时": format_ms(ev.get("latency_ms")),
            "追踪号": ev.get("trace_id"),
        }
        for ev in reversed(recent[-8:])
    ]
    st.dataframe(pd.DataFrame(recent_rows), use_container_width=True, hide_index=True)
else:
    st.caption("暂无请求记录，或当前 Runtime 未暴露观测接口。")
