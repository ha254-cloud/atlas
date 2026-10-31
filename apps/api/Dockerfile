FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update \
	&& apt-get install --no-install-recommends -y clamav-daemon clamav-freshclam tesseract-ocr \
	&& sed -i 's/^LocalSocket /#LocalSocket /' /etc/clamav/clamd.conf \
	&& printf '\nTCPSocket 3310\nTCPAddr 127.0.0.1\n' >> /etc/clamav/clamd.conf \
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
