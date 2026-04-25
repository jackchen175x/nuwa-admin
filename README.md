# nuwa-admin (Phase 0 — Streamlit PoC)

Week 1 临时管理面板：选 persona、切模型、调温度、跟老师对话。

Week 2 起切 Next.js 14 + shadcn/ui，Streamlit 作为兜底。

## 启动

```bash
# 先启动 nuwa-runtime（默认 http://localhost:8000）
# 然后：
uv sync
uv run streamlit run streamlit_app.py
```

可通过环境变量 `NUWA_RUNTIME_URL` 覆盖默认 runtime 地址。
