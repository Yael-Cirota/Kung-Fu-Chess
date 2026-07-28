# Server_Design.md §12.1: one image for every server-side role (server,
# and later server.roles.gateway/room/matchmaker/allocator/settlement).
# Role is chosen entirely by `command:` in docker-compose.yml, never by a
# separate image - see §12.1 "Two hand-written Dockerfiles" for why.

FROM python:3.12-slim AS builder
WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# There's no [build-system] table in pyproject.toml (the project isn't
# packaged as a wheel - see CLAUDE.md's `pip install -e .` dev flow), so
# this installs the server-side runtime deps directly rather than resolving
# them from pyproject.toml. Keep in sync with [project.dependencies]
# there - opencv/numpy are deliberately excluded (§12.2 item 3): they only
# serve ui/, which never ships in a server image.
RUN pip install --no-cache-dir "websockets>=12.0" "redis>=4.2"


FROM python:3.12-slim AS runtime
WORKDIR /app

RUN groupadd --system kfchess && useradd --system --gid kfchess --home-dir /app kfchess

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    KFC_HOST=0.0.0.0 \
    KFC_LOGGING_SERVER_FILE=""

# Only the packages the server stack imports (§12.3: ui/ and client/ are
# never imported by server/, and this makes it physically true in the
# image too, not just unimported).
COPY kfchess ./kfchess
COPY common ./common
COPY protocol ./protocol
COPY server ./server
COPY config ./config

EXPOSE 8765

# kfchess.db (dev-only, §12.3) and server.log land under /app at runtime -
# give the non-root user somewhere to write them.
RUN chown -R kfchess:kfchess /app

# Deliberately trivial (§12.4): a TCP connect proves process liveness and
# nothing more. Placement-eligibility readiness (/readyz) is a Kubernetes
# probe concern, not something HEALTHCHECK can express - see §12.4.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import os,socket; socket.create_connection(('127.0.0.1', int(os.environ.get('KFC_PORT', 8765))), timeout=2).close()" || exit 1

USER kfchess

CMD ["python", "-m", "server.main"]
