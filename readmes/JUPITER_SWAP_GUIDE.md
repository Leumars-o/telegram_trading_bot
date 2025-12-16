# Jupiter Swap Guide

Complete guide for swapping SOL to tokens using Jupiter Aggregator API.

## Overview

The `jupiter_swap.py` script allows you to swap SOL to any SPL token on Solana using the Jupiter Aggregator API v6. Jupiter finds the best routes across multiple DEXes for optimal pricing.

## Features

- Swap SOL to any SPL token
- Get real-time quotes with price impact
- Configurable slippage tolerance
- Simulation mode (test without executing)
- Automatic transaction confirmation tracking
- Support for priority fees

## Prerequisites

1. **Python 3.8+** installed
2. **Virtual environment** activated (recommended)
3. **Dependencies** installed
4. **Solana wallet** with SOL for swaps and gas fees

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install solders==0.19.0 requests==2.31.0 base58==2.1.1 python-dotenv==1.0.0
```

2. Verify installation:

```bash
python -c "import solders; import base58; import requests; print('All dependencies installed!')"
```

## Usage

### Interactive Mode

Run the script interactively:

```bash
python jupiter_swap.py
```

You'll be prompted for:

1. **Private Key**: Your wallet's private key (hex or base58 format)
2. **Input Token**: The token you're swapping from (default: SOL)
3. **Output Token**: The token you're swapping to (symbol or address)
4. **Amount**: Amount to swap
5. **Slippage**: Slippage tolerance percentage (default: 0.5%)
6. **Simulate**: Whether to simulate only (y/N)

### Example Session

```
============================================================
Jupiter Swap - SOL to Token Swapper
============================================================

Enter your private key (hex or base58): YOUR_PRIVATE_KEY_HERE

Available tokens:
  SOL: So11111111111111111111111111111111111111112
  USDC: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
  USDT: Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB
  BONK: DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263
  JUP: JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN
  RAY: 4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R
  WIF: EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm

Input token (default: SOL): SOL
Output token (symbol or address): USDC
Amount in SOL: 0.1
Slippage % (default: 0.5): 0.5
Simulate only? (y/N): N

============================================================
Executing swap...
============================================================

Quote received:
  Input: 0.100000000 SOL
  Output: 24.567890 tokens
  Price Impact: 0.0234%
  Routes: 2

Signing transaction...
Sending transaction to network...
Transaction sent: 5Kn8...xyz123
Polling transaction status: 5Kn8...xyz123
Transaction confirmed! Status: confirmed

============================================================
Swap completed successfully!
============================================================
Explorer: https://solscan.io/tx/5Kn8...xyz123
```

### Programmatic Usage

You can also use the `JupiterSwap` class in your own scripts:

```python
from jupiter_swap import JupiterSwap, TOKENS, sol_to_lamports

# Initialize with private key
swap_handler = JupiterSwap(
    private_key="your_private_key_here",
    rpc_url="https://api.mainnet-beta.solana.com"
)

# Swap 0.1 SOL to USDC with 0.5% slippage
success = swap_handler.swap(
    input_mint=TOKENS['SOL'],
    output_mint=TOKENS['USDC'],
    amount=sol_to_lamports(0.1),
    slippage_bps=50,  # 50 basis points = 0.5%
    simulate=False  # Set to True for simulation
)

if success:
    print("Swap completed!")
else:
    print("Swap failed!")
```

### Get Quote Only

```python
from jupiter_swap import JupiterSwap, TOKENS, sol_to_lamports

swap_handler = JupiterSwap("your_private_key_here")

# Get quote without executing
quote = swap_handler.get_quote(
    input_mint=TOKENS['SOL'],
    output_mint=TOKENS['USDC'],
    amount=sol_to_lamports(0.1),
    slippage_bps=50
)

if quote:
    in_amount = int(quote['inAmount']) / 1e9
    out_amount = int(quote['outAmount']) / 1e6
    print(f"Quote: {in_amount} SOL → {out_amount} USDC")
