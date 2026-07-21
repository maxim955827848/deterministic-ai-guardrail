# Minimal, reproducible image for running the guardrail test-suite and demo.
FROM python:3.11-slim

# Don't buffer stdout/stderr; don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first so the layer caches across source edits.
COPY pyproject.toml requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the source and install the package itself (editable is fine for a PoC).
COPY src ./src
COPY tests ./tests
COPY examples ./examples
RUN pip install -e .

# Default: run the tests. Override the command to run the demo, e.g.
#   docker run --rm deterministic-ai-guardrail python examples/demo.py
CMD ["pytest"]
