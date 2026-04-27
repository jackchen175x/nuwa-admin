"""Playground 页：跟老师对话，切 persona / model / 温度。"""

import os

import httpx
import streamlit as st

DEFAULT_RUNTIME_URL = os.getenv("NUWA_RUNTIME_URL", "http://localhost:8000")

PERSONAS = ["changqing", "zhouzi"]
MODELS = [
    "doubao-seed-2-0-pro-260215",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
]

st.set_page_config(page_title="女娲 Playground", page_icon="💬", layout="wide")
st.title("💬 Playground")
st.caption("调试老师人格 / 切模型 / 看温度对回复风格的影响。")

runtime_url = st.session_state.get("runtime_url") or DEFAULT_RUNTIME_URL

with st.sidebar:
    st.header("本轮配置")
    persona = st.selectbox("Persona", PERSONAS, index=0)
    model = st.selectbox("Model", MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
    user_id = st.text_input("user_id", value="admin-poc")
    if st.button("清空对话"):
        st.session_state.pop("playground_messages", None)
        st.rerun()
    st.caption(f"Runtime: {runtime_url}")

st.subheader(f"persona={persona} · model={model} · T={temperature}")

if "playground_messages" not in st.session_state:
    st.session_state.playground_messages = []

for msg in st.session_state.playground_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_msg := st.chat_input("跟老师聊点什么……"):
    st.session_state.playground_messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    payload = {
        "persona_id": persona,
        "user_id": user_id,
        "messages": st.session_state.playground_messages,
        "model_override": model,
        "temperature": temperature,
    }
    with st.chat_message("assistant"):
        with st.spinner("思考中…"):
            try:
                resp = httpx.post(f"{runtime_url}/v1/chat", json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                content = data["content"]
                st.markdown(content)
                latency = data.get("usage", {}).get("latency_ms", "?")
                thinking = data.get("usage", {}).get("thinking_path", "?")
                st.caption(
                    f"trace_id={data.get('trace_id')}  model={data.get('model_id')}  "
                    f"thinking_path={thinking}  latency={latency}ms"
                )
            except httpx.HTTPStatusError as e:
                content = f"❌ runtime {e.response.status_code}: {e.response.text}"
                st.error(content)
            except Exception as e:
                content = f"❌ 调用失败: {e}"
                st.error(content)
    st.session_state.playground_messages.append({"role": "assistant", "content": content})
