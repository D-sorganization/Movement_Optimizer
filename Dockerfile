FROM python:3.12-slim

LABEL maintainer="D-sorganization"
LABEL description="Movement Optimizer - CLI mode for headless batch optimization"

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

# Default entrypoint for CLI mode
ENTRYPOINT ["python3", "-m", "movement_optimizer.cli"]
CMD ["--help"]
