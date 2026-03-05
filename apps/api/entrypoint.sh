#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}============================================${NC}"
echo -e "${YELLOW}  LinkedIn Autopilot API - Entrypoint${NC}"
echo -e "${YELLOW}============================================${NC}"

# Function to wait for postgres
wait_for_postgres() {
    echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"

    # Extract connection details from DATABASE_URL
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    # We need to convert to postgres:// for pg_isready

    local host="postgres"
    local port="5432"
    local dbname="linkedin_autopilot"
    local user="linkedin_user"

    # Override with environment variables if available
    if [ -n "$POSTGRES_USER" ]; then
        user="$POSTGRES_USER"
    fi

    if [ -n "$POSTGRES_DB" ]; then
        dbname="$POSTGRES_DB"
    fi

    # Parse DATABASE_URL if available
    if [ -n "$DATABASE_URL" ]; then
        # Extract host from DATABASE_URL
        if [[ "$DATABASE_URL" =~ @([^:]+): ]]; then
            host="${BASH_REMATCH[1]}"
        fi

        # Extract port from DATABASE_URL
        if [[ "$DATABASE_URL" =~ :([0-9]+)/ ]]; then
            port="${BASH_REMATCH[1]}"
        fi

        # Extract dbname from DATABASE_URL
        if [[ "$DATABASE_URL" =~ /([^/]+)$ ]]; then
            dbname="${BASH_REMATCH[1]}"
        fi
    fi

    # Wait for postgres with timeout
    local timeout=60
    local counter=0

    until pg_isready -h "$host" -p "$port" -U "$user" -d "$dbname" > /dev/null 2>&1; do
        counter=$((counter + 1))
        if [ $counter -gt $timeout ]; then
            echo -e "${RED}ERROR: PostgreSQL did not become ready within ${timeout} seconds${NC}"
            exit 1
        fi
        echo -e "${YELLOW}  PostgreSQL is not ready yet... waiting (${counter}/${timeout})${NC}"
        sleep 1
    done

    echo -e "${GREEN}PostgreSQL is ready!${NC}"
}

# Wait for postgres to be ready
wait_for_postgres

# Set PYTHONPATH so alembic can find app modules
export PYTHONPATH=/app:$PYTHONPATH

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
alembic upgrade head

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Migrations completed successfully!${NC}"
else
    echo -e "${RED}ERROR: Migrations failed${NC}"
    exit 1
fi

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Starting Uvicorn server...${NC}"
echo -e "${GREEN}============================================${NC}"

# Start the application
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
