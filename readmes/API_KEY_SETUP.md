# Jupiter API Key Setup Guide

## The Issue

The error you encountered:
```
Failed to resolve 'quote-api.jup.ag'
```

This happened because:
1. **Old endpoint** (`quote-api.jup.ag`) no longer exists
2. **New endpoint** (`api.jup.ag`) requires an API key
3. Jupiter now **requires API keys for all users** (including free tier)

## What Changed

Jupiter has updated their API infrastructure:
- ❌ Old: `https://quote-api.jup.ag/v6` (no longer exists)
- ✅ New: `https://api.jup.ag/swap/v1` (requires API key)

## Get Your FREE Jupiter API Key

### Step 1: Visit Jupiter Portal

Go to: **https://portal.jup.ag/**

### Step 2: Sign In

- Click "Connect" or "Sign In"
- Enter your email address
- Verify your email

### Step 3: Generate API Key

- Once logged in, find "API Keys" section
- Click "Create New API Key"
- Copy your API key (it looks like: `abc123...`)

### Step 4: Add to .env File

Add this line to your `.env` file:

```bash
JUPITER_API_KEY=your_api_key_here
```

Full `.env` example:
```bash
TELEGRAM_BOT_TOKEN=your_telegram_token
TELEGRAM_ADMIN_ID=your_admin_id
SOLANA_RPC=https://api.mainnet-beta.solana.com
JUPITER_API_KEY=your_jupiter_api_key_here
```

## Free Tier Details

The **FREE tier** includes:
- Fixed rate limiting
- No cost
- Access to all swap functionality
- Perfect for testing and personal use

## Paid Tiers (Optional)

If you need more requests:

### Pro Tier
- 1-500 RPS (requests per second)
- Tiered pricing
- Pay via Helio or Coinflow

### Ultra Tier
- Dynamic rate limits
- Based on your swap volume
- Best for high-volume applications

## Testing Your API Key

Once you have your API key, test it:

```bash
# Add your API key to .env first
python jupiter_swap.py
```

Or test with curl:
```bash
curl -H "x-api-key: YOUR_API_KEY" \
  "https://api.jup.ag/swap/v1/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=50000000&slippageBps=50"
```

## What I Fixed

I've updated the following files:

### 1. jupiter_swap.py
- ✅ Changed API endpoint to `https://api.jup.ag/swap/v1`
- ✅ Added API key support via `x-api-key` header
- ✅ Reads API key from environment variable `JUPITER_API_KEY`

### 2. Documentation
- ✅ Updated JUPITER_SWAP_GUIDE.md with API key instructions
- ✅ Updated SWAP_QUICKSTART.md with .env example
- ✅ Added this setup guide

## Quick Start After Setup

1. Get API key from https://portal.jup.ag/
2. Add to .env: `JUPITER_API_KEY=your_key`
3. Run: `python jupiter_swap.py`
4. Test with simulation mode first!

## Troubleshooting

### "401 Unauthorized"
- API key is missing or invalid
- Check your `.env` file has `JUPITER_API_KEY=...`
- Verify the key is correct (no extra spaces)

### "Rate limit exceeded"
- Free tier has rate limits
- Wait a moment and try again
- Consider upgrading to Pro tier if needed

### "Failed to resolve"
- Check internet connection
- Verify DNS is working: `nslookup api.jup.ag`

## Resources

- **Get API Key**: https://portal.jup.ag/
- **API Documentation**: https://dev.jup.ag/docs
- **API Reference**: https://dev.jup.ag/api-reference
- **Support**: Check Jupiter Discord or docs

## Next Steps

1. Get your free API key now: https://portal.jup.ag/
2. Add it to your `.env` file
3. Run the swap script again
4. Start with small amounts and simulation mode

Your swap script is now updated and ready to use once you add your API key!
