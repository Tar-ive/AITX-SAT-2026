FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir "psycopg[binary]==3.3.4" "discord.py==2.6.4"
COPY server.py /app/server.py
EXPOSE 8001
CMD ["python", "/app/server.py"]
