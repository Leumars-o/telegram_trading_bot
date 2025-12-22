# Tenex Telegram Bot - Docker Deployment Guide

This guide will help you deploy the Tenex Telegram Bot on your VPS using Docker.

## Prerequisites

- VPS with Docker and Docker Compose installed
- SSH access to your VPS
- Your `.env` file configured with bot credentials

## VPS Specifications (Tested)

- 4 GB RAM
- 2 CPU Cores
- 40 GB NVMe Disk
- Ubuntu 20.04+ (or any Linux with Docker support)

## Quick Start (Recommended: GitHub Method)

**Repository:** https://github.com/Leumars-o/telegram_trading_bot.git

### Option 1: Automated Setup (Easiest)

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Download and run the setup script
curl -fsSL https://raw.githubusercontent.com/Leumars-o/telegram_trading_bot/main/setup-vps.sh -o setup-vps.sh
chmod +x setup-vps.sh
./setup-vps.sh

# Follow the prompts to complete setup
```

The setup script will:
- Install Docker and Docker Compose
- Install Git and Make
- Clone the repository
- Set up directories
- Configure auto-start

### Option 2: Manual GitHub Setup

#### 1. Install Docker and Git

```bash
# Update package index
sudo apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Install Git
sudo apt-get install git make

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Enable Docker on boot
sudo systemctl enable docker
```

#### 2. Clone from GitHub

```bash
# Clone the repository
git clone https://github.com/Leumars-o/telegram_trading_bot.git ~/tenex-telegram-bot
cd ~/tenex-telegram-bot

# Create required directories
mkdir -p logs backups

# Make deployment script executable
chmod +x deploy.sh
```

#### 3. Configure Environment

```bash
cd /home/user/tenex-telegram-bot

# Make sure your .env file is present and configured
nano .env
```

Ensure your `.env` contains:
```env
TELEGRAM_BOT_TOKEN="your-bot-token"
TELEGRAM_ADMIN_ID="your-admin-id"
TELEGRAM_NOTIFICATION_CHANNEL="your-channel-id"
JUPITER_API_KEY="your-jupiter-key"
HELIUS_RPC_URL="your-helius-rpc-url"
```

#### 4. Start the Bot

```bash
# Build and start (using make for convenience)
make up

# Or using docker compose directly
docker compose up -d --build

# Check if container is running
make status

# View logs
make logs-live
```

---

## Updating from GitHub (Recommended Workflow)

Once your bot is deployed, you can easily update it by pulling the latest code from GitHub.

### Deploy Latest Updates

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Navigate to bot directory
cd ~/tenex-telegram-bot

# Deploy latest version from GitHub
make deploy

# This will:
# 1. Backup current wallets and config
# 2. Pull latest code from GitHub
# 3. Preserve your .env and config.json
# 4. Rebuild Docker image
# 5. Restart the bot
```

### Manual Update Process

If you prefer to update manually:

```bash
cd ~/tenex-telegram-bot

# Pull latest code
git pull origin main

# Rebuild and restart
make update

# View logs to verify
make logs-live
```

### Update Workflow Best Practices

1. **Always backup before updating:**
   ```bash
   make backup
   ```

2. **Check current status:**
   ```bash
   make status
   git status
   ```

3. **Deploy updates:**
   ```bash
   make deploy
   ```

4. **Verify deployment:**
   ```bash
   make logs-live
   ```

### What Gets Updated vs Preserved

**Updated (from GitHub):**
- Bot code (`bot_modular.py`, etc.)
- Python dependencies (`requirements.txt`)
- Services and modules
- Docker configuration

**Preserved (your local files):**
- `.env` file (your credentials)
- `wallets/` directory (user wallets)
- `config.json` (unless intentionally updated in repo)
- `logs/` directory
- `backups/` directory

## Container Management

### Start the bot
```bash
docker compose up -d
```

### Stop the bot
```bash
docker compose down
```

### Restart the bot
```bash
docker compose restart
```

### View logs (live)
```bash
docker compose logs -f
```

### View logs (last 100 lines)
```bash
docker compose logs --tail=100
```

### Check container status
```bash
docker compose ps
```

