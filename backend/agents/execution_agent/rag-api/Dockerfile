# ✅ Use image with PyTorch pre-installed (much faster!)
FROM pytorch/pytorch:latest

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install only lightweight dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0 \
    chromadb==0.5.23 \
    sentence-transformers==2.7.0

COPY api/ /app/api/

RUN mkdir -p /app/data/vectordb /app/data/models

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]