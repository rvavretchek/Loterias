FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY vendor/django_sqlite_tenants /usr/local/lib/python3.12/site-packages/django_sqlite_tenants

COPY . .

RUN mkdir -p /app/data /app/media /app/staticfiles

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn loterias.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile -"]