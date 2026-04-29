from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import streamlit as st

from admin_ui import (
    FALLBACK_MODELS,
    FALLBACK_PERSONAS,
    compact_error,
    format_ms,
    model_label,
    option_label,
    persona_label,
    request_json,
    runtime_url,
    section,
    setup_page,
)


setup_page("对话调试", "验证老师人格、模型参数和接口延迟")


def load_personas() -> list[str]:
    try:
        items = request_json("GET", "/admin/personas", admin=True)
        return [item["id"] for item in items]
    except Exception:
        return FALLBACK_PERSONAS


personas = load_personas()

with st.sidebar:
    st.markdown("### 本轮参数")
    persona = st.selectbox("老师", personas, index=0, format_func=option_label)
    model_options = ["默认模型", *FALLBACK_MODELS]
    model_choice = st.selectbox("模型", model_options, index=0, format_func=option_label)
    temperature = st.slider("回复温度", 0.0, 2.0, 0.7, 0.1)
    user_id = st.text_input("测试用户 ID", value="admin-test")
    skill_label = st.text_input("提示词标签", value="", placeholder="留空使用生产版本")
    use_stream = st.toggle("流式输出", value=True)
    if st.button("清空对话", use_container_width=True):
        st.session_state.pop("playground_messages", None)
        st.rerun()

if "playground_messages" not in st.session_state:
    st.session_state.playground_messages = []

meta_cols = st.columns(4)
meta_cols[0].metric("老师", persona_label(persona))
meta_cols[1].metric("模型", model_label(model_choice) if model_choice != "默认模型" else "默认")
meta_cols[2].metric("温度", temperature)
meta_cols[3].metric("输出", "流式" if use_stream else "同步")

section("对话")
for msg in st.session_state.playground_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


def payload() -> dict:
    body = {
        "persona_id": persona,
        "user_id": user_id,
        "messages": st.session_state.playground_messages,
        "temperature": temperature,
    }
    if model_choice != "默认模型":
        body["model_override"] = model_choice
    if skill_label.strip():
        body["skill_label"] = skill_label.strip()
    return body


def parse_sse() -> Iterator[dict]:
    with httpx.stream(
        "POST",
        f"{runtime_url()}/v1/chat/stream",
        json=payload(),
        timeout=120,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            try:
                yield json.loads(line[len("data: ") :])
            except json.JSONDecodeError:
                continue


def stream_call() -> tuple[str, dict]:
    chunks: list[str] = []
    meta: dict = {}

    def gen() -> Iterator[str]:
        for item in parse_sse():
            if "error" in item:
                meta["error"] = item["error"]
                yield f"\n\n调用失败：{item['error']}"
                return
            if item.get("done"):
                meta.update(item)
                return
            delta = item.get("delta")
            if delta:
                chunks.append(delta)
                yield delta

    st.write_stream(gen())
    return "".join(chunks), meta


def sync_call() -> tuple[str, dict]:
    data = request_json("POST", "/v1/chat", json=payload(), timeout=120)
    return data.get("content", ""), {
        "trace_id": data.get("trace_id"),
        "model_id": data.get("model_id"),
        **data.get("usage", {}),
    }


def render_meta(meta: dict) -> None:
    if not meta or meta.get("error"):
        return
    items = []
    if meta.get("trace_id"):
        items.append(f"追踪号: `{meta['trace_id']}`")
    if meta.get("model_id"):
        items.append(f"模型: {model_label(meta['model_id'])}")
    if meta.get("thinking_path"):
        items.append(f"路径: {meta['thinking_path']}")
    if meta.get("first_token_ms") is not None:
        items.append(f"首字: {format_ms(meta['first_token_ms'])}")
    if meta.get("total_ms") is not None:
        items.append(f"总耗时: {format_ms(meta['total_ms'])}")
    elif meta.get("latency_ms") is not None:
        items.append(f"耗时: {format_ms(meta['latency_ms'])}")
    if items:
        st.caption("  ·  ".join(items))


if user_msg := st.chat_input("输入要测试的问题"):
    st.session_state.playground_messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        content = ""
        meta: dict = {}
        try:
            if use_stream:
                content, meta = stream_call()
            else:
                with st.spinner("生成中"):
                    content, meta = sync_call()
                st.markdown(content)
            render_meta(meta)
        except Exception as exc:
            content = f"调用失败：{compact_error(exc)}"
            st.error(content)

    st.session_state.playground_messages.append({"role": "assistant", "content": content})
