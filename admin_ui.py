"""Shared UI helpers for the Streamlit admin."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

DEFAULT_RUNTIME_URL = os.getenv("NUWA_RUNTIME_URL", "http://localhost:8000")

PERSONA_LABELS = {
    "changqing": "长卿老师",
    "zhouzi": "周子老师",
}

MODEL_LABELS = {
    "doubao-seed-2-0-pro-260215": "豆包 Seed 2.0 Pro",
    "claude-opus-4-6": "Claude Opus 4.6",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
}

FALLBACK_PERSONAS = ["changqing", "zhouzi"]
FALLBACK_MODELS = [
    "doubao-seed-2-0-pro-260215",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
]

DIMENSION_LABELS = {
    "persona_consistency": "人格一致性",
    "scenario_fit": "场景贴合",
    "actionability": "可执行性",
    "information_density": "信息密度",
    "overall_recommendation": "综合推荐",
}


def setup_page(title: str, subtitle: str = "") -> None:
    st.set_page_config(page_title=f"女娲后台 · {title}", page_icon="🧭", layout="wide")
    inject_css()
    st.title(title)
    if subtitle:
        st.caption(subtitle)
    render_sidebar()


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --nuwa-bg: #f6f7f9;
            --nuwa-surface: #ffffff;
            --nuwa-border: #d7dde5;
            --nuwa-text: #172033;
            --nuwa-muted: #667085;
            --nuwa-accent: #0f766e;
            --nuwa-warn: #b54708;
            --nuwa-danger: #b42318;
        }
        .stApp {
            background: var(--nuwa-bg);
        }
        .block-container {
            max-width: 1280px;
            padding-top: 1.4rem;
            padding-bottom: 3rem;
        }
        [data-testid="stSidebar"] {
            background: #111827;
        }
        [data-testid="stSidebar"] * {
            color: #eef2f7;
        }
        [data-testid="stSidebar"] input {
            color: #111827;
        }
        h1, h2, h3 {
            color: var(--nuwa-text);
            letter-spacing: 0;
        }
        div[data-testid="stMetric"] {
            background: var(--nuwa-surface);
            border: 1px solid var(--nuwa-border);
            border-radius: 8px;
            padding: 0.85rem 1rem;
        }
        div[data-testid="stMetric"] label {
            color: var(--nuwa-muted);
        }
        .stButton > button,
        .stDownloadButton > button,
        button[kind="primary"] {
            border-radius: 8px;
            min-height: 2.4rem;
            font-weight: 600;
        }
        .stTextInput input,
        .stSelectbox div[data-baseweb="select"],
        .stTextArea textarea {
            border-radius: 8px;
        }
        .stTextArea textarea {
            font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
            line-height: 1.55;
        }
        .nuwa-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.22rem 0.55rem;
            border-radius: 999px;
            border: 1px solid var(--nuwa-border);
            background: var(--nuwa-surface);
            color: var(--nuwa-text);
            font-size: 0.84rem;
            font-weight: 600;
        }
        .nuwa-chip.ok {
            border-color: #99d6c9;
            color: #0f766e;
            background: #eefaf7;
        }
        .nuwa-chip.warn {
            border-color: #f3c98b;
            color: #b54708;
            background: #fff7ed;
        }
        .nuwa-chip.bad {
            border-color: #f0a7a0;
            color: #b42318;
            background: #fff1f0;
        }
        .nuwa-section {
            margin-top: 1.2rem;
            margin-bottom: 0.45rem;
            color: var(--nuwa-muted);
            font-size: 0.9rem;
            font-weight: 700;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 女娲后台")
        st.text_input("服务地址", value=runtime_url(), key="runtime_url")
        st.text_input("管理密钥", value=admin_token(), type="password", key="admin_token")
        st.markdown("---")
        st.page_link("streamlit_app.py", label="总览")
        st.page_link("pages/1_对话调试.py", label="对话调试")
        st.page_link("pages/2_人格配置.py", label="人格配置")
        st.page_link("pages/3_质量评测.py", label="质量评测")
        st.page_link("pages/4_用户记忆.py", label="用户记忆")


def runtime_url() -> str:
    value = st.session_state.get("runtime_url") or DEFAULT_RUNTIME_URL
    return str(value).rstrip("/")


def admin_token() -> str:
    return st.session_state.get("admin_token") or os.getenv("NUWA_ADMIN_TOKEN", "")


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": admin_token()}


def require_admin_token() -> None:
    if not admin_token():
        st.warning("管理密钥未设置。请在左侧填入后继续。")
        st.stop()


def request_json(
    method: str,
    path: str,
    *,
    admin: bool = False,
    json: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float | None = 15,
) -> Any:
    headers = admin_headers() if admin else {}
    if json is not None:
        headers = {**headers, "Content-Type": "application/json"}
    resp = httpx.request(
        method,
        f"{runtime_url()}{path}",
        headers=headers,
        json=json,
        params=params,
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()


def persona_label(persona_id: str) -> str:
    return PERSONA_LABELS.get(persona_id, persona_id)


def model_label(model_id: str) -> str:
    return MODEL_LABELS.get(model_id, model_id)


def option_label(value: str) -> str:
    if value in PERSONA_LABELS:
        return f"{PERSONA_LABELS[value]} ({value})"
    if value in MODEL_LABELS:
        return f"{MODEL_LABELS[value]} ({value})"
    return value


def status_chip(label: str, tone: str = "ok") -> None:
    st.markdown(f'<span class="nuwa-chip {tone}">{label}</span>', unsafe_allow_html=True)


def section(label: str) -> None:
    st.markdown(f'<div class="nuwa-section">{label}</div>', unsafe_allow_html=True)


def compact_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"{exc.response.status_code}: {exc.response.text[:500]}"
    return str(exc)


def format_ms(value: Any) -> str:
    if value is None:
        return "-"
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    if n >= 1000:
        return f"{n / 1000:.1f}s"
    return f"{n}ms"
