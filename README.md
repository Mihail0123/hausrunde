# Hausrunde - Backend (Django + DRF)

Rental marketplace backend: listings (ads), availability and bookings, reviews, and a small auth flow (registration, login/logout, "me"). OpenAPI/Swagger is included.

Framework: Django 5 + Django REST Framework  
Auth: JWT (SimpleJWT) with cookies  
Database: MySQL 8  
API docs: /api/docs/ (Swagger UI), /api/schema/ (OpenAPI JSON)  
Containerization: Docker Compose (review stack with demo seed)

## Quick start with Docker

Prerequisite: Docker Desktop is running.

    docker compose -f infra/docker-compose.review.yml up -d --build
    docker compose -f infra/docker-compose.review.yml logs -f web

When the log shows "Starting development server at http://0.0.0.0:8000/", open:

- App: http://127.0.0.1:8001/
- Swagger: http://127.0.0.1:8001/api/docs/
- OpenAPI schema: http://127.0.0.1:8001/api/schema/

Note: the review compose exposes the app on host port 8001.

### Demo seed

The review stack seeds demo data automatically:

- Users: several owners and tenants (password: Passw0rd!)
- Ads: number is controlled by DEMO_SEED_ADS (default 40)
- Reviews: enabled if DEMO_SEED_WITH_REVIEWS=1

### Rebuild or reset

Rebuild the web image after code changes, then restart:

    docker compose -f infra/docker-compose.review.yml build web
    docker compose -f infra/docker-compose.review.yml up -d

Start from scratch (drops DB and media volumes):

    docker compose -f infra/docker-compose.review.yml down -v

## Project layout

    infra/
      docker-compose.review.yml   # review stack (web + MySQL, demo seed)
      docker/
        Dockerfile                # app image
        entrypoint.sh             # migrate, seed, runserver
    src/
      ads/                        # ads, images, bookings, reviews
      users/                      # registration, login/logout, "me"
      static/                     # js, css
      templates/                  # basic templates
      settings.py                 # base settings
      urls.py                     # API routes and spectacular

## Local development (without Docker)

Prerequisites: Python 3.12+, local MySQL 8.

Create a venv and install dependencies:

    python -m venv .venv
    . .venv/Scripts/activate   # Windows
    # or: source .venv/bin/activate
    pip install -r requirements.txt

Create .env in the project root (use env.example as reference):

    DJANGO_SECRET_KEY=change-me
    DEBUG=1
    ALLOWED_HOSTS=127.0.0.1,localhost
    DB_HOST=127.0.0.1
    DB_PORT=3306
    DB_NAME=hausrunde
    DB_USER=appuser
    DB_PASSWORD=app-pass-123

Run migrations and start the server:

    python manage.py migrate
    python manage.py runserver 8000

Open http://127.0.0.1:8000/ and http://127.0.0.1:8000/api/docs/.

Optional local demo seed: set DEMO_SEED=1 (and related vars) and run "python manage.py seed_demo".

## Configuration

Common environment variables:

- DJANGO_SECRET_KEY: Django secret key (review compose uses a dev key)
- DEBUG: 1 to enable debug mode
- ALLOWED_HOSTS: comma separated hosts (127.0.0.1,localhost)
- DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD: MySQL connection
- DEMO_SEED: 1 to seed demo data at startup
- DEMO_SEED_ADS: number of demo ads (default 40)
- DEMO_SEED_WITH_REVIEWS: 1 to also seed reviews

## API documentation

- Swagger UI: GET /api/docs/
- Schema (JSON): GET /api/schema/

Main groups:

- Ads: list, details, create/update, availability, images
- Bookings: create, confirm, reject, cancel
- Reviews
- Auth: registration, login/logout, me

## Testing

    pytest

Note: throttling tests may need isolated runs because of rate limits. If you hit a throttle, retry after a short pause or relax limits in local settings.

## Troubleshooting

- Port conflict: edit infra/docker-compose.review.yml (for example "8002:8000") and change your base URL.
- Reset DB and media: "docker compose -f infra/docker-compose.review.yml down -v" removes containers and named volumes.
- Windows line endings: .gitattributes enforces LF for Docker and shell scripts so builds do not fail on CRLF.
