FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cria diretório para o banco de dados e configura permissões
RUN mkdir -p /app/data && \
    chown -R nobody:nogroup /app/data && \
    chmod 777 /app/data

ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=8080

EXPOSE 8080

CMD ["python", "app.py"] 