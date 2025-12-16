# Trading Feature Integration Guide

## Overview

Your Telegram bot now has full Jupiter Swap integration for Solana token trading! Users can now buy tokens directly from the bot when they detect a contract address.

## What Was Implemented

### 1. **Automatic CA Detection with Buy Menu**
When a user sends a Solana contract address (CA), the bot:
- Fetches token information from DexScreener
- Displays comprehensive token details
- Shows interactive buy menu with:
  - **1 💵** - Buy with 1 SOL
  - **3 💵** - Buy with 3 SOL
  - **X SOL 💵** - Custom amount buy
  - **⚙️ Slippage** - Configure slippage (default: Auto 10%)
  - **📋 Orders** - View all orders for this token
  - **🔄 Refresh** - Refresh token data
  - **⬅️ Back** - Return to main menu

### 2. **Buy Flow**
1. User clicks a buy button (1 SOL, 3 SOL, or custom)
2. Bot gets real-time quote from Jupiter Aggregator
3. Shows quote with:
   - Amount to pay in SOL
   - Estimated tokens to receive
   - Price impact percentage
   - Current slippage setting
4. User confirms or cancels
5. If confirmed, bot executes swap via Jupiter
6. Shows success/failure message with transaction details

### 3. **Slippage Configuration**
Users can set slippage tolerance:
- **Auto (10%)** - Default, handles most volatile tokens
- **0.5%** - For stable pairs/low volatility
- **1%** - Standard setting
- **3%** - For moderate volatility
- **5%** - For higher volatility

### 4. **Orders Tracking**
- Bot tracks all buy orders per user
- Shows order history for each token
- Displays: order number, amount, timestamp, status

### 5. **Custom Amount Input**
- Users can enter any SOL amount (e.g., 0.1, 0.5, 2.5)
- Bot validates input and proceeds with buy flow

## Files Modified/Created

### Modified:
1. **tenex_trading_bot.py**
   - Added Jupiter Swap imports
   - Added TradingMixin inheritance
   - Added trading context and orders tracking
   - Modified `display_token_info()` to show buy buttons
   - Added trading callback handlers in `button_handler()`

### Created:
2. **jupiter_swap.py**
   - Complete Jupiter Swap API integration
   - Handles quotes, transactions, signing, sending
   - Production-ready with error handling

3. **trading_integration.py**
   - Trading Mixin class with all trading methods
   - `execute_buy()` - Get quote and show confirmation
   - `confirm_buy()` - Execute the swap
   - `show_slippage_menu()` - Show slippage options
   - `set_slippage()` - Update slippage setting
   - `show_orders()` - Display order history
   - `ask_custom_amount()` - Prompt for custom SOL amount

4. **API_KEY_SETUP.md**
   - Guide to get free Jupiter API key
   - Setup instructions

5. **JUPITER_SWAP_GUIDE.md**
   - Comprehensive Jupiter Swap documentation
   - Usage examples
   - Troubleshooting

6. **SWAP_QUICKSTART.md**
   - Quick start guide for Jupiter Swap

## How to Test

### 1. **Setup Jupiter API Key**
```bash
# Add to .env file
JUPITER_API_KEY=your_api_key_here
```
Get your free API key at: https://portal.jup.ag/

### 2. **Start the Bot**
```bash
python tenex_trading_bot.py
```

### 3. **Test Token Detection**
Send a Solana token contract address to the bot, for example:
```
So11111111111111111111111111111111111111112  # Wrapped SOL
EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v  # USDC
DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263  # BONK
```

### 4. **Test Buy Flow**
1. Bot shows token info with buy buttons
2. Click "1 💵" to buy with 1 SOL
3. Review the quote
4. Click "✅ Confirm Buy"
5. Wait for transaction to complete

### 5. **Test Other Features**
- Click "⚙️ Slippage" to change slippage
- Click "📋 Orders" to view order history
- Click "X SOL 💵" and enter custom amount like "0.1"
- Click "🔄 Refresh" to update token data

## User Flow Example

