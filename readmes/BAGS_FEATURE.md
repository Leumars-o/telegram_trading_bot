# Bags Feature 🎒

## Overview

The **Bags** feature allows users to view all the tokens they've bought through the bot in one convenient place!

## What It Does

- Shows all tokens the user has purchased
- Displays total SOL spent on each token
- Shows number of buys for each token
- Shows when the first buy was made
- Provides quick access to view each token's details

## How to Access

### From Main Menu:
1. Open the bot with `/start`
2. Click **"🎒 View Bags"** button
3. See all your token holdings!

### What You'll See:

```
🎒 Your Bags
━━━━━━━━━━━━━━━━━━━━

Total Tokens: 3

1. CALVIN
   💰 Spent: 0.0400 SOL
   📊 Buys: 1
   📅 First: 2025-12-11

2. USDC
   💰 Spent: 2.5000 SOL
   📊 Buys: 3
   📅 First: 2025-12-10

3. BONK
   💰 Spent: 1.0000 SOL
   📊 Buys: 2
   📅 First: 2025-12-09

[📊 View CALVIN]
[📊 View USDC]
[📊 View BONK]
[🔄 Refresh Bags] [⬅️ Back]
```

## Features

✅ **Track All Purchases** - See every token you've bought
✅ **Total Spent** - Know how much SOL you've invested in each token
✅ **Buy History** - See how many times you bought each token
✅ **Quick Access** - Click any token to view its current details
✅ **Auto-Updates** - Orders are automatically tracked when you buy

## Button Actions

- **📊 View [TOKEN]** - Opens the token's detail page with current price and buy options
- **🔄 Refresh Bags** - Refreshes the bags list
- **⬅️ Back** - Returns to main menu

## Empty State

If you haven't bought any tokens yet:

```
🎒 Your Bags
━━━━━━━━━━━━━━━━━━━━

You haven't bought any tokens yet!

Send a token contract address to start trading.

[⬅️ Back to Menu]
```

## How Orders Are Tracked

Every time you complete a buy transaction:
1. Order is created with token details, amount, timestamp
2. Order is saved to your user profile
3. Order appears in the token's order history
4. Order is counted in your bags

## Technical Details

### Data Stored Per Token:
- **Token Address** - Unique identifier
- **Token Symbol** - Display name (e.g., CALVIN, USDC)
- **Total SOL Spent** - Sum of all purchases
- **Buy Count** - Number of buy transactions
- **First Buy Date** - When you first bought this token

### Location:
- Method: `show_bags()` in `trading_integration.py`
- Callback: `view_bags` in button_handler
- Menu button: Main menu (line 931)

## Use Cases

1. **Portfolio Overview** - See all your token investments at a glance
2. **Quick Access** - Jump to any token's page to check price or buy more
3. **Track Spending** - Know how much you've invested in each token
4. **Trading History** - See when you first bought each token

## Future Enhancements

Potential additions:
- Show current token value (requires on-chain balance check)
- Calculate profit/loss (buy price vs current price)
- Sort by various criteria (date, amount, etc.)
- Filter by profitable/unprofitable tokens
- Show percentage allocation of portfolio

## Example User Flow

```
User: /start
Bot: [Shows main menu with "🎒 View Bags" button]

User: *clicks "🎒 View Bags"*
Bot: [Shows list of all tokens bought]

User: *clicks "📊 View CALVIN"*
Bot: [Shows CALVIN token details with buy buttons]

User: *clicks "1 💵" to buy more*
Bot: [Processes buy, adds to bags]

User: *clicks "🎒 View Bags" again*
Bot: [Shows updated CALVIN with 2 buys, more SOL spent]
```

## Summary

The Bags feature provides a central place to:
- ✅ View all your token purchases
- ✅ Track total investment per token
- ✅ Quickly access token details
- ✅ Monitor your trading activity

It's like a portfolio manager built right into your trading bot! 🎒
