# ARG for the Debian base image tag
ARG DEBIAN_IMAGE=debian:bookworm-20250929-slim
# ARG for the uv binary version
ARG UV_VERSION=0.8.22

# Stage for fetching the uv binary.
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- Stage 1: python-base ---
# Creates a reusable base image with a specific Python version installed.
FROM ${DEBIAN_IMAGE} AS base
# Install uv from the dedicated uv stage.
COPY --from=uv /uv /uvx /bin/
# Install the Python version specified in the .python-version file.
COPY .python-version ./
RUN uv python install


# --- Stage 2: builder ---
# Builds the application's virtual environment with all dependencies.
FROM base AS builder

# Install build-essential for compiling dependencies like grpcio-tools
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Change the working directory to the `app` directory
WORKDIR /app

# Slow dependencies are built separately, allowing other steps to reuse these caches.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv && uv pip install "grpcio==1.75.1" "grpcio-tools==1.71.2" "asyncpg==0.30.0"

# Copy only proto files first for proto build
COPY gui_agents/proto /app/gui_agents/proto

# Build proto
RUN .venv/bin/python -m grpc_tools.protoc -Igui_agents/proto \
  --python_out=gui_agents/proto/pb  \
  --grpc_python_out=gui_agents/proto/pb \
  --pyi_out=gui_agents/proto/pb \
  gui_agents/proto/agent.proto && \
    sed -i 's/^import agent_pb2 as agent__pb2/from . import agent_pb2 as agent__pb2/' /app/gui_agents/proto/pb/agent_pb2_grpc.py

# Install dependencies including grpc extras needed for protoc
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable --extra grpc --extra postgres --extra prometheus --extra mcp --extra restful

# Copy the project into the intermediate image
COPY . /app

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


# --- Stage 3: final ---
# Creates the lean, final runtime image.
FROM base AS final

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Expose the gRPC port ,RESTful API and mcp port
EXPOSE 50051
EXPOSE 8080
EXPOSE 8000

# Set the CMD to run the CLI app by default. This can be overridden to run the gRPC, Mcp or RESTful server.
CMD ["/app/.venv/bin/lybic-guiagent"]
