# Runs the bid tools in Linux, independent of Windows Smart App Control.
# The project folder is mounted at /app by compose.yaml, so code edits and out/ stay on the host.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python"]
