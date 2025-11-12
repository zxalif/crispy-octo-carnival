#!/bin/bash
# Fix PostgreSQL permissions for rixly user
# Use this if you're getting "permission denied for schema public" errors

set -e

echo "========================================="
echo "Fixing PostgreSQL permissions for rixly"
echo "========================================="
echo ""

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "Error: PostgreSQL is not running. Please start PostgreSQL first."
    exit 1
fi

echo "Connecting to PostgreSQL as postgres user..."
echo ""

sudo -u postgres psql << EOF
-- Connect to rixly database
\c rixly

-- Grant schema permissions (required for PostgreSQL 15+)
GRANT ALL ON SCHEMA public TO rixly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rixly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rixly;

-- Make rixly the owner of the public schema (ensures full control)
ALTER SCHEMA public OWNER TO rixly;

-- Verify permissions
\dn+ public

EOF

echo ""
echo "========================================="
echo "Permissions fixed successfully!"
echo "========================================="
echo ""
echo "You can now run migrations:"
echo "  docker compose -f docker-compose.production.yml restart"
echo ""

