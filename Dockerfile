FROM python:3.12-slim

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install dependencies first (cached unless pyproject.toml / uv.lock change)
COPY pyproject.toml uv.lock* .python-version ./
RUN uv sync --no-dev --no-install-project

COPY . .

# Run as a non-root user
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import os,urllib.request as u; u.urlopen('http://localhost:%s/_stcore/health' % os.environ.get('PORT','8501'))"

# GROQ_API_KEY must be supplied as an environment variable by the host (never baked into the image)
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
