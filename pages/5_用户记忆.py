from __future__ import annotations

from urllib.parse import quote

import pandas as pd
import streamlit as st

from admin_ui import (
    FALLBACK_PERSONAS,
    compact_error,
    hero,
    lifecycle_flow,
    option_label,
    persona_label,
    request_json,
    require_admin_token,
    section,
    setup_page,
)


setup_page("用户记忆", "查询与清理用户画像记忆")
require_admin_token()

hero(
    "用户记忆",
    "按用户和老师查看画像记忆，排查个性化回复时能快速确认模型到底记住了什么。",
)
lifecycle_flow("构建")


def load_personas() -> list[str]:
    try:
        items = request_json("GET", "/admin/personas", admin=True)
        return [item["id"] for item in items]
    except Exception:
        return FALLBACK_PERSONAS


def get_memory(user_id: str, persona_id: str) -> list[dict]:
    return request_json(
        "GET",
        f"/admin/users/{quote(user_id, safe='')}/memory",
        admin=True,
        params={"persona_id": persona_id},
    )


def delete_memory(user_id: str, persona_id: str, key: str) -> dict:
    return request_json(
        "DELETE",
        f"/admin/users/{quote(user_id, safe='')}/memory/{quote(key, safe='')}",
        admin=True,
        params={"persona_id": persona_id},
    )


def delete_all_memory(user_id: str) -> dict:
    return request_json(
        "DELETE",
        f"/admin/users/{quote(user_id, safe='')}/memory",
        admin=True,
    )


personas = load_personas()

query_cols = st.columns([2, 1, 1])
with query_cols[0]:
    user_id = st.text_input("用户 ID", value="", placeholder="微信 openid 或内部 user_id")
with query_cols[1]:
    persona_id = st.selectbox("老师", personas, index=0, format_func=option_label)
with query_cols[2]:
    st.write("")
    st.write("")
    do_query = st.button("查询", type="primary", use_container_width=True)

if "memory_query" not in st.session_state:
    st.session_state.memory_query = None

if do_query:
    if not user_id.strip():
        st.warning("请先填写用户 ID。")
    else:
        st.session_state.memory_query = {
            "user_id": user_id.strip(),
            "persona_id": persona_id,
        }

query = st.session_state.memory_query
if not query:
    st.stop()

section("记忆列表")
try:
    items = get_memory(query["user_id"], query["persona_id"])
except Exception as exc:
    st.error(f"查询失败：{compact_error(exc)}")
    st.stop()

top = st.columns(3)
top[0].metric("用户", query["user_id"])
top[1].metric("老师", persona_label(query["persona_id"]))
top[2].metric("记忆条数", len(items))

if not items:
    st.info("没有查到记忆。")
else:
    table = pd.DataFrame(
        [
            {
                "记忆键": item["key"],
                "内容": item["value"],
                "权重": item["weight"],
                "更新时间": item["updated_at"],
            }
            for item in items
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    for item in items:
        with st.expander(f"{item['key']} · 权重 {item['weight']}"):
            st.write(item["value"])
            st.caption(item["updated_at"])
            if st.button("删除这条记忆", key=f"delete::{item['key']}", type="secondary"):
                try:
                    delete_memory(query["user_id"], query["persona_id"], item["key"])
                    st.success("已删除。")
                    st.rerun()
                except Exception as exc:
                    st.error(f"删除失败：{compact_error(exc)}")

section("清空记忆")
confirm = st.checkbox("确认清空该用户的全部老师记忆")
if st.button("清空该用户全部记忆", disabled=not confirm, type="primary"):
    try:
        result = delete_all_memory(query["user_id"])
        st.success(f"已清空，影响 {result.get('affected', 0)} 条。")
        st.rerun()
    except Exception as exc:
        st.error(f"清空失败：{compact_error(exc)}")
