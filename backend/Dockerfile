FROM python:3.13-slim

WORKDIR /app

# Dépendances système pour Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code
COPY engine/ ./engine/
COPY api.py dev_server.py ./

# Port du serveur de développement
EXPOSE 8765

CMD ["python3", "dev_server.py"]
