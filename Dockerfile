FROM python:3.11-slim

# Instalar dependências essenciais do WeasyPrint e ferramentas de compilação
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar os requerimentos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo o resto do projeto
COPY . .

# Expor a porta 5002
EXPOSE 5002

# Comando de boot do servidor
CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:app"]
