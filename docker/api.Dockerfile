FROM python:3.12-slim

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

CMD ["python", "-m", "api", "--host", "0.0.0.0", "--port", "5000"]
