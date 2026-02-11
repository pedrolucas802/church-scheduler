FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# deps do psycopg2-binary normalmente ok, mas vamos garantir certificados e tzdata
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Streamlit no container
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]