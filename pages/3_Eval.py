"""Eval 页：在线跑标准考卷（单题同步 / 全套 SSE 流式）+ 看历史 run。

模式：
- 单题：POST /admin/eval/run，~30s 同步等结果
- 批量：POST /admin/eval/run/stream，SSE 长连接，进度条逐题更新（适合 12 题 × 30s）

历史：列 eval/results/ 下所有 jsonl，切到详情看 5 维度均分 + 逐题 expander。
"""

import json
import os
from collections.abc import Iterator

import httpx
import pandas as pd
import streamlit as st

DEFAULT_RUNTIME_URL = os.getenv("NUWA_RUNTIME_URL", "http://localhost:8000")

DIMENSIONS = (
    "persona_consistency",
    "scenario_fit",
    "actionability",
    "information_density",
    "overall_recommendation",
)

st.set_page_config(page_title="女娲 Eval", page_icon="📝", layout="wide")
st.title("📝 标准考卷")
st.caption("跑单题：浏览器同步等结果（约 30 秒）。批量跑请用 `scripts/eval_skill.py` CLI。")

runtime_url = st.session_state.get("runtime_url") or DEFAULT_RUNTIME_URL
admin_token = st.session_state.get("admin_token") or os.getenv("NUWA_ADMIN_TOKEN", "")

if not admin_token:
    st.warning("⚠ Admin Token 未设置。在主页 sidebar 填入，或 export NUWA_ADMIN_TOKEN=...")
    st.stop()


def _headers() -> dict:
    return {"X-Admin-Token": admin_token}


