# ARG for the Debian base image tag
ARG DEBIAN_IMAGE=debian:bookworm-20250929-slim
# ARG for the uv binary version
ARG UV_VERSION=0.8.22

# Stage for fetching the uv binary.
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- Stage 1: python-base ---
# Creates a reusable base image with a specific Python version installed.
FROM ${DEBIAN_IMAGE} AS python-base
# Install uv from the dedicated uv stage.
COPY --from=uv /uv /uvx /bin/
# Install the Python version specified in the .python-version file.
COPY .python-version ./ 
RUN uv python install


# --- Stage 2: builder ---
# Builds the application's virtual environment with all dependencies.
FROM python-base AS builder
# Change the working directory to the `app` directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy the project into the intermediate image
COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable


# --- Stage 3: final ---
# Creates the lean, final runtime image.
FROM python-base AS final

# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# Set the entrypoint to a script that activates the venv and runs the app.
ENTRYPOINT ["/app/.venv/bin/lybic-guiagent"]
