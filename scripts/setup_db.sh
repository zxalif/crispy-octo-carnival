#!/bin/bash
# Setup PostgreSQL database for Rixly

set -e

echo "Setting up PostgreSQL database for Rixly..."

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "Error: PostgreSQL is not running. Please start PostgreSQL first."
    exit 1
fi

# Create database and user
psql -U postgres << EOF
-- Create database if not exists
SELECT 'CREATE DATABASE rixly'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'rixly')\gexec

-- Create user if not exists
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'rixly') THEN
        CREATE USER rixly WITH PASSWORD 'rixly';
    END IF;
END
\$\$;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE rixly TO rixly;
\c rixly
GRANT ALL ON SCHEMA public TO rixly;
EOF

echo "Database setup complete!"
echo "Run 'alembic upgrade head' to create tables."

