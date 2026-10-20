FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV RENDER=true
ENV PORT=10000
ENV WEBHOOK_URL=https://kino-bot-s6um.onrender.com

EXPOSE 10000

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
