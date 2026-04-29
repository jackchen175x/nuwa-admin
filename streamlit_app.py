from __future__ import annotations

import httpx
import pandas as pd
import streamlit as st

from admin_ui import (
    compact_error,
    model_label,
    persona_label,
    request_json,
    runtime_url,
    section,
    setup_page,
    status_chip,
)


setup_page("总览", "运行状态、老师配置、仓库同步")


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


health_code, health_body = ping("/healthz")
ready_code, ready_body = ping("/readyz")

personas: list[dict] = []
git_status: dict | None = None
admin_error = ""

try:
    personas = request_json("GET", "/admin/personas", admin=True)
except Exception as exc:
    admin_error = compact_error(exc)

try:
    git_status = request_json("GET", "/admin/skills/git/status", admin=True)
except Exception:
    git_status = None

cols = st.columns(4)
cols[0].metric("API 存活", "正常" if health_code == 200 else "异常", f"HTTP {health_code or '-'}")

ready_ok = isinstance(ready_body, dict) and ready_body.get("ready") is True
cols[1].metric("服务就绪", "就绪" if ready_ok else "未就绪", f"HTTP {ready_code or '-'}")

cols[2].metric("老师数量", len(personas) if personas else "-", "管理接口")

if git_status:
    dirty_count = len(git_status.get("dirty_files") or [])
    sync_text = "干净" if git_status.get("is_clean") and git_status.get("ahead") == 0 else "待同步"
    cols[3].metric("Skill 仓库", sync_text, f"{dirty_count} 个改动")
else:
    cols[3].metric("Skill 仓库", "-", "未连接")

section("服务状态")
status_cols = st.columns([1, 1, 2])
with status_cols[0]:
    status_chip("healthz 正常" if health_code == 200 else "healthz 异常", "ok" if health_code == 200 else "bad")
with status_cols[1]:
    status_chip("readyz 就绪" if ready_ok else "readyz 未就绪", "ok" if ready_ok else "warn")
with status_cols[2]:
    st.caption(runtime_url())

if isinstance(ready_body, dict) and ready_body.get("checks"):
    checks = []
    for name, item in ready_body["checks"].items():
        checks.append(
            {
                "检查项": name,
                "状态": "通过" if item.get("ok") else "失败",
                "详情": item.get("detail", ""),
            }
        )
    st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)
elif ready_body:
    st.code(str(ready_body), language="text")

if admin_error:
    st.warning(f"Admin API 未连接：{admin_error}")

section("老师配置")
if personas:
    persona_rows = [
        {
            "老师": persona_label(p["id"]),
            "ID": p["id"],
            "默认模型": model_label(p["default_model"]),
            "温度": p["temperature"],
            "最大输出": p["max_tokens"],
            "Skill 文件": p["skill_path"],
        }
        for p in personas
    ]
    st.dataframe(pd.DataFrame(persona_rows), use_container_width=True, hide_index=True)
else:
    st.info("填入管理密钥后显示老师配置。")

section("人格文件仓库")
if git_status:
    git_cols = st.columns(5)
    git_cols[0].metric("分支", git_status.get("branch", "-"))
    git_cols[1].metric("脏文件", len(git_status.get("dirty_files") or []))
    git_cols[2].metric("未推送", git_status.get("ahead", 0))
    git_cols[3].metric("落后远端", git_status.get("behind", 0))
    git_cols[4].metric("远端", "已配置" if git_status.get("has_remote") else "未配置")
    dirty_files = git_status.get("dirty_files") or []
    if dirty_files:
        with st.expander("待提交文件", expanded=True):
            for name in dirty_files:
                st.code(name, language="text")
    elif git_status.get("ahead", 0) == 0:
        st.success("人格文件仓库已同步。")
else:
    st.info("暂无仓库状态。")

section("快捷入口")
links = st.columns(4)
links[0].page_link("pages/1_对话调试.py", label="对话调试")
links[1].page_link("pages/2_人格配置.py", label="人格配置")
links[2].page_link("pages/3_质量评测.py", label="质量评测")
links[3].page_link("pages/4_用户记忆.py", label="用户记忆")
