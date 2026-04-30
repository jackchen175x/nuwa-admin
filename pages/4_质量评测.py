from __future__ import annotations

import json
from collections.abc import Iterator

import httpx
import pandas as pd
import streamlit as st

from admin_ui import (
    DIMENSION_LABELS,
    admin_headers,
    card_grid,
    compact_error,
    format_ms,
    hero,
    lifecycle_flow,
    model_label,
    option_label,
    request_json,
    require_admin_token,
    runtime_url,
    section,
    setup_page,
)


setup_page("质量评测", "标准考卷、批量跑分、历史结果")
require_admin_token()

hero(
    "质量评测",
    "用标准题和维度评分把“像不像老师”变成可追踪结果，支撑每次人格文件改动后的回归验证。",
)
lifecycle_flow("评测")

card_grid(
    [
        ("单题", "快速验证", "改完人格文件后先跑单题，观察回复和追踪号。"),
        ("批量", "标准考卷", "全套题覆盖人格一致性、场景贴合、可执行性等维度。"),
        ("历史", "趋势回看", "比较不同时间、不同模型和不同老师的评测结果。"),
    ]
)

DIMENSIONS = tuple(DIMENSION_LABELS.keys())


def get_admin(path: str):
    return request_json("GET", path, admin=True)


def post_admin(path: str, body: dict):
    return request_json("POST", path, admin=True, json=body, timeout=120)


def stream_eval(payload: dict) -> Iterator[dict]:
    with httpx.stream(
        "POST",
        f"{runtime_url()}/admin/eval/run/stream",
        headers=admin_headers(),
        json=payload,
        timeout=None,
    ) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            try:
                yield json.loads(line[len("data: ") :])
            except json.JSONDecodeError:
                continue


def score_table(scores: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "维度": DIMENSION_LABELS[key],
                "分数": scores.get(key, "-"),
            }
            for key in DIMENSIONS
        ]
    )


def aggregate_table(aggregate: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "维度": DIMENSION_LABELS[key],
                "均分": round(aggregate.get(key, 0), 2),
            }
            for key in DIMENSIONS
        ]
    )


try:
    personas = get_admin("/admin/eval/personas")
except Exception as exc:
    st.error(f"加载评测老师失败：{compact_error(exc)}")
    st.stop()

tab_single, tab_batch, tab_history = st.tabs(["单题评测", "批量跑分", "历史结果"])

with tab_single:
    section("单题")
    form_cols = st.columns([1, 1, 1, 2])
    with form_cols[0]:
        persona = st.selectbox("老师", personas, index=0, format_func=option_label)
    with form_cols[1]:
        default_case = "cq-001" if persona == "changqing" else "zz-001"
        case_id = st.text_input("题目编号", value=default_case)
    with form_cols[2]:
        do_judge = st.toggle("自动评分", value=False)
    with form_cols[3]:
        model_override = st.text_input("模型覆盖", value="", placeholder="留空使用默认模型")

    if st.button("开始评测", type="primary"):
        body = {
            "persona": persona,
            "case_id": case_id.strip(),
            "model_override": model_override.strip() or None,
            "do_judge": do_judge,
        }
        try:
            with st.spinner("评测中"):
                resp = post_admin("/admin/eval/run", body)
        except Exception as exc:
            st.error(f"评测失败：{compact_error(exc)}")
            st.stop()

        rec = resp["record"]
        if rec.get("error"):
            st.error(rec["error"])
        else:
            meta_cols = st.columns(4)
            meta_cols[0].metric("追踪号", rec.get("trace_id", "-"))
            meta_cols[1].metric("模型", model_label(rec.get("model_id", "-")))
            meta_cols[2].metric("思维路径", rec.get("thinking_path", "-"))
            meta_cols[3].metric("耗时", format_ms(rec.get("latency_ms")))

            section("回复")
            st.write(rec.get("reply", ""))

            judge = rec.get("judge") or {}
            if judge:
                if "_judge_parse_error" in judge:
                    st.warning("评分结果解析失败。")
                    st.code(judge.get("_judge_raw", "")[:1200], language="text")
                else:
                    scores = judge.get("scores") or {}
                    if scores:
                        section("评分")
                        st.dataframe(score_table(scores), use_container_width=True, hide_index=True)
                    if judge.get("strengths"):
                        st.markdown(f"**优点**：{judge['strengths']}")
                    if judge.get("weaknesses"):
                        st.markdown(f"**问题**：{judge['weaknesses']}")
                    if judge.get("suggested_improvement"):
                        st.markdown(f"**建议**：{judge['suggested_improvement']}")

        st.caption(f"结果文件：`{resp['out_path']}`")