### Rebuild after code changes
```bash
docker compose down
docker compose up -d --build
```

## Auto-Start on Boot

The bot is configured with `restart: unless-stopped` which means:
- ✅ Starts automatically when VPS boots
- ✅ Restarts automatically if it crashes
- ❌ Won't restart if you manually stop it with `docker compose down`

To ensure Docker starts on boot:
```bash
sudo systemctl enable docker
```

## Persistent Data

The following directories are mounted as volumes for data persistence:

- `./wallets` - User wallet data (CRITICAL)
- `./config.json` - Bot configuration
- `./logs` - Application logs
- `./.env` - Environment variables

**These files will persist even if you rebuild or restart the container.**

## Resource Usage

Current configuration (optimized for your VPS):
- **CPU Limit**: 25% of one core (max 0.25 cores)
- **CPU Reserved**: 10% of one core
- **Memory Limit**: 256 MB
- **Memory Reserved**: 128 MB

This leaves plenty of resources (~3.75GB RAM and 1.75 CPU cores) for other services.

## Logging

Logs are automatically rotated to save disk space:
- Max log file size: 5 MB
- Max log files kept: 3 (15 MB total)
- Compression: Enabled

View logs location:
```bash
ls -lh logs/
```

## Monitoring

### Check container health
```bash
docker inspect tenex-telegram-bot --format='{{.State.Health.Status}}'
```

### Check resource usage
```bash
docker stats tenex-telegram-bot
```

### Check disk space
```bash
df -h
du -sh wallets/ logs/
```

## Backup

### Backup critical data
```bash
# Create backup directory
mkdir -p ~/backups

# Backup wallets and config
tar -czf ~/backups/bot-backup-$(date +%Y%m%d).tar.gz wallets/ config.json .env

# List backups
ls -lh ~/backups/
```

### Restore from backup
```bash
tar -xzf ~/backups/bot-backup-YYYYMMDD.tar.gz
```

## Troubleshooting

### Bot not starting
```bash
# Check logs for errors
docker compose logs

# Check if container is running
docker compose ps

# Restart container
docker compose restart
```

### Out of memory
```bash
# Check memory usage
docker stats

# Increase memory limit in docker-compose.yml if needed
# Edit: memory: 512M
```

### Container keeps restarting
```bash
# View logs to see the error
docker compose logs --tail=50

# Check environment variables
docker compose exec telegram-bot env | grep TELEGRAM
```

### Update bot code
```bash
# Pull latest code (if using git)
git pull

# Rebuild and restart
docker compose down
docker compose up -d --build
```

## Security Recommendations

1. **Firewall**: Only open necessary ports (SSH, if you have a webhook)
```bash
sudo ufw allow 22/tcp
sudo ufw enable
```

2. **Keep Docker updated**
```bash
sudo apt-get update && sudo apt-get upgrade docker-ce docker-ce-cli
```

3. **Secure .env file**
```bash
chmod 600 .env
```

4. **Regular backups**: Set up automated backups of wallet data
```bash
# Add to crontab (daily backup at 2 AM)
0 2 * * * cd /home/user/tenex-telegram-bot && tar -czf ~/backups/bot-backup-$(date +\%Y\%m\%d).tar.gz wallets/ config.json .env
```

## Performance Optimization

The Docker container is optimized for lightweight operation:
- ✅ Python 3.11 slim base image (small footprint)
- ✅ Minimal system dependencies
- ✅ No cache during pip install
- ✅ Non-root user for security
- ✅ Compressed log rotation
- ✅ Resource limits to prevent overuse

## Support

If you encounter issues:
1. Check the logs: `docker compose logs -f`
2. Verify .env configuration
3. Ensure wallet files exist in `./wallets/`
4. Check VPS disk space: `df -h`
5. Check VPS memory: `free -h`

## Maintenance

### Weekly checks
- Check disk space: `df -h`
- Check logs: `docker compose logs --tail=50`
- Check container health: `docker compose ps`

### Monthly maintenance
- Backup wallet data
- Review and clean old logs
- Update system packages: `sudo apt-get update && sudo apt-get upgrade`
