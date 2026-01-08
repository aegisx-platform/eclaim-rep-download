#!/bin/bash
# =============================================================================
# E-Claim Database Migration to Schema V2 (Option A: Fresh Install)
# This script will DROP existing database and create new one with merged schema
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
DB_TYPE=${DB_TYPE:-mysql}
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-3306}
DB_NAME=${DB_NAME:-eclaim_db}
DB_USER=${DB_USER:-eclaim}
DB_PASSWORD=${DB_PASSWORD:-eclaim_password}

echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}E-Claim Database Migration to Schema V2${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""
echo -e "Database Type: ${YELLOW}${DB_TYPE}${NC}"
echo -e "Database Name: ${YELLOW}${DB_NAME}${NC}"
echo ""

# Confirmation
echo -e "${RED}⚠️  WARNING: This will DROP existing database and create new one!${NC}"
echo -e "${RED}⚠️  All existing data will be DELETED!${NC}"
echo ""
read -p "Have you backed up your data? (yes/no): " BACKUP_CONFIRM

if [ "$BACKUP_CONFIRM" != "yes" ]; then
    echo -e "${RED}Migration cancelled. Please backup your data first.${NC}"
    exit 1
fi

read -p "Type 'DELETE ALL DATA' to confirm: " CONFIRM

if [ "$CONFIRM" != "DELETE ALL DATA" ]; then
    echo -e "${RED}Migration cancelled.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Starting migration...${NC}"
echo ""

# =============================================================================
# MySQL Migration
# =============================================================================
if [ "$DB_TYPE" == "mysql" ]; then
    echo -e "${YELLOW}[1/4] Creating backup...${NC}"
    BACKUP_FILE="backup_before_v2_$(date +%Y%m%d_%H%M%S).sql"
    mysqldump -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD $DB_NAME > "$BACKUP_FILE" 2>/dev/null || echo "No existing database to backup"

    if [ -f "$BACKUP_FILE" ]; then
        echo -e "${GREEN}✓ Backup saved: $BACKUP_FILE${NC}"
    fi

    echo ""
    echo -e "${YELLOW}[2/4] Dropping existing database...${NC}"
    mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD -e "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    echo -e "${GREEN}✓ Database dropped${NC}"

    echo ""
    echo -e "${YELLOW}[3/4] Creating new database...${NC}"
    mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD -e "CREATE DATABASE $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
    echo -e "${GREEN}✓ Database created${NC}"

    echo ""
    echo -e "${YELLOW}[4/4] Importing Schema V2...${NC}"
    mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD $DB_NAME < database/schema-mysql-merged.sql
    echo -e "${GREEN}✓ Schema imported${NC}"

# =============================================================================
# PostgreSQL Migration
# =============================================================================
elif [ "$DB_TYPE" == "postgresql" ]; then
    echo -e "${YELLOW}[1/4] Creating backup...${NC}"
    BACKUP_FILE="backup_before_v2_$(date +%Y%m%d_%H%M%S).sql"
    PGPASSWORD=$DB_PASSWORD pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME > "$BACKUP_FILE" 2>/dev/null || echo "No existing database to backup"

    if [ -f "$BACKUP_FILE" ]; then
        echo -e "${GREEN}✓ Backup saved: $BACKUP_FILE${NC}"
    fi

    echo ""
    echo -e "${YELLOW}[2/4] Dropping existing database...${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>/dev/null || true
    echo -e "${GREEN}✓ Database dropped${NC}"

    echo ""
    echo -e "${YELLOW}[3/4] Creating new database...${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c "CREATE DATABASE $DB_NAME;"
    echo -e "${GREEN}✓ Database created${NC}"

    echo ""
    echo -e "${YELLOW}[4/4] Importing Schema V2...${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f database/schema-postgresql-merged.sql
    echo -e "${GREEN}✓ Schema imported${NC}"

else
    echo -e "${RED}Error: Unsupported DB_TYPE: $DB_TYPE${NC}"
    echo "Supported types: mysql, postgresql"
    exit 1
fi

# =============================================================================
# Verification
# =============================================================================
echo ""
echo -e "${GREEN}==============================================================================${NC}"
echo -e "${GREEN}Migration completed successfully!${NC}"
echo -e "${GREEN}==============================================================================${NC}"
echo ""

if [ "$DB_TYPE" == "mysql" ]; then
    echo -e "${YELLOW}Verification:${NC}"
    mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p$DB_PASSWORD $DB_NAME -e "
        SELECT 'Tables' as Info, COUNT(*) as Count FROM information_schema.tables WHERE table_schema = '$DB_NAME'
        UNION ALL
        SELECT 'eclaim_imported_files', COUNT(*) FROM eclaim_imported_files
        UNION ALL
        SELECT 'claim_rep_opip_nhso_item', COUNT(*) FROM claim_rep_opip_nhso_item
        UNION ALL
        SELECT 'claim_rep_orf_nhso_item', COUNT(*) FROM claim_rep_orf_nhso_item;
    "
elif [ "$DB_TYPE" == "postgresql" ]; then
    echo -e "${YELLOW}Verification:${NC}"
    PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c "
        SELECT 'Tables' as info, COUNT(*) as count FROM information_schema.tables WHERE table_schema = 'public'
        UNION ALL
        SELECT 'eclaim_imported_files', COUNT(*)::text FROM eclaim_imported_files
        UNION ALL
        SELECT 'claim_rep_opip_nhso_item', COUNT(*)::text FROM claim_rep_opip_nhso_item
        UNION ALL
        SELECT 'claim_rep_orf_nhso_item', COUNT(*)::text FROM claim_rep_orf_nhso_item;
    "
fi

echo ""
echo -e "${GREEN}✓ Database ready for use!${NC}"
echo -e "${GREEN}✓ Backup saved in: $BACKUP_FILE${NC}"
echo ""
echo -e "Next steps:"
echo -e "1. Import E-Claim files via Web UI: http://localhost:5001/files"
echo -e "2. Or use CLI: python eclaim_import.py downloads/your_file.xls"
echo ""
