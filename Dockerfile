FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends cron tzdata && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime && echo "America/Sao_Paulo" > /etc/timezone

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/media /app/staticfiles

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py createcachetable && python manage.py collectstatic --noinput && exec gunicorn loterias.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]