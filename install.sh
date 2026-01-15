#!/bin/bash
#
# NHSO Revenue Intelligence - Quick Install Script
# Version: 3.1.0
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
#
# Or with options:
#   curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --mysql
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
VERSION="v3.1.0"
INSTALL_DIR="nhso-revenue"
DB_TYPE="postgresql"
GITHUB_RAW="https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mysql)
            DB_TYPE="mysql"
            shift
            ;;
        --no-db)
            DB_TYPE="none"
            shift
            ;;
        --dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        -h|--help)
            echo "NHSO Revenue Intelligence Installer"
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --mysql      Use MySQL instead of PostgreSQL"
            echo "  --no-db      Download-only mode (no database)"
            echo "  --dir NAME   Installation directory (default: nhso-revenue)"
            echo "  --version    Version to install (default: v3.1.0)"
            echo "  -h, --help   Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║       NHSO Revenue Intelligence - Quick Install          ║"
echo "║                     Version ${VERSION}                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Docker
echo -e "${YELLOW}[1/5] Checking requirements...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed${NC}"
    echo "Please install Docker Compose first"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"

# Create directory
echo -e "${YELLOW}[2/5] Creating installation directory...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Warning: Directory '$INSTALL_DIR' already exists${NC}"
    read -p "Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 1
    fi
fi

mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"
echo -e "${GREEN}✓ Created directory: $(pwd)${NC}"

# Download files
echo -e "${YELLOW}[3/5] Downloading configuration files...${NC}"

# Select docker-compose file based on DB type
case $DB_TYPE in
    postgresql)
        COMPOSE_FILE="docker-compose.yml"
        ;;
    mysql)
        COMPOSE_FILE="docker-compose-mysql.yml"
        ;;
    none)
        COMPOSE_FILE="docker-compose-no-db.yml"
        ;;
esac

# Download docker-compose
curl -fsSL "${GITHUB_RAW}/${COMPOSE_FILE}" -o docker-compose.yml
echo -e "${GREEN}✓ Downloaded docker-compose.yml (${DB_TYPE})${NC}"

# Download .env.example
curl -fsSL "${GITHUB_RAW}/.env.example" -o .env
echo -e "${GREEN}✓ Downloaded .env${NC}"

# Create directories
mkdir -p downloads/{rep,stm,smt}
mkdir -p logs
mkdir -p config
echo -e "${GREEN}✓ Created directories${NC}"

# Configure credentials
echo -e "${YELLOW}[4/5] Configuring credentials...${NC}"
echo ""
echo -e "${BLUE}Please enter your NHSO E-Claim credentials:${NC}"
echo "(These will be saved in .env file)"
echo ""

read -p "ECLAIM_USERNAME: " ECLAIM_USER
read -s -p "ECLAIM_PASSWORD: " ECLAIM_PASS
echo ""

# Update .env file
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/ECLAIM_USERNAME=.*/ECLAIM_USERNAME=${ECLAIM_USER}/" .env
    sed -i '' "s/ECLAIM_PASSWORD=.*/ECLAIM_PASSWORD=${ECLAIM_PASS}/" .env
else
    # Linux
    sed -i "s/ECLAIM_USERNAME=.*/ECLAIM_USERNAME=${ECLAIM_USER}/" .env
    sed -i "s/ECLAIM_PASSWORD=.*/ECLAIM_PASSWORD=${ECLAIM_PASS}/" .env
fi

echo -e "${GREEN}✓ Credentials configured${NC}"

# Start services
echo -e "${YELLOW}[5/5] Starting services...${NC}"
echo ""

# Use docker compose or docker-compose
if docker compose version &> /dev/null; then
    docker compose pull
    docker compose up -d
else
    docker-compose pull
    docker-compose up -d
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            Installation Complete!                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Access the application at: ${BLUE}http://localhost:5001${NC}"
echo ""
echo -e "Useful commands:"
echo -e "  ${YELLOW}cd ${INSTALL_DIR}${NC}"
echo -e "  ${YELLOW}docker compose logs -f web${NC}     # View logs"
echo -e "  ${YELLOW}docker compose down${NC}            # Stop services"
echo -e "  ${YELLOW}docker compose up -d${NC}           # Start services"
echo ""
echo -e "Documentation: ${BLUE}https://github.com/aegisx-platform/eclaim-rep-download${NC}"
echo ""
