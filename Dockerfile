# AuditPilot AI: MCP server (:8000) + web app (:8501) in one CPU-only container (fits Voroa's 2 vCPU / 4 GB).
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8000 UI_PORT=8501 PYTHONUNBUFFERED=1
EXPOSE 8000 8501
CMD ["sh", "scripts/start.sh"]
