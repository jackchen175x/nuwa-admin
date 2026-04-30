from __future__ import annotations

import pandas as pd
import streamlit as st

from admin_ui import (
    compact_error,
    format_ms,
    hero,
    lifecycle_flow,
    persona_label,
    request_json,
    require_admin_token,
    section,
    setup_page,
)


setup_page("观测中心", "线上调用、延迟、错误和追踪信息")
require_admin_token()

hero(
    "运行观测",
    "面向灰度上线后的日常巡检：调用量、成功率、延迟、错误分布和最近请求集中在一个页面。",
)
lifecycle_flow("观测")

range_cols = st.columns([1, 1, 3])
with range_cols[0]:
    since_hours = st.selectbox("时间范围", [1, 6, 24, 72, 168, 720], index=2, format_func=lambda h: f"{h} 小时")
with range_cols[1]:
    recent_limit = st.selectbox("最近请求", [30, 80, 150, 300], index=1)

try:
    summary = request_json(
        "GET",
        "/admin/observability/chat-summary",
        admin=True,
        params={"since_hours": since_hours, "recent_limit": recent_limit},
        timeout=20,
    )
except Exception as exc:
    st.error(f"加载观测数据失败：{compact_error(exc)}")
    st.stop()

top = st.columns(5)
top[0].metric("调用量", summary["total"])
top[1].metric("成功率", f"{summary['ok_rate'] * 100:.1f}%")
top[2].metric("错误数", summary["errors"])
top[3].metric("p50 延迟", format_ms((summary["latency"] or {}).get("p50_ms")))
top[4].metric("p95 延迟", format_ms((summary["latency"] or {}).get("p95_ms")))

col_left, col_right = st.columns([1.15, 0.85])

with col_left:
    section("小时趋势")
    hourly = summary.get("by_hour") or []
    if hourly:
        hourly_df = pd.DataFrame(hourly)
        st.bar_chart(hourly_df.set_index("hour")[["ok", "errors"]])
        st.dataframe(hourly_df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无趋势数据。")

with col_right:
    section("状态分布")
    by_status = summary.get("by_status") or []
    if by_status:
        st.dataframe(pd.DataFrame(by_status), use_container_width=True, hide_index=True)
    else:
        st.info("暂无状态数据。")

    section("首字延迟")
    first_token = summary.get("first_token") or {}
    ft_cols = st.columns(3)
    ft_cols[0].metric("流式数", first_token.get("streamed_count", 0))
    ft_cols[1].metric("FTT p50", format_ms(first_token.get("p50_ms")))
    ft_cols[2].metric("FTT p95", format_ms(first_token.get("p95_ms")))

section("按老师")
by_persona = summary.get("by_persona") or []
if by_persona:
    rows = [
        {
            "老师": persona_label(row.get("persona_id", "")),
            "调用": row.get("calls"),
            "成功": row.get("ok"),
            "错误": row.get("errors"),
            "成功率": f"{row.get('ok_rate', 0) * 100:.1f}%",
            "p50": format_ms(row.get("p50_ms")),
            "p95": format_ms(row.get("p95_ms")),
        }
        for row in by_persona
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.caption("暂无老师维度数据。")

section("最近错误")
recent_errors = summary.get("recent_errors") or []
if recent_errors:
    error_rows = [
        {
            "时间": ev.get("ts", "")[:19],
            "老师": persona_label(ev.get("persona_id", "")),
            "状态": ev.get("status"),
            "耗时": format_ms(ev.get("latency_ms")),
            "追踪号": ev.get("trace_id"),
            "错误": ev.get("error", ""),
        }
        for ev in reversed(recent_errors[-30:])
    ]
    st.dataframe(pd.DataFrame(error_rows), use_container_width=True, hide_index=True)
else:
    st.success("当前范围内没有错误。")

section("最近请求")
recent_events = summary.get("recent_events") or []
if recent_events:
    rows = [
        {
            "时间": ev.get("ts", "")[:19],
            "老师": persona_label(ev.get("persona_id", "")),
            "用户": ev.get("user_id"),
            "状态": ev.get("status"),
            "耗时": format_ms(ev.get("latency_ms")),
            "输入字数": ev.get("input_chars"),
            "输出字数": ev.get("output_chars"),
            "追踪号": ev.get("trace_id"),
        }
        for ev in reversed(recent_events)
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("暂无请求记录。")

st.caption(f"日志文件：`{summary.get('log_path', '-')}`")
