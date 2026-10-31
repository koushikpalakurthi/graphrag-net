# ==========================================
# Stage 1: Build React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Python Backend Runtime (Hugging Face Spaces compatible)
# ==========================================
FROM python:3.10-slim

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies as root
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create HF default user (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH
WORKDIR $HOME/app

# Copy project files and ensure user has write permissions for data/
COPY --chown=user:user . $HOME/app
# Copy built React frontend assets into frontend/dist
COPY --chown=user:user --from=frontend-builder /app/frontend/dist $HOME/app/frontend/dist

# Switch to user 1000
USER user

# Hugging Face Spaces default port
EXPOSE 7860
ENV PORT=7860
ENV PYTHONUNBUFFERED=1

CMD ["python", "server.py"]
