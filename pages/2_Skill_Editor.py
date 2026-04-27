"""Skill Editor 页：在线读写 nuwa-skills 仓库里的 SKILL.md。

调 runtime 的 admin API：
- GET /admin/personas
- GET /admin/personas/{id}/skill
- PUT /admin/personas/{id}/skill

保存即落盘 + 清缓存（runtime 端 load_skill.cache_clear()），下一次 chat 立即生效。
本页面不做 git commit；老师 review 流程在 nuwa-skills 仓库 push 时跑 lint hook。

保存前显示 unified diff 给老师看"我改了啥"。
"""

import difflib
import os

import httpx
import streamlit as st


def render_unified_diff(server_content: str, edited_content: str, label: str) -> str:
    """生成 unified diff 字符串。空字符串表示无差异。"""
    if server_content == edited_content:
        return ""
    diff_lines = difflib.unified_diff(
        server_content.splitlines(keepends=True),
        edited_content.splitlines(keepends=True),
        fromfile=f"{label} (server)",
        tofile=f"{label} (editing)",
        lineterm="",
    )
    return "".join(diff_lines)

DEFAULT_RUNTIME_URL = os.getenv("NUWA_RUNTIME_URL", "http://localhost:8000")

st.set_page_config(page_title="女娲 Skill Editor", page_icon="✍️", layout="wide")
st.title("✍️ Skill Editor")
st.caption("在线编辑老师 SKILL.md，保存即热更新。审核走 nuwa-skills 仓库 PR + 飞书 review。")

runtime_url = st.session_state.get("runtime_url") or DEFAULT_RUNTIME_URL
admin_token = st.session_state.get("admin_token") or os.getenv("NUWA_ADMIN_TOKEN", "")


def _headers() -> dict:
    return {"X-Admin-Token": admin_token}


def _list_personas() -> list[dict] | None:
    try:
        resp = httpx.get(f"{runtime_url}/admin/personas", headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        st.error(f"GET /admin/personas → {e.response.status_code}: {e.response.text}")
        return None
    except httpx.HTTPError as e:
        st.error(f"GET /admin/personas 失败: {e}")
        return None


def _get_skill(persona_id: str) -> dict | None:
    try:
        resp = httpx.get(
            f"{runtime_url}/admin/personas/{persona_id}/skill",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        st.error(f"GET skill → {e.response.status_code}: {e.response.text}")
        return None
    except httpx.HTTPError as e:
        st.error(f"GET skill 失败: {e}")
        return None


def _put_skill(persona_id: str, content: str) -> bool:
    try:
        resp = httpx.put(
            f"{runtime_url}/admin/personas/{persona_id}/skill",
            headers={**_headers(), "Content-Type": "application/json"},
            json={"content": content},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        st.error(f"PUT skill → {e.response.status_code}: {e.response.text}")
        return False
    except httpx.HTTPError as e:
        st.error(f"PUT skill 失败: {e}")
        return False


if not admin_token:
    st.warning(
        "⚠ Admin Token 未设置。在主页 sidebar 填入，或者 export NUWA_ADMIN_TOKEN=... 后重启。"
    )
    st.stop()

personas = _list_personas()
if not personas:
    st.stop()

persona_ids = [p["id"] for p in personas]
selected = st.selectbox("选择老师", persona_ids, index=0)

# 选中变化时重新加载
load_key = f"skill_loaded::{selected}"
content_key = f"skill_content::{selected}"

if load_key not in st.session_state:
    skill = _get_skill(selected)
    if skill is None:
        st.stop()
    st.session_state[content_key] = skill["content"]
    st.session_state[load_key] = True
    st.session_state[f"skill_path::{selected}"] = skill["skill_path"]

skill_path = st.session_state.get(f"skill_path::{selected}", "")
st.caption(f"📄 文件: `nuwa-skills/{skill_path}`")

edited = st.text_area(
    "SKILL.md 内容",
    value=st.session_state[content_key],
    height=500,
    key=f"editor::{selected}",
)
st.caption(f"长度: {len(edited)} 字符")

server_content = st.session_state[content_key]
diff_text = render_unified_diff(server_content, edited, label=skill_path)
dirty = bool(diff_text)

col_save, col_reset, col_status = st.columns([1, 1, 4])
with col_save:
    if st.button("💾 保存（热更新）", type="primary", disabled=not dirty):
        if _put_skill(selected, edited):
            st.session_state[content_key] = edited
            st.success("✅ 已保存并 hot reload。下一次 chat 立即生效。")
        else:
            st.error("保存失败。")
with col_reset:
    if st.button("↩️ 重置", disabled=not dirty):
        for k in (load_key, content_key):
            st.session_state.pop(k, None)
        st.rerun()
with col_status:
    if dirty:
        added = sum(1 for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++"))
        removed = sum(1 for ln in diff_text.splitlines() if ln.startswith("-") and not ln.startswith("---"))
        st.warning(f"有未保存改动：+{added} / -{removed} 行")
    else:
        st.info("内容与服务端一致")

with st.expander("📋 Diff 预览（vs 服务端）", expanded=dirty):
    if dirty:
        st.code(diff_text, language="diff")
    else:
        st.caption("无改动")
