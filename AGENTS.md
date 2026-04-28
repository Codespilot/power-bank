# AGENTS.md

## Project Summary
- Django 5 style project managed with `uv`.
- Backend API lives in `api/` and uses Django REST Framework.
- Server-rendered web pages live in `web/` with templates in `templates/web/` and static assets in `static/`.
- Database is MySQL, configured through `.env`.
- Product and domain notes are written in Chinese under `specs/`.

## Setup
1. Install dependencies: `uv sync`
2. Create local env file: `cp .env.example .env`
3. Ensure MySQL exists and matches `.env` values. Default database name is `power_bank`.
4. Apply migrations: `uv run python manage.py migrate`
5. Start dev server: `uv run python manage.py runserver`

## Key Paths
- `config/settings.py`: Django settings, DRF config, logging, MySQL config.
- `config/urls.py`: top-level routing, Swagger, web routes, API routes.
- `api/models.py`: primary data models.
- `api/<domain>/`: domain-specific serializers, views, and URL modules.
- `web/views.py` and `web/urls.py`: template-based page flows.
- `templates/web/`: HTML templates.
- `static/js/`, `static/css/`: front-end assets.
- `specs/`: product behavior, data model notes, and domain requirements.
- `api/management/commands/run_profit_task.py`: manual entry point for profit allocation processing.

## Domain Notes
- The project centers on users, merchants, orders, invites, wallet, withdraw, and profit allocation.
- Read the relevant file in `specs/` before changing business logic. The specs appear to be the main source of domain intent.
- Profit allocation has dedicated task code in `api/profit_tasks.py` and related views in `api/profit_views.py`.

## Working Conventions
- Keep API changes inside the existing domain split under `api/` instead of growing monolithic files.
- If models change, create migrations as part of the same change.
- Preserve existing route behavior: `APPEND_SLASH = False` and custom slash-stripping middleware are enabled, so avoid introducing assumptions that trailing slashes are required.
- Authentication uses custom JWT auth plus Django session auth. Check `api/auth.py` before changing auth behavior.
- Logging writes to `logs/` through custom handlers in `config/logging_filters.py`.
- Prefer minimal, targeted changes. Do not rewrite specs unless the task explicitly asks for it.

## Validation
- Basic project check: `uv run python manage.py check`
- Migration consistency after model edits: `uv run python manage.py makemigrations --check`
- Run tests if they are added: `uv run python manage.py test`
- For profit task changes, validate against a known import record with `uv run python manage.py run_profit_task --order-import-id <id>` when local data is available.

## Cautions
- `.env` contains local secrets and database settings. Do not overwrite it unless requested.
- The repo includes generated `__pycache__` content; ignore it when reasoning about source changes.
- Many behaviors depend on MySQL-backed data. Avoid claiming runtime verification unless the relevant command was actually run against a working local database.
