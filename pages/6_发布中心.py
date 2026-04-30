from __future__ import annotations

import pandas as pd
import streamlit as st

from admin_ui import API_BASE_URL, ADMIN_URL, hero, lifecycle_flow, request_json, section, setup_page


setup_page("发布中心", "接口、灰度、回滚和研发交接")

hero(
    "发布中心",
    "把研发接入、灰度变量、验收标准和回滚动作集中放在一处，避免上线时到处翻文档。",
)
lifecycle_flow("发布")

section("生产地址")
st.dataframe(
    pd.DataFrame(
        [
            {"用途": "健康检查", "方法": "GET", "地址": f"{API_BASE_URL}/healthz"},
            {"用途": "就绪检查", "方法": "GET", "地址": f"{API_BASE_URL}/readyz"},
            {"用途": "同步对话", "方法": "POST", "地址": f"{API_BASE_URL}/v1/chat"},
            {"用途": "流式对话", "方法": "POST", "地址": f"{API_BASE_URL}/v1/chat/stream"},
            {"用途": "管理后台", "方法": "GET", "地址": ADMIN_URL},
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

section("接口示例")
st.code(
    """curl -sS https://api.nuwa.aizd.org/v1/chat \\
  -H 'Content-Type: application/json' \\
  -d '{
    "persona_id": "changqing",
    "user_id": "wx-openid-or-internal-user-id",
    "messages": [
      {"role": "user", "content": "我最近很焦虑"}
    ]
  }'""",
    language="bash",
)

section("长卿小程序灰度变量")
st.dataframe(
    pd.DataFrame(
        [
            {"变量": "AI_ROUTE_MODE", "推荐值": "ab", "说明": "dify / nuwa / ab"},
            {"变量": "NUWA_AB_PERCENT", "推荐值": "10", "说明": "10% 命中 Nuwa"},
            {"变量": "NUWA_API_URL", "推荐值": f"{API_BASE_URL}/v1/chat", "说明": "同步接口"},
            {"变量": "NUWA_TIMEOUT_MS", "推荐值": "55000", "说明": "云函数 60s 内部超时"},
            {"变量": "NUWA_PERSONA_COMPANION", "推荐值": "changqing", "说明": "陪伴入口"},
            {"变量": "NUWA_PERSONA_CONSULT", "推荐值": "changqing", "说明": "咨询入口"},
            {"变量": "NUWA_PERSONA_TUTOR", "推荐值": "changqing", "说明": "辅导入口"},
        ]
    ),
    use_container_width=True,
    hide_index=True,
)

section("验收清单")
checks = [
    "healthz 返回 200",
    "readyz 返回 ready=true",
    "POST /v1/chat 能返回 content 和 trace_id",
    "小程序默认 Dify 路径正常",
    "内部 nuwa 模式纯文本能返回 aiProvider=nuwa",
    "Nuwa 失败能自动回退 Dify",
    "AB 模式下 messages.aiProvider 出现少量 nuwa",
    "观测中心能看到 trace_id、延迟和错误",
]
for item in checks:
    st.checkbox(item, value=False, key=f"release-check::{item}")

section("回滚")
st.code(
    """AI_ROUTE_MODE=dify
NUWA_AB_PERCENT=0""",
    language="bash",
)

st.warning("任一条件命中先回 Dify：错误率 > 5%、p95 超过 60s、用户集中反馈不像/空白/很慢、readyz 非 ready。")

section("研发交接")
st.link_button(
    "打开研发对接文档",
    "https://github.com/jackchen175x/nuwa-runtime/blob/main/docs/DEVELOPER_HANDOFF.md",
)

try:
    ready = request_json("GET", "/readyz", timeout=8)
    if ready.get("ready"):
        st.success("当前生产 Runtime 已就绪。")
    else:
        st.warning("当前生产 Runtime 未完全就绪。")
except Exception as exc:
    st.error(f"readyz 检查失败：{exc}")
