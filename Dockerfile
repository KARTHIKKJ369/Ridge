FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# System deps: git for pip installs from git, build-essential for native exts
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user required by Hugging Face Spaces
RUN useradd -m -u 1000 user

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source files
COPY *.py ./
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY alembic.ini ./

# Copy env defaults (actual secrets are injected via runtime environment)
COPY .env.example .env

# Pre-download the sentence-transformers embedding model into the image
RUN python -c "from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='BAAI/bge-large-en-v1.5')"


# Copy compiled React frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create writable dirs and hand ownership to the non-root user
RUN mkdir -p /app/data && chown -R user:user /app


USER user

EXPOSE 7860

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-7860}"]
