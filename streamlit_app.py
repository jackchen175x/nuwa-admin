import os

import httpx
import streamlit as st

RUNTIME_URL = os.getenv("NUWA_RUNTIME_URL", "http://localhost:8000")

PERSONAS = ["changqing", "zhouzi"]
MODELS = [
    "doubao-seed-2-0-pro-260215",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
]

st.set_page_config(page_title="女娲 Admin (PoC)", page_icon="🪡")

with st.sidebar:
    st.header("配置")
    persona = st.selectbox("Persona", PERSONAS, index=0)
    model = st.selectbox("Model", MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
    user_id = st.text_input("user_id", value="admin-poc")
    if st.button("清空对话"):
        st.session_state.pop("messages", None)
        st.rerun()
    st.caption(f"Runtime: {RUNTIME_URL}")

st.title("🪡 女娲底座 · Playground")
st.caption(f"persona={persona}  model={model}  T={temperature}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_msg := st.chat_input("跟老师聊点什么……"):
    st.session_state.messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    payload = {
        "persona_id": persona,
        "user_id": user_id,
        "messages": st.session_state.messages,
        "model_override": model,
        "temperature": temperature,
    }
    with st.chat_message("assistant"):
        with st.spinner("思考中…"):
            try:
                resp = httpx.post(f"{RUNTIME_URL}/v1/chat", json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
                content = data["content"]
                st.markdown(content)
                st.caption(f"trace_id={data.get('trace_id')}  model={data.get('model_id')}")
            except httpx.HTTPStatusError as e:
                content = f"❌ runtime {e.response.status_code}: {e.response.text}"
                st.error(content)
            except Exception as e:
                content = f"❌ 调用失败: {e}"
                st.error(content)
    st.session_state.messages.append({"role": "assistant", "content": content})