def _get(path: str) -> dict | list:
    resp = httpx.get(f"{runtime_url}{path}", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, body: dict) -> dict:
    resp = httpx.post(f"{runtime_url}{path}", headers=_headers(), json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _stream_eval(payload: dict) -> Iterator[dict]:
    """打开 SSE 跑批连接，yield 每个 event dict（started / case / done / error）。"""
    with httpx.stream(
        "POST",
        f"{runtime_url}/admin/eval/run/stream",
        headers={**_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=None,  # SSE 长连接，不要客户端 idle 超时
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            try:
                yield json.loads(line[len("data: ") :])
            except json.JSONDecodeError:
                continue


tab_run, tab_batch, tab_history = st.tabs(["▶️ 跑单题", "🚀 批量跑全套", "📚 历史"])


with tab_run:
    try:
        personas = _get("/admin/eval/personas")
    except httpx.HTTPError as e:
        st.error(f"加载 persona 列表失败：{e}")
        st.stop()

    col_a, col_b = st.columns([1, 2])
    with col_a:
        persona = st.selectbox("Persona", personas, index=0)
        model_override = st.text_input("Model override", value="", help="留空走 personas.yaml 默认")
        do_judge = st.checkbox(
            "调 Claude judge 打分",
            value=False,
            help="需要 ANTHROPIC_API_KEY 配在 runtime；多花一次 Claude Opus 调用",
        )
    with col_b:
        # 拉这个 persona 的所有题目作为 case 选项
        # （admin API 没暴露题库本身，先用 ID 列表硬编码 fallback；后续 admin 加 list_cases 再填）
        case_id = st.text_input(
            "Case ID（必填，例如 cq-001 / zz-003）",
            value="cq-001" if persona == "changqing" else "zz-001",
        )

    if st.button("▶️ 跑这一题", type="primary"):
        with st.spinner(f"调 runtime + persona={persona} case={case_id}…"):
            try:
                resp = _post(
                    "/admin/eval/run",
                    {
                        "persona": persona,
                        "case_id": case_id.strip(),
                        "model_override": model_override.strip() or None,
                        "do_judge": do_judge,
                    },
                )
            except httpx.HTTPStatusError as e:
                st.error(f"runtime {e.response.status_code}: {e.response.text}")
                st.stop()
            except httpx.HTTPError as e:
                st.error(f"runtime 调用失败：{e}")
                st.stop()

        rec = resp["record"]
        if "error" in rec:
            st.error(f"❌ {rec['error']}")
        else:
            meta = []
            if rec.get("trace_id"):
                meta.append(f"trace={rec['trace_id']}")
            if rec.get("model_id"):
                meta.append(f"model={rec['model_id']}")
            if rec.get("thinking_path"):
                meta.append(f"thinking={rec['thinking_path']}")
            if rec.get("latency_ms") is not None:
                meta.append(f"latency={rec['latency_ms']}ms")
            st.caption("  ".join(meta))

            st.subheader("回复")
            st.write(rec["reply"])

            judge = rec.get("judge")
            if judge:
                if "_judge_parse_error" in judge:
                    st.warning("Judge 返回了非 JSON。原文：")
                    st.code(judge.get("_judge_raw", "")[:1000])
                else:
                    scores = judge.get("scores", {})
                    if scores:
                        st.subheader("Judge 评分")
                        score_df = pd.DataFrame(
                            [(k, scores.get(k, "-")) for k in DIMENSIONS],
                            columns=["维度", "分数"],
                        )
                        st.dataframe(score_df, use_container_width=True, hide_index=True)
                    if judge.get("strengths"):
                        st.markdown(f"**亮点**：{judge['strengths']}")
                    if judge.get("weaknesses"):
                        st.markdown(f"**待改**：{judge['weaknesses']}")
                    if judge.get("suggested_improvement"):
                        st.markdown(f"**改写建议**：{judge['suggested_improvement']}")

        st.caption(f"已落盘：`{resp['out_path']}`")


with tab_batch:
    st.caption("跑当前 persona 的全套题（12 题 × ~30 秒 ≈ 6 分钟，SSE 长连接）。")
    try:
        batch_personas = _get("/admin/eval/personas")
    except httpx.HTTPError as e:
        st.error(f"加载 persona 列表失败：{e}")
        batch_personas = []

    if batch_personas:
        b_persona = st.selectbox("Persona", batch_personas, key="batch_persona")
        b_model = st.text_input("Model override", value="", key="batch_model")
        b_judge = st.checkbox("调 Claude judge 打分", value=False, key="batch_judge")

        if st.button("🚀 开始跑批", type="primary", key="batch_start"):
            payload = {
                "persona": b_persona,
                "model_override": b_model.strip() or None,
                "do_judge": b_judge,
            }
            progress = st.progress(0.0, text="启动跑批…")
            log_area = st.empty()
            done_area = st.empty()
            rows: list[dict] = []

            try:
                total = 0
                for ev in _stream_eval(payload):
                    if ev.get("event") == "started":
                        total = ev.get("total", 0)
                        progress.progress(0.0, text=f"准备跑 {total} 题")
                    elif ev.get("event") == "case":
                        idx = ev.get("index", 0)
                        rec = ev.get("record", {})
                        rows.append(
                            {
                                "case_id": rec.get("case_id"),
                                "category": rec.get("category"),
                                "latency_ms": rec.get("latency_ms"),
                                "thinking": rec.get("thinking_path"),
                                "reply_chars": len(rec.get("reply", "")),
                                "error": rec.get("error", ""),
                            }
                        )
                        progress.progress(
                            idx / max(total, 1),
                            text=f"已完成 {idx}/{total} · 最新: {rec.get('case_id')}",
                        )
                        log_area.dataframe(
                            pd.DataFrame(rows), use_container_width=True, hide_index=True
                        )
                    elif ev.get("event") == "done":
                        progress.progress(1.0, text="✅ 跑批完成")
                        done_area.success(
                            f"完成 {ev.get('ok')}/{ev.get('total')} → {ev.get('out_path')}"
                        )
                        agg = ev.get("aggregate") or {}
                        if any(agg.values()):
                            st.subheader("各维度均分")
                            agg_df = pd.DataFrame(
                                [(k, round(agg.get(k, 0), 2)) for k in DIMENSIONS],
                                columns=["维度", "均分"],
                            )
                            st.dataframe(agg_df, use_container_width=True, hide_index=True)
                    elif ev.get("event") == "error":
                        done_area.error(
                            f"跑批中断：{ev.get('error')}（已完成 {ev.get('completed', 0)} 题）"
                        )
            except httpx.HTTPStatusError as e:
                st.error(f"runtime {e.response.status_code}: {e.response.text}")
            except httpx.HTTPError as e:
                st.error(f"runtime 调用失败：{e}")


with tab_history:
    try:
        runs = _get("/admin/eval/runs")
    except httpx.HTTPError as e:
        st.error(f"加载历史失败：{e}")
        st.stop()

    if not runs:
        st.info("还没有历史 run。先跑一题或用 `scripts/eval_skill.py` 跑批。")
        st.stop()

    runs_df = pd.DataFrame(runs)[["mtime", "persona", "model", "size_bytes", "filename"]]
    st.dataframe(runs_df, use_container_width=True, hide_index=True)

    selected = st.selectbox(
        "选一份 run 看详情",
        [r["filename"] for r in runs],
        index=0,
        format_func=lambda f: f"{f}",
    )

    try:
        detail = _get(f"/admin/eval/runs/{selected}")
    except httpx.HTTPError as e:
        st.error(f"加载 {selected} 失败：{e}")
        st.stop()

    cols = st.columns(3)
    cols[0].metric("总题数", detail["total"])
    cols[1].metric("成功", detail["ok"])
    cols[2].metric("失败", detail["total"] - detail["ok"])

    agg = detail.get("aggregate") or {}
    if any(agg.values()):
        st.subheader("各维度均分")
        agg_df = pd.DataFrame(
            [(k, round(agg.get(k, 0), 2)) for k in DIMENSIONS],
            columns=["维度", "均分"],
        )
        st.dataframe(agg_df, use_container_width=True, hide_index=True)
    else:
        st.info("这份 run 没有 judge 评分（CLI 跑时没配 ANTHROPIC_API_KEY 或显式 --no-judge）")

    st.subheader("逐题")
    for r in detail["records"]:
        with st.expander(
            f"{r.get('case_id')} · {r.get('category', '?')} · {len(r.get('reply', ''))} 字"
        ):
            if "error" in r:
                st.error(f"❌ {r['error']}")
                continue
            st.markdown(f"**用户**：{r.get('user_msg', '')}")
            st.markdown("**回复**：")
            st.write(r.get("reply", ""))
            judge = r.get("judge") or {}
            scores = judge.get("scores")
            if scores:
                st.caption("  ".join(f"{k}={scores.get(k, '-')}" for k in DIMENSIONS))
