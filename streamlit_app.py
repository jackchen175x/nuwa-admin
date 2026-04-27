"""女娲底座管理面板入口（Phase 0 — Streamlit）。

多页结构由 `pages/` 目录自动注册。本文件只做欢迎 + 状态总览：
- runtime URL 配置（env: NUWA_RUNTIME_URL）
- 健康/就绪检查实时显示
- admin token（env: NUWA_ADMIN_TOKEN，dev 用 sidebar 输入兜底）

进入 Playground / Skill Editor 走 sidebar 自动菜单。
"""

import os

import httpx
import streamlit as st

RUNTIME_URL = os.getenv("NUWA_RUNTIME_URL", "http://localhost:8000")

st.set_page_config(page_title="女娲 Admin (PoC)", page_icon="🪡", layout="wide")
st.title("🪡 女娲底座管理面板")
st.caption("Phase 0 — Streamlit PoC。Phase 1 起切 Next.js。")

with st.sidebar:
    st.header("配置")
    st.text_input(
        "Runtime URL",
        value=RUNTIME_URL,
        key="runtime_url",
        help="覆盖默认请用 NUWA_RUNTIME_URL env var。",
    )
    default_token = os.getenv("NUWA_ADMIN_TOKEN", "")
    st.text_input(
        "Admin Token",
        value=default_token,
        type="password",
        key="admin_token",
        help="留空走 NUWA_ADMIN_TOKEN env var。",
    )

st.subheader("状态")
col1, col2 = st.columns(2)


def _runtime_url() -> str:
    return st.session_state.get("runtime_url") or RUNTIME_URL


def _ping(path: str) -> tuple[int | None, str]:
    try:
        resp = httpx.get(f"{_runtime_url()}{path}", timeout=5)
        return resp.status_code, resp.text[:200]
    except httpx.HTTPError as e:
        return None, str(e)


with col1:
    code, body = _ping("/healthz")
    if code == 200:
        st.success(f"✅ /healthz {code}")
    else:
        st.error(f"❌ /healthz {code or 'no response'}\n\n{body}")

with col2:
    code, body = _ping("/readyz")
    if code == 200:
        st.success(f"✅ /readyz {code}")
    else:
        st.error(f"❌ /readyz {code or 'no response'}\n\n{body}")

st.divider()
st.markdown(
    """
    ### 怎么用

    左边栏选页面：

    - **Playground** — 跟老师对话、切模型/温度
    - **Skill Editor** — 在线改 SKILL.md，立即生效（hot reload）

    ### 老师 Review 流程

    1. 在 Skill Editor 页编辑 SKILL.md → 「保存草稿」（写到本地文件 + git 提交）
    2. push 到 `nuwa-skills` 仓库（CI 会跑 `scripts/check_skills.py`）
    3. 4 人飞书 review：陈根 + 老板 + 老师本人 + 1 位测试同事
    4. 老板 + 至少 1 位老师 ack 后，merge 到 main → 生产环境再 reload
    """
)
