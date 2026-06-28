# knitting-app-backend

Backend of the Knitting App, a web application for knitters and crocheters that allows importing, translating and adapting knitting patterns. Built with FastAPI, PostgreSQL, SQLAlchemy and Docker.

## Prerequisites

- Docker and Docker Compose
- A Firebase project with a service account (`firebase-service-account.json`)
- A Groq API key
- A Ravelry Pro developer app (Client ID and Client Secret)
- A YouTube Data API v3 key

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/knitting-app-tfm/knitting-app-backend.git
cd knitting-app-backend
```

**2. Copy the environment file and fill in the values**
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```
DATABASE_URL=postgresql://user:password@db:5432/knitting
SECRET_KEY=your-secret-key
RAVELRY_CLIENT_ID=your-ravelry-client-id
RAVELRY_CLIENT_SECRET=your-ravelry-client-secret
RAVELRY_REDIRECT_URI=https://localhost:8000/auth/ravelry/callback
FRONTEND_BASE_URL=http://localhost:5173
GROQ_API_KEY=your-groq-api-key
FIREBASE_WEB_API_KEY=your-firebase-web-api-key
YOUTUBE_API_KEY=your-youtube-api-key
```

**3. Add your Firebase service account**

Place your `firebase-service-account.json` file in the root of the repository. This file is not versioned for security reasons.

**4. Generate a self-signed certificate for local HTTPS** (required for Ravelry OAuth callback)
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```

## Running the project

```bash
docker-compose up --build
```

The backend will be available at `https://localhost:8000`. The API documentation (Swagger) is available at `https://localhost:8000/docs`.

On first startup, the abbreviation dictionary is automatically seeded from the CSV file at `scripts/data/abbreviations_seed.csv`.

## Running the tests

```bash
docker-compose exec backend pytest --cov
```

## Scripts

**Populate YouTube video links**

This one-off script enriches the abbreviation dictionary with YouTube tutorial links. It is resumable — if interrupted by the daily API quota limit, it will pick up where it left off on the next run.

```bash
docker-compose exec backend python scripts/populate_video_links.py
```

## Project structure

```
app/
  core/          → configuration, database, Firebase, security
  models/        → SQLAlchemy models
  repositories/  → database operations
  services/      → business logic
  routers/       → HTTP endpoints
  schemas/       → Pydantic validation schemas
alembic/         → database migrations
scripts/         → one-off maintenance scripts
tests/           → unit and integration tests
```