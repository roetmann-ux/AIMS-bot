# AIMS — container for the hosted/public deployment.
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Public build defaults: hidden Settings, passphrase gate, spend cap. Secrets come from the host env.
ENV AIMS_HOSTED=1
EXPOSE 8765
# Hosts inject $PORT; fall back to 8765 locally.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8765}"]
