FROM python:3.13-slim

# Layer 1: System dependencies (rarely changes)
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Layer 2: Create user (rarely changes)
RUN useradd -m -u 1000 appuser

# Layer 3: Set working directory (rarely changes)
WORKDIR /app

# Layer 4: Python dependencies (changes occasionally)
# This layer only rebuilds when requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 5: Application code (changes most frequently)
# This is last so code changes don't bust the cache
COPY --chown=appuser:appuser . .

# Switch to non-root user for security
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/docs')" || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
