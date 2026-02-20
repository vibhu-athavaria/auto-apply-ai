# LinkedIn Autopilot

A SaaS application that automates LinkedIn job discovery and Easy Apply using AI agents.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running with Docker](#running-with-docker)
- [Database Migrations](#database-migrations)
- [API Endpoints](#api-endpoints)
- [Running Tests](#running-tests)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following installed:

| Software | Minimum Version | Installation |
|----------|-----------------|--------------|
| Docker | 20.10+ | [Install Docker](https://docs.docker.com/get-docker/) |
| Docker Compose | 2.0+ | [Install Docker Compose](https://docs.docker.com/compose/install/) |

### Verify Installation

```bash
docker --version
docker compose version
```

---

## Quick Start

```bash
# 1. Clone the repository
git clone <repository-url>
cd "AutoApply AI"

# 2. Copy environment file
cp .env.example .env

# 3. Generate a secure secret key and update .env
# IMPORTANT: Change the default SECRET_KEY in production!
sed -i '' "s/your-secret-key-change-in-production/$(openssl rand -hex 32)/" .env

# 4. Build and start all services
docker compose up -d --build

# 5. Run database migrations
docker compose exec api alembic upgrade head

# 6. Verify the API is running
curl http://localhost:8000/health/
```

The API will be available at `http://localhost:8000`

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

```bash
cp .env.example .env
```

#### Database Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `linkedin_user` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `linkedin_password` |
| `POSTGRES_DB` | Database name | `linkedin_autopilot` |
| `DATABASE_URL` | Async database connection URL | `postgresql+asyncpg://...` |

#### Redis Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |

#### JWT Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key (CHANGE IN PRODUCTION!) | `your-secret-key-change-in-production` |
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | `30` |

#### File Upload Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `MAX_UPLOAD_SIZE` | Maximum file upload size (bytes) | `10485760` (10MB) |
| `ALLOWED_EXTENSIONS` | Allowed file extensions | `.pdf,.doc,.docx` |

#### Logging Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |

### Generate Secure Secret Key

For production, generate a secure secret key:

```bash
openssl rand -hex 32
```

Update your `.env` file:

```
SECRET_KEY=<your-generated-key>
```

---

## Running with Docker

### Start All Services

```bash
# Build and start in detached mode
docker compose up -d --build

# View logs
docker compose logs -f api

# View all service logs
docker compose logs -f
```

### Service Architecture

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | FastAPI backend |
| `postgres` | 5432 | PostgreSQL database |
| `redis` | 6379 | Redis cache/queue |

### Stop Services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v
```

### Rebuild Services

```bash
# Rebuild API service
docker compose up -d --build api

# Rebuild all services
docker compose up -d --build
```

### View Service Status

```bash
docker compose ps
```

---

## Database Migrations

Migrations are managed using Alembic.

### Run Migrations

```bash
# Apply all pending migrations
docker compose exec api alembic upgrade head

# Check current migration version
docker compose exec api alembic current
```

### Create New Migration

```bash
# Create a new migration after model changes
docker compose exec api alembic revision --autogenerate -m "description of changes"

# Apply the new migration
docker compose exec api alembic upgrade head
```

### Rollback Migration

```bash
# Rollback one migration
docker compose exec api alembic downgrade -1

# Rollback all migrations
docker compose exec api alembic downgrade base
```

### Migration History

```bash
# View migration history
docker compose exec api alembic history
```

---

## API Endpoints

Base URL: `http://localhost:8000`

Interactive documentation available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Authentication

#### Register a New User

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Login

```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Resumes

All resume endpoints require authentication. Include the token in the Authorization header:

```bash
TOKEN="your-access-token"
```

#### Upload Resume

```bash
curl -X POST http://localhost:8000/resumes/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/resume.pdf"
```

**Response:**
```json
{
  "id": "uuid-here",
  "user_id": "user-uuid",
  "filename": "resume.pdf",
  "file_path": "/app/uploads/user-id/resume-id.pdf",
  "file_size": 102400,
  "content_type": "application/pdf",
  "uploaded_at": "2024-01-15T10:30:00"
}
```

#### List Resumes

```bash
curl -X GET http://localhost:8000/resumes/ \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "id": "uuid-here",
    "user_id": "user-uuid",
    "filename": "resume.pdf",
    "file_path": "/app/uploads/user-id/resume-id.pdf",
    "file_size": 102400,
    "content_type": "application/pdf",
    "uploaded_at": "2024-01-15T10:30:00"
  }
]
```

### Job Search Profiles

All profile endpoints require authentication.

#### Create Profile

```bash
curl -X POST http://localhost:8000/profiles/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "Software Engineer Python",
    "location": "San Francisco, CA",
    "remote_preference": "remote",
    "salary_min": 100000,
    "salary_max": 200000
  }'
```

**Response:**
```json
{
  "id": "profile-uuid",
  "user_id": "user-uuid",
  "keywords": "Software Engineer Python",
  "location": "San Francisco, CA",
  "remote_preference": "remote",
  "salary_min": 100000.0,
  "salary_max": 200000.0,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T10:30:00"
}
```

#### List Profiles

```bash
curl -X GET http://localhost:8000/profiles/ \
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "id": "profile-uuid",
    "user_id": "user-uuid",
    "keywords": "Software Engineer Python",
    "location": "San Francisco, CA",
    "remote_preference": "remote",
    "salary_min": 100000.0,
    "salary_max": 200000.0,
    "created_at": "2024-01-15T10:30:00",
    "updated_at": "2024-01-15T10:30:00"
  }
]
```

#### Update Profile

```bash
curl -X PUT http://localhost:8000/profiles/{profile_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "keywords": "Senior Software Engineer Python",
    "location": "New York, NY"
  }'
