FROM python:3.11-slim

# Install git and other system dependencies if needed
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Install dependencies using uv
RUN pip install --no-cache-dir uv
RUN uv pip install --system -r requirements.txt

# Create directories for DB and local HTML saves
RUN mkdir -p data invoices && chmod 777 data invoices

EXPOSE 7860
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
