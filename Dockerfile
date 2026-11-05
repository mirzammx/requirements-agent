# Runs the bid tools in Linux, independent of Windows Smart App Control.
# Locally, compose.yaml mounts the project folder over /app, so code edits and out/ stay on the host.
# On Azure, the copied code below is what runs, with data/ on an Azure Files share.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Kolkata
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

EXPOSE 8000
ENTRYPOINT ["python"]
# One worker so background AI jobs and their locks live in one process; threads serve the pages.
CMD ["-m", "gunicorn", "--workers", "1", "--threads", "8", "--timeout", "120", "--bind", "0.0.0.0:8000", "webapp:app_from_env()"]
