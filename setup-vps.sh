#!/bin/bash

# Tenex Telegram Bot - First-Time VPS Setup Script
# Repository: https://github.com/Leumars-o/telegram_trading_bot.git
# This script sets up the bot on a fresh VPS

set -e  # Exit on any error

echo "🚀 Tenex Telegram Bot - VPS Setup"
echo "=================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Repository URL
REPO_URL="https://github.com/Leumars-o/telegram_trading_bot.git"
INSTALL_DIR="$HOME/tenex-telegram-bot"

# Step 1: Update system
echo -e "${YELLOW}📦 Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y
echo -e "${GREEN}✅ System updated${NC}"
echo ""

# Step 2: Install Docker
echo -e "${YELLOW}🐳 Installing Docker...${NC}"
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker already installed${NC}"
else
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}✅ Docker installed${NC}"
fi
echo ""

# Step 3: Install Docker Compose
echo -e "${YELLOW}🐳 Installing Docker Compose plugin...${NC}"
sudo apt-get install -y docker-compose-plugin
echo -e "${GREEN}✅ Docker Compose installed${NC}"
echo ""

# Step 4: Install Git
echo -e "${YELLOW}📥 Installing Git...${NC}"
if command -v git &> /dev/null; then
    echo -e "${GREEN}✅ Git already installed${NC}"
else
    sudo apt-get install -y git
    echo -e "${GREEN}✅ Git installed${NC}"
fi
echo ""

# Step 5: Install Make (optional but convenient)
echo -e "${YELLOW}🔧 Installing Make...${NC}"
if command -v make &> /dev/null; then
    echo -e "${GREEN}✅ Make already installed${NC}"
else
    sudo apt-get install -y make
    echo -e "${GREEN}✅ Make installed${NC}"
fi
echo ""

# Step 6: Clone repository
echo -e "${YELLOW}📥 Cloning repository...${NC}"
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}⚠️  Directory already exists: $INSTALL_DIR${NC}"
    read -p "Do you want to remove it and clone fresh? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        git clone "$REPO_URL" "$INSTALL_DIR"
        echo -e "${GREEN}✅ Repository cloned${NC}"
    else
        echo -e "${YELLOW}⚠️  Using existing directory${NC}"
    fi
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    echo -e "${GREEN}✅ Repository cloned${NC}"
fi
echo ""

# Step 7: Change to project directory
cd "$INSTALL_DIR"

# Step 8: Configure environment
echo -e "${YELLOW}🔐 Setting up environment variables...${NC}"
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo ""
    echo "Please create .env file with your configuration:"
    echo ""
    cat <<EOF
TELEGRAM_BOT_TOKEN="your-bot-token"
TELEGRAM_ADMIN_ID="your-admin-id"
TELEGRAM_NOTIFICATION_CHANNEL="your-channel-id"
JUPITER_API_KEY="your-jupiter-key"
HELIUS_RPC_URL="your-helius-rpc-url"
EOF
    echo ""
    echo "You can create it now or later with:"
    echo "  cd $INSTALL_DIR"
    echo "  nano .env"
    echo ""
    read -p "Press Enter to continue..."
else
    echo -e "${GREEN}✅ .env file exists${NC}"
fi
echo ""

# Step 9: Create required directories
echo -e "${YELLOW}📁 Creating required directories...${NC}"
mkdir -p logs backups
echo -e "${GREEN}✅ Directories created${NC}"
echo ""

# Step 10: Make scripts executable
echo -e "${YELLOW}🔧 Making scripts executable...${NC}"
chmod +x deploy.sh 2>/dev/null || true
echo -e "${GREEN}✅ Scripts are executable${NC}"
echo ""

# Step 11: Enable Docker to start on boot
echo -e "${YELLOW}🔄 Enabling Docker to start on boot...${NC}"
sudo systemctl enable docker
echo -e "${GREEN}✅ Docker will start on boot${NC}"
echo ""

# Step 12: Build and start the bot
echo -e "${YELLOW}🚀 Building and starting the bot...${NC}"
read -p "Do you want to build and start the bot now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if [ -f .env ]; then
        # Need to apply docker group membership
        echo -e "${YELLOW}⚠️  Note: You may need to log out and log back in for Docker permissions to take effect${NC}"
        echo -e "${YELLOW}   Trying to build anyway...${NC}"

        # Try with current session first
        if docker compose build 2>/dev/null; then
            docker compose up -d
            echo -e "${GREEN}✅ Bot is running!${NC}"
            echo ""
            docker compose ps
        else
            # Need new login
            echo -e "${RED}❌ Docker permission denied${NC}"
            echo -e "${YELLOW}Please run the following commands after logging out and back in:${NC}"
            echo ""
            echo "  cd $INSTALL_DIR"
            echo "  docker compose build"
            echo "  docker compose up -d"
        fi
    else
        echo -e "${RED}❌ Cannot start: .env file is missing${NC}"
        echo "Please create .env file first, then run:"
        echo "  cd $INSTALL_DIR"
        echo "  make up"
    fi
else
    echo -e "${YELLOW}⏭️  Skipped. You can start the bot later with:${NC}"
    echo "  cd $INSTALL_DIR"
    echo "  make up"
fi
echo ""

# Summary
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo ""
echo "Next steps:"
echo "  1. Ensure .env file is configured with your credentials"
echo "  2. Log out and log back in (for Docker permissions)"
echo "  3. Start the bot:"
echo "     cd $INSTALL_DIR"
echo "     make up"
echo ""
echo "Useful commands:"
echo "  make deploy     - Pull latest updates from GitHub"
echo "  make logs-live  - View bot logs"
echo "  make status     - Check bot status"
echo "  make restart    - Restart bot"
echo "  make backup     - Backup wallet data"
echo ""
echo "Documentation:"
echo "  - DEPLOYMENT.md - Full deployment guide"
echo "  - README.md     - Project documentation"
echo ""
