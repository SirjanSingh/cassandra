# Shared image for the Patient and the Dashboard Cloud Run services.
# Build target is selected via the SERVICE env var (patient | dashboard).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

# Node is needed to run the @arizeai/phoenix-mcp server via npx (partner MCP).
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY cassandra ./cassandra
COPY patient ./patient
COPY dashboard ./dashboard
RUN pip install --upgrade pip && pip install .

ENV SERVICE=dashboard PORT=8080
# patient -> patient.agent:app ; dashboard -> dashboard.main:app
CMD ["sh", "-c", "uvicorn ${SERVICE}.$( [ \"$SERVICE\" = patient ] && echo agent || echo main ):app --host 0.0.0.0 --port ${PORT}"]
