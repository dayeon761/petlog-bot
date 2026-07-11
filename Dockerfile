FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

RUN mkdir -p /app/data
ENV DB_PATH=/app/data/bot.db

CMD ["python", "-m", "bot.main"]
