FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY api/alembic.ini ./alembic.ini
COPY api/migrations ./migrations
COPY assets /assets
RUN mkdir -p /content
COPY web/content/book.json /content/book.json
COPY web/content/book-expansion.json /content/book-expansion.json
COPY web/content/book-expansion-final.json /content/book-expansion-final.json
COPY web/content/book-fieldwork.json /content/book-fieldwork.json
ENV PRODUCT_ASSET_DIR=/assets
CMD ["sh","-c","alembic upgrade head && exec uvicorn app.production:app --host 0.0.0.0 --port 8080 --proxy-headers"]
