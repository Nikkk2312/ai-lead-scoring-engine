FROM python:3.11-slim

LABEL maintainer="AI Lead Scoring Engine"
LABEL description="Self-hosted AI-powered B2B lead scoring pipeline"

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory for persistent storage
RUN mkdir -p /app/data

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:5000/api/health || exit 1

ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=sqlite:///data/lead_scorer.db

# Default: run the dashboard
CMD ["python", "main.py", "dashboard"]
