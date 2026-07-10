FROM python:3.11-slim

# Install system dependencies (supervisor, etc)
RUN apt-get update && apt-get install -y supervisor curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Create log directories for supervisor
RUN mkdir -p /var/log/supervisor

# Set working directory
WORKDIR /app

# Copy the full project
COPY . /app

# Sync dependencies
RUN uv sync

# Expose port 7860
EXPOSE 7860

# Entrypoint is supervisord
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
