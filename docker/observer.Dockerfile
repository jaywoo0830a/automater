FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium \
    && playwright install-deps

COPY automator/ automator/
COPY observer/ observer/
COPY selectors/ selectors/

CMD ["python", "-m", "observer", "run"]
