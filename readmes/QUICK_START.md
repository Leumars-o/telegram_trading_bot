# Quick Start Guide - VPS Deployment

**Repository:** https://github.com/Leumars-o/telegram_trading_bot.git

## First-Time Setup (Choose One Method)

### Method 1: Automated (Recommended)
```bash
ssh user@your-vps-ip
curl -fsSL https://raw.githubusercontent.com/Leumars-o/telegram_trading_bot/main/setup-vps.sh -o setup-vps.sh
chmod +x setup-vps.sh
./setup-vps.sh
```

### Method 2: Manual
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
sudo apt-get install -y docker-compose-plugin git make
sudo usermod -aG docker $USER && newgrp docker

# Clone and setup
git clone https://github.com/Leumars-o/telegram_trading_bot.git ~/tenex-telegram-bot
cd ~/tenex-telegram-bot
mkdir -p logs backups
nano .env  # Configure your credentials

# Start bot
make up
```

## Daily Operations

```bash
# View logs
make logs-live

# Check status
make status

# Restart bot
make restart

# Backup data
make backup

# Deploy updates from GitHub
make deploy
```

## Update Workflow

When you push changes to GitHub:

```bash
# On VPS
cd ~/tenex-telegram-bot
make deploy
```

This will:
1. ✅ Backup your data
2. ✅ Pull latest code
3. ✅ Preserve your .env and wallets
4. ✅ Rebuild container
5. ✅ Restart bot

## Essential Commands

| Command | Description |
|---------|-------------|
| `make up` | Start the bot |
| `make down` | Stop the bot |
| `make restart` | Restart the bot |
| `make logs-live` | View live logs |
| `make status` | Check container status |
| `make deploy` | Update from GitHub |
| `make backup` | Backup wallets/config |

## File Structure

```
~/tenex-telegram-bot/
├── .env              # Your credentials (not in git)
├── wallets/          # User wallet data (not in git)
├── logs/             # Application logs
├── backups/          # Automatic backups
├── bot_modular.py    # Main bot code
├── services/         # Bot services
├── docker-compose.yml # Docker configuration
├── Dockerfile        # Container definition
└── deploy.sh         # Deployment script
```

## Troubleshooting

**Bot not starting?**
```bash
make logs
```

**Check resources?**
```bash
make stats
docker stats
```

**Restore from backup?**
```bash
cd ~/tenex-telegram-bot
tar -xzf backups/bot-backup-YYYYMMDD-HHMMSS.tar.gz
make restart
```

## Full Documentation

See `DEPLOYMENT.md` for comprehensive documentation.
