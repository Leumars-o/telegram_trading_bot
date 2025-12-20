.PHONY: help build up down restart logs logs-live status clean backup deploy update

# Default target
help:
	@echo "Tenex Telegram Bot - Docker Management"
	@echo ""
	@echo "Available commands:"
	@echo "  make build      - Build the Docker image"
	@echo "  make up         - Start the bot (detached)"
	@echo "  make down       - Stop the bot"
	@echo "  make restart    - Restart the bot"
	@echo "  make logs       - Show last 100 log lines"
	@echo "  make logs-live  - Follow logs in real-time"
	@echo "  make status     - Check container status"
	@echo "  make stats      - Show resource usage"
	@echo "  make backup     - Backup wallets and config"
	@echo "  make deploy     - Pull from GitHub and deploy updates"
	@echo "  make update     - Rebuild and restart (local changes)"
	@echo "  make clean      - Stop and remove containers/volumes"
	@echo ""

# Build the Docker image
build:
	docker compose build

# Start the bot
up:
	docker compose up -d
	@echo "Bot started! Use 'make logs-live' to view logs"

# Stop the bot
down:
	docker compose down

# Restart the bot
restart:
	docker compose restart
	@echo "Bot restarted!"

# Show logs (last 100 lines)
logs:
	docker compose logs --tail=100

# Follow logs in real-time
logs-live:
	docker compose logs -f

# Check status
status:
	docker compose ps

# Show resource usage
stats:
	docker stats tenex-telegram-bot --no-stream

# Clean everything (WARNING: removes volumes)
clean:
	docker compose down -v
	@echo "⚠️  Containers and volumes removed!"

# Backup wallets and config
backup:
	@mkdir -p backups
	@tar -czf backups/bot-backup-$$(date +%Y%m%d-%H%M%S).tar.gz wallets/ config.json .env
	@echo "✅ Backup created in backups/ directory"
	@ls -lh backups/ | tail -1

# Deploy from GitHub (pull latest code and rebuild)
deploy:
	@chmod +x deploy.sh
	@./deploy.sh

# Rebuild and restart (for local code changes)
update:
	docker compose down
	docker compose build
	docker compose up -d
	@echo "✅ Bot updated and restarted!"
