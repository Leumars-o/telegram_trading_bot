# Jupiter Swap - Quick Start Guide

Get started with swapping SOL to tokens in 5 minutes.

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

Or install just what you need for swapping:

```bash
pip install solders requests base58 python-dotenv
```

## Step 2: Prepare Your Wallet

You need:
- A Solana wallet private key
- Some SOL for the swap (minimum 0.01 SOL + gas fees)

### Get Your Private Key

**From Phantom:**
1. Open Phantom wallet
2. Settings → Security & Privacy → Export Private Key
3. Enter password and copy the key

**From Solflare:**
1. Open Solflare wallet
2. Settings → Export Private Key
3. Copy the key

## Step 3: Quick Test (Recommended)

Test with simulation mode first:

```bash
python jupiter_swap.py
```

When prompted:
- Enter your private key
- Choose `SOL` for input token
- Choose `USDC` for output token
- Enter a small amount like `0.01`
- Use default slippage `0.5`
- **Enter `y` for simulate only**

This will show you the quote without executing the swap.

## Step 4: Execute Real Swap

Once you're comfortable:

```bash
python jupiter_swap.py
```

Same prompts but:
- **Enter `N` for simulate only** to execute the real swap

## Step 5: Verify Transaction

After swap completes, you'll see:
```
Swap completed successfully!
Explorer: https://solscan.io/tx/YOUR_TRANSACTION_SIGNATURE
```

Click the link to view your transaction on Solscan.

## Using in Your Code

Create a `.env` file:

```bash
SOLANA_PRIVATE_KEY=your_private_key_here
SOLANA_RPC=https://api.mainnet-beta.solana.com
JUPITER_API_KEY=your_api_key_here  # REQUIRED - Get free at https://portal.jup.ag/
```

**IMPORTANT:** Jupiter API key is now **required** (even for free tier). Get yours at https://portal.jup.ag/ - it's free! See [API_KEY_SETUP.md](API_KEY_SETUP.md) for instructions.

Run the example script:

```bash
python swap_example.py
```

Or use in your own code:

```python
from jupiter_swap import JupiterSwap, TOKENS, sol_to_lamports

# Initialize
swap = JupiterSwap(private_key="your_key")

# Swap 0.1 SOL to USDC
swap.swap(
    input_mint=TOKENS['SOL'],
    output_mint=TOKENS['USDC'],
    amount=sol_to_lamports(0.1),
    slippage_bps=50
)
```

## Common Issues

### "Failed to load private key"
- Remove any spaces or quotes from your key
- Try both hex and base58 formats

### "Insufficient funds"
- Make sure you have enough SOL
- Keep at least 0.01 SOL for gas fees

### "Slippage exceeded"
- Increase slippage to 1-2% for volatile tokens
- Try again during less volatile market conditions

## Next Steps

- Read [JUPITER_SWAP_GUIDE.md](JUPITER_SWAP_GUIDE.md) for detailed documentation
- Check [swap_example.py](swap_example.py) for code examples
- Start with small amounts and test thoroughly

## Safety Tips

1. Always test with small amounts first
2. Use simulation mode before real swaps
3. Double-check token addresses
4. Keep private keys secure
5. Monitor transactions on Solscan

## Support

- Jupiter Docs: https://station.jup.ag/docs/apis/swap-api
- Solana Explorer: https://solscan.io
- Check transaction status if timeout occurs

Happy swapping!
