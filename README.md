# Stores Inventory System

Inventory and sales management for stores built with Django.

## Environments

- `development` uses `config.settings.development`
- `staging` uses `config.settings.staging`
- `production` uses `config.settings.production`

## Local run

```bash
cp .env.development.example .env.development
python manage.py migrate
python manage.py bootstrap_superuser
python manage.py runserver
```

## Docker

```bash
docker compose --env-file .env.development up --build
docker compose --env-file .env.staging up --build -d
docker compose --env-file .env.production up --build -d
```

The entrypoint runs migrations, collects static files, and ensures the `kannde` superuser exists.

Use the `DJANGO_*` variables from the environment files so Docker does not inherit unrelated machine-wide `DEBUG` or `SECRET_KEY` values.
