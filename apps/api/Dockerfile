FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update \
	&& apt-get install --no-install-recommends -y tesseract-ocr \
	&& rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY seed.py ./
COPY scripts/start_hcode.sh ./scripts/start_hcode.sh
RUN chmod +x ./scripts/start_hcode.sh

EXPOSE 8000

CMD ["./scripts/start_hcode.sh"]