```

## Supported Tokens

The script includes pre-configured addresses for common tokens:

| Symbol | Token Name | Address |
|--------|-----------|---------|
| SOL | Wrapped SOL | So11111111111111111111111111111111111111112 |
| USDC | USD Coin | EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v |
| USDT | Tether | Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB |
| BONK | Bonk | DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 |
| JUP | Jupiter | JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN |
| RAY | Raydium | 4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R |
| WIF | dogwifhat | EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm |

You can also use any SPL token by providing its mint address directly.

## Configuration

### Environment Variables

You can set environment variables in `.env`:

```bash
SOLANA_RPC=https://api.mainnet-beta.solana.com
JUPITER_API_KEY=your_api_key_here  # Optional but recommended for better rate limits
```

**Jupiter API Key (REQUIRED):**
- **An API key is now required** for all Jupiter API usage (including free tier)
- Get a free API key at: https://portal.jup.ag/
- Free tier includes fixed rate limits at no cost
- Pro/Ultra tiers available for higher volume needs
- See [API_KEY_SETUP.md](API_KEY_SETUP.md) for detailed setup instructions

### Slippage Settings

Slippage is specified in basis points (bps):
- 50 bps = 0.5%
- 100 bps = 1%
- 300 bps = 3%

Higher slippage may be needed for:
- Large trades
- Low liquidity tokens
- Volatile market conditions

### RPC Endpoints

For better performance, consider using a paid RPC provider:

- **Helius**: https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
- **QuickNode**: https://YOUR_ENDPOINT.solana-mainnet.quiknode.pro/YOUR_KEY/
- **Alchemy**: https://solana-mainnet.g.alchemy.com/v2/YOUR_KEY

## Private Key Formats

The script accepts private keys in two formats:

1. **Hex format** (128 characters):
   ```
   a1b2c3d4e5f6...
   ```

2. **Base58 format** (Phantom/Solflare export):
   ```
   5Kn8abc123...
   ```

### Extracting Private Key from Wallet

**Phantom Wallet:**
1. Settings → Show Secret Recovery Phrase
2. Use the 12/24 word phrase (not supported directly, needs derivation)
3. Or export private key from Settings → Export Private Key

**Solflare:**
1. Settings → Export Private Key
2. Copy the base58 encoded key

## Security Best Practices

1. **Never share your private key**
2. **Use environment variables** for storing keys:
   ```python
   import os
   private_key = os.getenv('SOLANA_PRIVATE_KEY')
   ```
3. **Test with small amounts first**
4. **Use simulation mode** before executing real swaps
5. **Keep your private keys encrypted** when stored on disk
6. **Consider using a separate wallet** for testing

## Troubleshooting

### "Failed to load private key"

- Check that your private key is in hex or base58 format
- Verify there are no extra spaces or newlines

### "Failed to get quote"

- Check your internet connection
- Verify the token addresses are correct
- Ensure the token pair has liquidity on Jupiter

### "Transaction failed"

- Insufficient SOL for gas fees (keep at least 0.01 SOL)
- Slippage too low (try increasing to 1-2%)
- Token account doesn't exist (Jupiter should create it automatically)
- Network congestion (wait and retry)

### "Transaction timeout"

- Transaction may still be processing
- Check on Solscan: https://solscan.io/tx/YOUR_TX_SIGNATURE
- Increase confirmation timeout in code if needed

## API Rate Limits

Jupiter API has rate limits:
- **Public endpoint**: 600 requests/minute
- Consider caching quotes if making multiple requests
- Add delays between requests if needed

## Adding Custom Tokens

To add more tokens to the predefined list, edit the `TOKENS` dictionary in `jupiter_swap.py`:

```python
TOKENS = {
    'SOL': 'So11111111111111111111111111111111111111112',
    'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    # Add your tokens here
    'MYTOKEN': 'YourTokenMintAddress...',
}
```

## Advanced Features

### Priority Fees

For faster transaction confirmation during network congestion, you can add priority fees:

```python
swap_tx = swap_handler.get_swap_transaction(
    quote=quote,
    user_public_key=swap_handler.wallet_address,
    priority_fee=100000  # 0.0001 SOL priority fee
)
```

### Custom RPC

Use a custom RPC endpoint:

```python
swap_handler = JupiterSwap(
    private_key="your_key",
    rpc_url="https://your-custom-rpc.com"
)
```

## Resources

- **Jupiter Aggregator**: https://jup.ag
- **Jupiter API Docs**: https://station.jup.ag/docs/apis/swap-api
- **Solana Explorer**: https://solscan.io
- **Solana Docs**: https://docs.solana.com

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Jupiter API documentation
3. Check Solana network status
4. Verify your wallet has sufficient SOL

## License

This script is provided as-is for educational and personal use.
