FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY assets /assets
ENV PRODUCT_ASSET_DIR=/assets
CMD ["uvicorn","app.bootstrap:app","--host","0.0.0.0","--port","8080","--proxy-headers"]
