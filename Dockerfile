FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --ignore-scripts
COPY frontend/ ./
RUN rm -f next.config.mjs next.config.ts next.config.js && printf '%s\n' 'module.exports={output:"export",trailingSlash:true,images:{unoptimized:true},webpack:function(c){c.resolve.alias.canvas=false;c.resolve.alias.encoding=false;return c;}};' > next.config.js
RUN node scripts/copy-worker.js
RUN npm run build
RUN ls -la /app/frontend && test -d out

FROM node:20-slim AS admin
WORKDIR /app/frontend-admin
COPY frontend-admin/package.json frontend-admin/package-lock.json* ./
RUN npm install
COPY frontend-admin/ ./
RUN npm run build
RUN test -d out

FROM node:20-slim AS stt
WORKDIR /app/frontend-stt
COPY frontend-stt/package.json frontend-stt/package-lock.json* ./
RUN npm install
COPY frontend-stt/ ./
RUN npm run build
RUN test -d out

FROM python:3.12-slim
WORKDIR /app
# ffmpeg cuts long recordings into pieces for the transcription engine
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY --from=frontend /app/frontend/out frontend/out
COPY --from=admin /app/frontend-admin/out frontend-admin/out
COPY --from=stt /app/frontend-stt/out frontend-stt/out
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
