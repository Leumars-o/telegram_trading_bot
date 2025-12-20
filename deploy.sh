#!/bin/bash

# Tenex Telegram Bot - GitHub Deployment Script
# Repository: https://github.com/Leumars-o/telegram_trading_bot.git
# This script pulls the latest code from GitHub and restarts the bot

set -e  # Exit on any error

echo "🚀 Starting deployment from GitHub..."
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# GitHub repository
REPO_URL="https://github.com/Leumars-o/telegram_trading_bot.git"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Error: git is not installed${NC}"
    echo "Install it with: sudo apt-get install git"
    exit 1
fi

# Check if docker compose is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: docker is not installed${NC}"
    exit 1
fi

# Backup current state before update
echo -e "${YELLOW}📦 Creating backup...${NC}"
mkdir -p backups
BACKUP_FILE="backups/pre-deploy-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
tar -czf "$BACKUP_FILE" wallets/ config.json .env 2>/dev/null || true
echo -e "${GREEN}✅ Backup created: $BACKUP_FILE${NC}"
echo ""

# Save current .env and config.json (in case they're not in git)
echo -e "${YELLOW}💾 Saving local configuration...${NC}"
cp .env .env.backup 2>/dev/null || true
cp config.json config.json.backup 2>/dev/null || true
echo ""

# Pull latest code from GitHub
echo -e "${YELLOW}📥 Pulling latest code from GitHub...${NC}"
echo "Repository: $REPO_URL"
git fetch origin
git pull origin main || git pull origin master

# Check if pull was successful
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Code updated successfully${NC}"
else
    echo -e "${RED}❌ Failed to pull from GitHub${NC}"
    exit 1
fi
echo ""

# Restore .env and config.json if they were backed up
echo -e "${YELLOW}🔧 Restoring local configuration...${NC}"
if [ -f .env.backup ]; then
    cp .env.backup .env
    rm .env.backup
    echo -e "${GREEN}✅ .env restored${NC}"
fi

if [ -f config.json.backup ]; then
    # Only restore if the pulled version is significantly different
    # (this prevents overwriting intentional config updates)
    if ! cmp -s config.json config.json.backup; then
        echo -e "${YELLOW}⚠️  config.json has changed in repository${NC}"
        echo -e "${YELLOW}   Your local version is backed up as config.json.backup${NC}"
        echo -e "${YELLOW}   Review and merge changes if needed${NC}"
    fi
    rm config.json.backup 2>/dev/null || true
fi
echo ""

# Stop the current container
echo -e "${YELLOW}🛑 Stopping current container...${NC}"
docker compose down
echo -e "${GREEN}✅ Container stopped${NC}"
echo ""

# Rebuild the image with new code
echo -e "${YELLOW}🔨 Building new Docker image...${NC}"
docker compose build --no-cache
echo -e "${GREEN}✅ Image built successfully${NC}"
echo ""

# Start the container
echo -e "${YELLOW}🚀 Starting bot...${NC}"
docker compose up -d
echo -e "${GREEN}✅ Bot started successfully${NC}"
echo ""

# Show status
echo -e "${YELLOW}📊 Container status:${NC}"
docker compose ps
echo ""

# Show recent logs
echo -e "${YELLOW}📋 Recent logs:${NC}"
docker compose logs --tail=20
echo ""

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "Commands:"
echo "  View logs:     docker compose logs -f"
echo "  Check status:  docker compose ps"
echo "  Restart bot:   docker compose restart"
echo ""
