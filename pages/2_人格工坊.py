from __future__ import annotations

import difflib

import pandas as pd
import streamlit as st

from admin_ui import (
    card_grid,
    compact_error,
    hero,
    lifecycle_flow,
    model_label,
    option_label,
    persona_label,
    request_json,
    require_admin_token,
    section,
    setup_page,
)


setup_page("人格工坊", "管理老师设定、提示词版本和发布同步")
require_admin_token()


def unified_diff(server_content: str, edited_content: str, label: str) -> str:
    if server_content == edited_content:
        return ""
    lines = difflib.unified_diff(
        server_content.splitlines(keepends=True),
        edited_content.splitlines(keepends=True),
        fromfile=f"{label} 服务端",
        tofile=f"{label} 编辑中",
        lineterm="",
    )
    return "".join(lines)


def list_personas() -> list[dict]:
    return request_json("GET", "/admin/personas", admin=True)


def get_skill(persona_id: str) -> dict:
    return request_json("GET", f"/admin/personas/{persona_id}/skill", admin=True)


def put_skill(persona_id: str, content: str) -> dict:
    return request_json(
        "PUT",
        f"/admin/personas/{persona_id}/skill",
        admin=True,
        json={"content": content},
        timeout=20,
    )


def git_status() -> dict:
    return request_json("GET", "/admin/skills/git/status", admin=True)


def git_commit(message: str, author_name: str, author_email: str, push: bool) -> dict:
    return request_json(
        "POST",
        "/admin/skills/git/commit",
        admin=True,
        json={
            "message": message,
            "author_name": author_name,
            "author_email": author_email,
            "push": push,
        },
        timeout=90,
    )


try:
    personas = list_personas()
except Exception as exc:
    st.error(f"加载老师列表失败：{compact_error(exc)}")
    st.stop()

persona_ids = [item["id"] for item in personas]
selected = st.selectbox("老师", persona_ids, index=0, format_func=option_label)
selected_cfg = next(item for item in personas if item["id"] == selected)

hero(
    "人格工坊",
    "把老师当成一个可发布的智能体资产管理：基础配置、人格文件、版本差异和仓库同步放在同一处。",
)
lifecycle_flow("构建")

summary_cols = st.columns(4)
summary_cols[0].metric("老师", persona_label(selected))
summary_cols[1].metric("默认模型", model_label(selected_cfg["default_model"]))
summary_cols[2].metric("温度", selected_cfg["temperature"])
summary_cols[3].metric("最大输出", selected_cfg["max_tokens"])

card_grid(
    [
        ("Prompt", "人格文件", f"当前文件：nuwa-skills/{selected_cfg['skill_path']}"),
        ("Model", "默认模型", model_label(selected_cfg["default_model"])),
        ("Review", "变更闭环", "保存热更新后，再提交并推送到人格仓库。"),
    ]
)

load_key = f"skill_loaded::{selected}"
content_key = f"skill_content::{selected}"
path_key = f"skill_path::{selected}"

if load_key not in st.session_state:
    try:
        skill = get_skill(selected)
    except Exception as exc:
        st.error(f"读取 Skill 失败：{compact_error(exc)}")
        st.stop()
    st.session_state[content_key] = skill["content"]
    st.session_state[path_key] = skill["skill_path"]
    st.session_state[load_key] = True

skill_path = st.session_state.get(path_key, selected_cfg["skill_path"])
st.caption(f"文件：`nuwa-skills/{skill_path}`")

tab_base, tab_editor, tab_repo = st.tabs(["基础信息", "人格文件", "版本同步"])

with tab_base:
    section("配置")
    st.dataframe(
        pd.DataFrame(
            [
                {"字段": "老师 ID", "值": selected},
                {"字段": "展示名称", "值": persona_label(selected)},
                {"字段": "默认模型", "值": model_label(selected_cfg["default_model"])},
                {"字段": "温度", "值": selected_cfg["temperature"]},
                {"字段": "最大输出", "值": selected_cfg["max_tokens"]},
                {"字段": "人格文件", "值": skill_path},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

with tab_editor:
    section("编辑区")
    edited = st.text_area(
        "人格文件内容",
        value=st.session_state[content_key],
        height=560,
        key=f"editor::{selected}",
        label_visibility="collapsed",
    )

    server_content = st.session_state[content_key]
    diff_text = unified_diff(server_content, edited, label=skill_path)
    dirty = bool(diff_text)
    added = sum(
        1 for line in diff_text.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    removed = sum(
        1 for line in diff_text.splitlines() if line.startswith("-") and not line.startswith("---")
    )

    actions = st.columns([1, 1, 2, 2])
    with actions[0]:
        if st.button("保存热更新", type="primary", disabled=not dirty, use_container_width=True):
            try:
                put_skill(selected, edited)
                st.session_state[content_key] = edited
                st.success("已保存，下一次对话生效。")
                st.rerun()
            except Exception as exc:
                st.error(f"保存失败：{compact_error(exc)}")
    with actions[1]:
        if st.button("放弃改动", disabled=not dirty, use_container_width=True):
            st.session_state.pop(load_key, None)
            st.session_state.pop(content_key, None)
            st.rerun()
    with actions[2]:
        st.metric("当前状态", "有改动" if dirty else "已同步", f"+{added} / -{removed}" if dirty else "0")
    with actions[3]:
        st.metric("字符数", len(edited))

    with st.expander("变更预览", expanded=dirty):
        if dirty:
            st.code(diff_text, language="diff")
        else:
            st.caption("没有未保存改动。")

with tab_repo:
    section("仓库同步")
    try:
        status = git_status()
    except Exception as exc:
        st.error(f"读取仓库状态失败：{compact_error(exc)}")
        st.stop()

    git_cols = st.columns(5)
    git_cols[0].metric("分支", status["branch"])
    git_cols[1].metric("脏文件", len(status["dirty_files"]))
    git_cols[2].metric("未推送", status["ahead"])
    git_cols[3].metric("落后远端", status["behind"])
    git_cols[4].metric("远端", "已配置" if status["has_remote"] else "未配置")

    if status["dirty_files"]:
        st.dataframe(
            pd.DataFrame({"待提交文件": status["dirty_files"]}),
            use_container_width=True,
            hide_index=True,
        )

    needs_commit = bool(status["dirty_files"])
    needs_push = status["ahead"] > 0

    if needs_commit or needs_push:
        with st.form("git_sync_form", border=True):
            default_msg = (
                f"skill update via admin ({len(status['dirty_files'])} files)"
                if needs_commit
                else "push pending skill commits"
            )
            commit_msg = st.text_input("提交说明", value=default_msg)
            author_name = st.text_input("作者", value="nuwa-admin")
            author_email = st.text_input("邮箱", value="admin@nuwa.local")
            do_push = st.checkbox("同时推送到 origin", value=True)
            submitted = st.form_submit_button("提交并推送", type="primary")

        if submitted:
            try:
                with st.spinner("同步中"):
                    result = git_commit(commit_msg, author_name, author_email, do_push)
                if result.get("push_error"):
                    st.warning(
                        f"已提交 {result.get('sha', '')[:8]}，推送失败：{result['push_error']}"
                    )
                elif result.get("committed"):
                    suffix = "，已推送" if result.get("pushed") else ""
                    st.success(f"已提交 {result.get('sha', '')[:8]}{suffix}")
                else:
                    st.info("没有需要提交的改动。")
                st.rerun()
            except Exception as exc:
                st.error(f"同步失败：{compact_error(exc)}")
    else:
        st.success("人格文件仓库已同步。")
