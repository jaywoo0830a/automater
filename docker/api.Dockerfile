FROM python:3.14.4-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && playwright install-deps

# VNC stack for remote login
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    websockify \
    novnc \
    && rm -rf /var/lib/apt/lists/*

COPY automator/ automator/
COPY cli/ cli/
COPY api/ api/
COPY selectors/ selectors/

EXPOSE 5000
EXPOSE 6080-6089

# --port 미지정 시 api/__main__.py가 AUTOMATOR_API_PORT 환경변수를 읽음 (없으면 5000)
CMD ["python", "-m", "api", "--host", "0.0.0.0"]
