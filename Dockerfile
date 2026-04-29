# nuwa-admin production image
# Build: docker build -t nuwa-admin:latest .

# syntax=docker/dockerfile:1.7-labs

FROM ghcr.io/astral-sh/uv:0.9-python3.11-bookworm-slim AS deps
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project


FROM ghcr.io/astral-sh/uv:0.9-python3.11-bookworm-slim AS final
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app

COPY --from=deps /app/.venv /app/.venv
COPY pyproject.toml uv.lock README.md streamlit_app.py admin_ui.py ./
COPY .streamlit .streamlit
COPY pages pages

# 项目本体（即 streamlit_app + pages，pyproject 标了 package=false 所以 sync 只校验依赖）
RUN uv sync --frozen

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3).read()==b'ok' else 1)" \
    || exit 1

# headless + 关掉 telemetry + 严禁 cors（生产由 Caddy 反代）
CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false", \
     "--server.fileWatcherType=none"]
