"""Playground 页：跟老师对话，切 persona / model / 温度。

默认走 SSE 流式（/v1/chat/stream）— st.write_stream 喂打字机效果；可切回非流式。
"""

import json
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
st.caption("调试老师人格 / 切模型 / 看温度对回复风格的影响。默认流式（打字机）。")

runtime_url = st.session_state.get("runtime_url") or DEFAULT_RUNTIME_URL

with st.sidebar:
    st.header("本轮配置")
    persona = st.selectbox("Persona", PERSONAS, index=0)
    model = st.selectbox("Model", MODELS, index=0)
    temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
    user_id = st.text_input("user_id", value="admin-poc")
    use_stream = st.checkbox("流式输出（打字机）", value=True)
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


def _payload() -> dict:
    return {
        "persona_id": persona,
        "user_id": user_id,
        "messages": st.session_state.playground_messages,
        "model_override": model,
        "temperature": temperature,
    }


def _stream_call() -> tuple[str, dict]:
    """生成器拉 SSE，st.write_stream 喂的 generator。返回 (full_text, meta)。

    Streamlit 1.30+ 的 st.write_stream 接受 generator yield str 段；done 事件不喂给它，
    存到本闭包的 meta 字典里。
    """
    full_chunks: list[str] = []
    meta: dict = {}

    def gen():
        with httpx.stream(
            "POST",
            f"{runtime_url}/v1/chat/stream",
            json=_payload(),
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line[len("data: ") :])
                except json.JSONDecodeError:
                    continue
                if "error" in data:
                    meta["error"] = data["error"]
                    yield f"\n\n❌ {data['error']}"
                    return
                if data.get("done"):
                    meta.update(data)
                    return
                delta = data.get("delta")
                if delta:
                    full_chunks.append(delta)
                    yield delta

    # st.write_stream 渲染 generator，同时把 yield 内容收集到 full_chunks
    st.write_stream(gen())
    return "".join(full_chunks), meta


def _sync_call() -> tuple[str, dict]:
    resp = httpx.post(f"{runtime_url}/v1/chat", json=_payload(), timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return data.get("content", ""), {
        "trace_id": data.get("trace_id"),
        "model_id": data.get("model_id"),
        **data.get("usage", {}),
    }


if user_msg := st.chat_input("跟老师聊点什么……"):
    st.session_state.playground_messages.append({"role": "user", "content": user_msg})
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        content = ""
        meta: dict = {}
        try:
            if use_stream:
                content, meta = _stream_call()
            else:
                with st.spinner("思考中…"):
                    content, meta = _sync_call()
                st.markdown(content)
            if meta and "error" not in meta:
                bits = []
                if meta.get("trace_id"):
                    bits.append(f"trace_id={meta['trace_id']}")
                if meta.get("model_id"):
                    bits.append(f"model={meta['model_id']}")
                if meta.get("thinking_path"):
                    bits.append(f"thinking_path={meta['thinking_path']}")
                if meta.get("first_token_ms") is not None:
                    bits.append(f"first_token={meta['first_token_ms']}ms")
                if meta.get("total_ms") is not None:
                    bits.append(f"total={meta['total_ms']}ms")
                elif meta.get("latency_ms") is not None:
                    bits.append(f"latency={meta['latency_ms']}ms")
                if bits:
                    st.caption("  ".join(bits))
        except httpx.HTTPStatusError as e:
            content = f"❌ runtime {e.response.status_code}: {e.response.text}"
            st.error(content)
        except Exception as e:
            content = f"❌ 调用失败: {e}"
            st.error(content)
    st.session_state.playground_messages.append({"role": "assistant", "content": content})
