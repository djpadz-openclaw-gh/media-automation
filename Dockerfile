FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY notify_sonarr.py notify_radarr.py ./

# State file will be mounted as a volume
VOLUME ["/app/state"]

ENTRYPOINT ["python3"]
