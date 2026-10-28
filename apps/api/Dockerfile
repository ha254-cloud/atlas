FROM python:3.11-slim
WORKDIR /app
RUN apt-get update \
	&& apt-get install --no-install-recommends -y tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
