FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    BACKEND_URL=http://127.0.0.1:8000

# System deps + Node.js 20 LTS for Next.js frontend
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Non-root user UID 1000 required by Hugging Face Spaces
RUN useradd -m -u 1000 user
WORKDIR /app

# 1. Backend Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/backend/requirements.txt

# 2. Frontend dependencies & production Next.js build
COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN cd /app/frontend && npm ci

COPY frontend /app/frontend
RUN cd /app/frontend && BACKEND_URL=http://127.0.0.1:8000 npm run build

# 3. Copy backend, Harvey collectors, datasets, contracts, and startup script
COPY backend /app/backend
COPY harvey /app/harvey
COPY data /app/data
COPY contracts /app/contracts
COPY docker_start.sh /app/docker_start.sh

RUN mkdir -p /app/exports /app/data \
    && chmod +x /app/docker_start.sh \
    && chown -R user:user /app

USER user
EXPOSE 7860

CMD ["/app/docker_start.sh"]
