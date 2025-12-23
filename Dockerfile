FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
        libffi-dev \
        libssl-dev \
        curl \
        ca-certificates \
        nodejs \
        npm && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY bot_modular.py .
COPY trading_integration.py .
COPY trading_methods.py .
COPY jupiter_swap.py .
COPY bsc_swap.py .
COPY wallet_manager.js .
COPY config.json .
COPY services/ ./services/
COPY chains/ ./chains/

# Create directories
RUN mkdir -p ./wallets ./logs ./data

# Create a non-root user
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app

USER botuser

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# Run the bot
CMD ["python", "-u", "bot_modular.py"]
