# syntax=docker/dockerfile:1
# One container: NestJS API + built Vue UI + Python runner (+ Hermes Agent). Data in a volume.
# Agents run as a per-trial unprivileged user (runner/evalrunner/isolation.py); answer keys are root-only.

FROM node:22-bookworm-slim AS web
RUN npm install -g npm@11.6.2   # lock files are npm 11 format (FIX-23)
WORKDIR /src/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM node:22-bookworm-slim AS api
# better-sqlite3 compiles its native module when no prebuilt binary matches; tools stay in this build stage only
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/* \
 && npm install -g npm@11.6.2
WORKDIR /src/apps/api
COPY apps/api/package.json apps/api/package-lock.json ./
RUN npm ci
COPY apps/api/ ./
RUN npm run build && npm prune --omit=dev

FROM node:22-bookworm-slim
ARG INSTALL_HERMES=1
ARG CODE_SHA=unknown
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git util-linux procps \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy UV_CACHE_DIR=/tmp/uv-cache
COPY runner/pyproject.toml runner/uv.lock runner/.python-version runner/
RUN cd runner && uv sync --frozen --no-install-project
COPY runner/ runner/
RUN cd runner && uv sync --frozen && rm -rf /tmp/uv-cache

COPY tasks/ tasks/
COPY configs/ configs/
COPY skills/ skills/
COPY judge_validation/ judge_validation/
COPY --from=api /src/apps/api/package.json apps/api/package.json
COPY --from=api /src/apps/api/node_modules apps/api/node_modules
COPY --from=api /src/apps/api/dist apps/api/dist
COPY --from=web /src/apps/web/dist apps/web/dist

# Hermes Agent (required harness). Installed under /opt/hermes so agents can read it; skip with INSTALL_HERMES=0.
RUN if [ "$INSTALL_HERMES" = "1" ]; then \
      curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash -s -- --non-interactive --hermes-home /opt/hermes ; \
    fi

# Answer keys and labels: root only. Agents get only their own trial folder (mode 700, own user ID).
RUN chmod -R go-rwx /app/tasks /app/judge_validation \
 && mkdir -p /app/data /opt/evalcache && chmod 755 /opt/evalcache

ENV REPO_ROOT=/app DB_PATH=/app/data/evals.db PORT=3000 \
    RUNNER_PYTHON=/app/runner/.venv/bin/python \
    HERMES_BIN=/opt/hermes/hermes-agent/.hermes/bin/hermes \
    EVAL_TOOL_CACHE=/opt/evalcache CODE_SHA=${CODE_SHA}
VOLUME /app/data
EXPOSE 3000
CMD ["node", "apps/api/dist/main.js"]