```
User: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

Bot: 🔍 Detecting chain and fetching token data...

Bot: [Shows USDC token info]
     🪙 Token Information
     ━━━━━━━━━━━━━━━━━━━━

     📛 Name: USD Coin (USDC)
     ⛓️ Chain: Solana
     💹 Price: $1.00000000
     📊 Market Cap: $...
     ...

     [1 💵] [3 💵] [X SOL 💵]
     [⚙️ Slippage (Auto)]
     [📋 Orders] [🔄 Refresh]
     [⬅️ Back]

User: *clicks "1 💵"*

Bot: 🔄 Processing buy order...

     💰 Amount: 1 SOL
     🪙 Token: USDC
     ⚙️ Slippage: 10%

     ⏳ Getting quote...

Bot: 📊 Buy Order Quote
     ━━━━━━━━━━━━━━━━━━━━

     💰 You Pay: 1.000000000 SOL
     🪙 You Receive: ~200.00 USDC
     📊 Price Impact: 0.0012%
     ⚙️ Slippage: 10%

     ⚠️ Confirm this transaction?

     [✅ Confirm Buy] [❌ Cancel]

User: *clicks "✅ Confirm Buy"*

Bot: ⏳ Executing Swap...

     💰 Amount: 1 SOL
     🪙 Token: USDC

     ⏳ Please wait...

Bot: ✅ Buy Order Completed!
     ━━━━━━━━━━━━━━━━━━━━

     💰 Spent: 1 SOL
     🪙 Token: USDC
     📋 Status: Success

     🔍 Check your transaction on Solscan

     [🔄 Refresh Token] [📋 View Orders] [⬅️ Back to Menu]
```

## Configuration

### Default Settings
- **Slippage**: Auto (10%)
- **Network**: Solana Mainnet
- **RPC**: https://api.mainnet-beta.solana.com

### Environment Variables
Add to your `.env` file:
```bash
JUPITER_API_KEY=your_api_key_here  # REQUIRED
SOLANA_RPC=https://api.mainnet-beta.solana.com  # Optional
```

## Important Notes

### Requirements
1. **Jupiter API Key is REQUIRED** - Get free key at https://portal.jup.ag/
2. **User must have a Solana wallet** in the bot
3. **Wallet must have sufficient SOL** for trade + gas fees

### Safety Features
- Real-time quotes before execution
- Price impact warnings
- Slippage protection
- User confirmation required
- Transaction status tracking

### Limitations
- **Solana only** - Currently only works for Solana tokens
- **Buy only** - Sell functionality not yet implemented
- **SPL tokens** - Only supports SPL token standard

## Troubleshooting

### "❌ Trading session expired"
- Token data expired, user needs to re-scan the contract address

### "❌ No Solana wallet found"
- User needs to create a Solana wallet first via /start

### "❌ Failed to get quote"
- Token may have low liquidity
- Invalid contract address
- Jupiter API issue
- Check API key is set correctly

### "❌ Buy Order Failed"
- Insufficient SOL balance
- Slippage exceeded
- Network congestion
- Try increasing slippage or retry

### "401 Unauthorized"
- Jupiter API key missing or invalid
- Check `.env` has `JUPITER_API_KEY`

## Next Steps / Future Enhancements

Potential additions:
1. **Sell functionality** - Sell tokens back to SOL
2. **Limit orders** - Set buy/sell at specific prices
3. **Position tracking** - Track P&L for each token
4. **Multi-chain support** - Add Ethereum, Base, etc.
5. **Advanced orders** - Stop-loss, take-profit
6. **Portfolio view** - See all token holdings
7. **Price alerts** - Notify when price hits target

## Support

- **Jupiter API Docs**: https://dev.jup.ag/docs
- **Setup Guide**: See API_KEY_SETUP.md
- **Swap Guide**: See JUPITER_SWAP_GUIDE.md
- **Quick Start**: See SWAP_QUICKSTART.md

## Summary

Your bot now has a complete trading integration! Users can:
✅ Detect Solana token CAs automatically
✅ View real-time token data
✅ Buy tokens with 1 SOL, 3 SOL, or custom amounts
✅ Configure slippage (0.5% to 10%)
✅ View order history
✅ Refresh data anytime

The integration is production-ready with proper error handling, user confirmations, and safety features!
