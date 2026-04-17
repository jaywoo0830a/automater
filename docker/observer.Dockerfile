FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && playwright install-deps

# VNC stack for remote browser viewing
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    websockify \
    novnc \
    && rm -rf /var/lib/apt/lists/*

COPY automator/ automator/
COPY observer/ observer/
COPY selectors/ selectors/

EXPOSE 7080-7089

CMD ["python", "-m", "observer", "run"]
