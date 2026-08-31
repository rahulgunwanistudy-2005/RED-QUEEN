# --- stage 1: build the Svelte frontend (one app, one store, one stream) -----
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- stage 2: the FastAPI control plane + real GCP surfaces -------------------
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY sentinel ./sentinel
COPY migrations ./migrations
COPY --from=frontend /fe/dist ./frontend/dist

# Cloud Run injects $PORT (default 8080); bind it. ADC + Cloud SQL socket come
# from the runtime service account and --add-cloudsql-instances.
ENV PORT=8080
EXPOSE 8080
CMD exec uvicorn sentinel.app:app --host 0.0.0.0 --port ${PORT}