```

**Response:**
```json
{
  "id": "profile-uuid",
  "user_id": "user-uuid",
  "keywords": "Senior Software Engineer Python",
  "location": "New York, NY",
  "remote_preference": "remote",
  "salary_min": 100000.0,
  "salary_max": 200000.0,
  "created_at": "2024-01-15T10:30:00",
  "updated_at": "2024-01-15T11:00:00"
}
```

### Health Check

```bash
curl -X GET http://localhost:8000/health/
```

**Response:**
```json
{
  "status": "healthy",
  "service": "api"
}
```

---

## Running Tests

### Run Tests in Docker

```bash
# Run all tests
docker compose exec api pytest tests/ -v

# Run specific test file
docker compose exec api pytest tests/test_auth.py -v

# Run with coverage
docker compose exec api pytest tests/ -v --cov=app --cov-report=term-missing
```

### Run Tests Locally (without Docker)

```bash
# Navigate to API directory
cd apps/api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

### Test Categories

| Test File | Description |
|-----------|-------------|
| `test_auth.py` | Authentication endpoints |
| `test_health.py` | Health check endpoint |
| `test_resumes.py` | Resume upload and listing |

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

**Error:** `Error: port is already allocated`

**Solution:**
```bash
# Find process using the port
lsof -i :8000  # or :5432, :6379

# Kill the process
kill -9 <PID>

# Or change ports in docker-compose.yml
```

#### 2. Database Connection Failed

**Error:** `Connection refused` or `could not connect to server`

**Solution:**
```bash
# Check if postgres is healthy
docker compose ps postgres

# Check postgres logs
docker compose logs postgres

# Restart postgres
docker compose restart postgres

# Wait for health check to pass
docker compose up -d --wait postgres
```

#### 3. Migration Fails

**Error:** `Can't locate revision identified by 'xxx'`

**Solution:**
```bash
# Check current migration state
docker compose exec api alembic current

# If database is out of sync, reset (WARNING: data loss)
docker compose down -v
docker compose up -d
docker compose exec api alembic upgrade head
```

#### 4. Redis Connection Failed

**Error:** `Redis connection error`

**Solution:**
```bash
# Check redis status
docker compose ps redis

# Test redis connection
docker compose exec redis redis-cli ping

# Restart redis
docker compose restart redis
```

#### 5. Authentication 401 Unauthorized

**Error:** `401 Unauthorized` or `Could not validate credentials`

**Solution:**
- Ensure token is included in Authorization header
- Check token hasn't expired (default: 30 minutes)
- Verify SECRET_KEY matches between token creation and validation

```bash
# Get a new token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "yourpassword"}'
```

#### 6. File Upload Fails

**Error:** `413 Request Entity Too Large` or `Invalid file type`

**Solution:**
- Check file size is under `MAX_UPLOAD_SIZE` (default: 10MB)
- Verify file extension is in `ALLOWED_EXTENSIONS` (.pdf, .doc, .docx)
- Ensure Content-Type is `multipart/form-data`

#### 7. Container Won't Start

**Error:** Container exits immediately

**Solution:**
```bash
# Check container logs
docker compose logs api

# Check for configuration errors
docker compose config

# Rebuild without cache
docker compose build --no-cache api
docker compose up -d api
```

### Useful Debugging Commands

```bash
# View all container logs
docker compose logs -f

# Execute shell in API container
docker compose exec api /bin/bash

# Check container resource usage
docker stats

# Inspect container
docker inspect linkedin_autopilot_api

# Check network connectivity
docker compose exec api ping postgres
docker compose exec api ping redis
```

### Reset Everything

```bash
# Stop and remove all containers, networks, and volumes
docker compose down -v

# Remove all images
docker compose down --rmi all

# Start fresh
docker compose up -d --build
docker compose exec api alembic upgrade head
```

---

## Architecture

For detailed architecture documentation, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

For product roadmap, see [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md).

For engineering constraints, see [`AGENTS.md`](AGENTS.md).

---

## License

Proprietary - All rights reserved.