with tab_batch:
    section("批量")
    batch_cols = st.columns([1, 1, 2])
    with batch_cols[0]:
        batch_persona = st.selectbox("老师", personas, key="batch_persona", format_func=option_label)
    with batch_cols[1]:
        batch_judge = st.toggle("自动评分", value=False, key="batch_judge")
    with batch_cols[2]:
        batch_model = st.text_input("模型覆盖", value="", key="batch_model")

    if st.button("开始跑分", type="primary", key="batch_start"):
        payload = {
            "persona": batch_persona,
            "model_override": batch_model.strip() or None,
            "do_judge": batch_judge,
        }
        progress = st.progress(0.0, text="启动中")
        table_area = st.empty()
        result_area = st.empty()
        rows: list[dict] = []

        try:
            total = 0
            for event in stream_eval(payload):
                if event.get("event") == "started":
                    total = event.get("total", 0)
                    progress.progress(0.0, text=f"准备评测 {total} 题")
                elif event.get("event") == "case":
                    rec = event.get("record", {})
                    index = event.get("index", 0)
                    rows.append(
                        {
                            "题目": rec.get("case_id"),
                            "类别": rec.get("category"),
                            "耗时": format_ms(rec.get("latency_ms")),
                            "路径": rec.get("thinking_path"),
                            "回复字数": len(rec.get("reply", "")),
                            "错误": rec.get("error", ""),
                        }
                    )
                    progress.progress(
                        index / max(total, 1),
                        text=f"已完成 {index}/{total} · {rec.get('case_id')}",
                    )
                    table_area.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                elif event.get("event") == "done":
                    progress.progress(1.0, text="完成")
                    result_area.success(
                        f"完成 {event.get('ok')}/{event.get('total')}，结果：{event.get('out_path')}"
                    )
                    aggregate = event.get("aggregate") or {}
                    if any(aggregate.values()):
                        st.dataframe(
                            aggregate_table(aggregate),
                            use_container_width=True,
                            hide_index=True,
                        )
                elif event.get("event") == "error":
                    result_area.error(
                        f"跑分中断：{event.get('error')}，已完成 {event.get('completed', 0)} 题"
                    )
        except Exception as exc:
            st.error(f"跑分失败：{compact_error(exc)}")

with tab_history:
    section("历史")
    try:
        runs = get_admin("/admin/eval/runs")
    except Exception as exc:
        st.error(f"加载历史失败：{compact_error(exc)}")
        st.stop()

    if not runs:
        st.info("暂无历史结果。")
        st.stop()

    runs_df = pd.DataFrame(runs).rename(
        columns={
            "mtime": "时间",
            "persona": "老师",
            "model": "模型",
            "size_bytes": "大小",
            "filename": "文件",
        }
    )
    st.dataframe(runs_df[["时间", "老师", "模型", "大小", "文件"]], use_container_width=True, hide_index=True)

    selected = st.selectbox("结果文件", [item["filename"] for item in runs], index=0)

    try:
        detail = get_admin(f"/admin/eval/runs/{selected}")
    except Exception as exc:
        st.error(f"加载结果失败：{compact_error(exc)}")
        st.stop()

    metrics = st.columns(3)
    metrics[0].metric("总题数", detail["total"])
    metrics[1].metric("成功", detail["ok"])
    metrics[2].metric("失败", detail["total"] - detail["ok"])

    aggregate = detail.get("aggregate") or {}
    if any(aggregate.values()):
        st.dataframe(aggregate_table(aggregate), use_container_width=True, hide_index=True)

    section("逐题结果")
    for rec in detail["records"]:
        title = f"{rec.get('case_id')} · {rec.get('category', '?')} · {len(rec.get('reply', ''))} 字"
        with st.expander(title):
            if rec.get("error"):
                st.error(rec["error"])
                continue
            st.markdown(f"**用户**：{rec.get('user_msg', '')}")
            st.markdown("**回复**")
            st.write(rec.get("reply", ""))
            judge = rec.get("judge") or {}
            scores = judge.get("scores")
            if scores:
                st.dataframe(score_table(scores), use_container_width=True, hide_index=True)
