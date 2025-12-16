# Limit Sell Orders - Implementation Guide

## Overview

The Tenex Trading Bot now supports **limit sell orders** based on:
- **Price targets** (e.g., sell when price reaches $0.01)
- **Market cap targets** (e.g., sell when market cap reaches $10M)

This guide explains the implementation and how to enable automatic order monitoring and execution.

## Architecture

### Components

1. **LimitOrderService** (`services/limit_order_service.py`)
   - Manages creation, storage, and cancellation of limit orders
   - Stores orders in JSON file (`wallets/limit_orders.json`)
   - Provides methods to check if orders should execute

2. **TradingMixin Methods** (`trading_integration.py`)
   - `show_limit_order_menu()` - Display limit order options
   - `ask_limit_price_target()` - Get price target from user
   - `ask_limit_mcap_target()` - Get market cap target from user
   - `create_limit_order()` - Create and save limit order
   - `view_limit_orders()` - View active/completed orders
   - `cancel_limit_order()` - Cancel an active order

3. **Bot Integration** (`bot_modular.py`)
   - Button handlers for limit order actions
   - Message handlers for user input (price/mcap values)
   - Limit Order button in token info display

## User Flow

### Creating a Price-Based Limit Order

1. User scans token contract address
2. Bot displays token info with "⏰ Limit Orders" button
3. User clicks "⏰ Limit Orders"
4. Bot shows limit order menu:
   - 💰 Set Price Target
   - 📊 Set Market Cap Target
   - 📋 View Active Orders
5. User clicks "💰 Set Price Target"
6. Bot asks for target price (e.g., "0.001")
7. User enters price
8. Bot asks for sell percentage (25%, 50%, 75%, 100%, custom)
9. User selects percentage
10. ✅ Limit order created!

### Creating a Market Cap-Based Limit Order

Same flow as price-based, but user enters market cap target:
- Can use "K" for thousands (e.g., "500K" = $500,000)
- Can use "M" for millions (e.g., "5M" = $5,000,000)
- Can enter full number (e.g., "1500000")

## Order Monitoring & Execution

**IMPORTANT**: The limit order system requires a **background monitoring task** to check prices and execute orders automatically.

### Manual Implementation (Current State)

The limit order service is fully implemented for order CRUD operations, but automatic execution requires you to implement a monitoring loop.

### Recommended Implementation

Create a separate monitoring script (`order_monitor.py`):

```python
import asyncio
import logging
from pathlib import Path
from services import LimitOrderService, BalanceService, TokenService
from jupiter_swap import JupiterSwap, JUPITER_TOKENS, sol_to_lamports
from telegram import Bot
import json

logger = logging.getLogger(__name__)

async def monitor_limit_orders():
    """Monitor and execute limit orders"""

    # Initialize services
    limit_service = LimitOrderService(Path('wallets'))
    token_service = TokenService(config)

    # Load config
    with open('config.json') as f:
        config = json.load(f)

    # Initialize Telegram bot for notifications
    bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))

    while True:
        try:
            # Get all active limit orders
            active_orders = limit_service.get_all_active_orders()

            for order in active_orders:
                token_address = order['token_address']
                user_id = order['user_id']
                order_type = order['order_type']
                trigger_value = order['trigger_value']
                sell_percentage = order['sell_percentage']

                # Fetch current token data
                result = await token_service.detect_and_fetch_token(token_address)

                if not result:
                    logger.warning(f"Could not fetch data for {token_address}")
                    continue

                pair_data = result['data']
                current_price = float(pair_data.get('priceUsd', 0))
                current_market_cap = float(pair_data.get('marketCap', 0)) if pair_data.get('marketCap') else 0

                # Check if order should execute
                should_execute = limit_service.should_execute_order(
                    order, current_price, current_market_cap
                )

                if should_execute:
                    logger.info(f"Executing limit order {order['order_id']}")

                    # Execute the sell
                    success = await execute_limit_sell(
                        user_id, token_address, sell_percentage, config
                    )

                    if success:
                        # Mark as executed
                        limit_service.mark_order_executed(
                            order['order_id'],
                            current_price,
                            current_market_cap
                        )

                        # Notify user
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"✅ Limit order executed!\n\n"
                                 f"🪙 Token: {order['token_symbol']}\n"
                                 f"💸 Sold: {sell_percentage}%\n"
                                 f"💰 Price: ${current_price:.10f}\n"
                                 f"📊 Market Cap: ${current_market_cap:,.0f}"
                        )
                    else:
                        # Mark as failed
                        limit_service.mark_order_failed(
                            order['order_id'],
                            "Swap execution failed"
                        )

                        await bot.send_message(
                            chat_id=user_id,
                            text=f"❌ Limit order failed to execute\n\n"
                                 f"Order ID: {order['order_id']}\n"
                                 f"Please try manually."
                        )

            # Sleep for interval (e.g., check every 30 seconds)
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Error in order monitor: {e}", exc_info=True)
            await asyncio.sleep(30)

async def execute_limit_sell(user_id: int, token_address: str, percentage: float, config):
    """Execute a limit sell order"""
    try:
        # Load user data to get private key
        with open('wallets/user_wallets.json') as f:
            user_wallets = json.load(f)

        user_data = user_wallets.get(str(user_id), {})
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        sol_wallet = user_data['wallet_slots'][primary_wallet]['chains']['SOL']
        private_key = sol_wallet['private_key']

        # Initialize swap handler
        swap_handler = JupiterSwap(private_key)

        # Get token balance
        balance_info = swap_handler.get_token_balance(token_address)
        if not balance_info:
            return False

        token_balance = balance_info['balance']
        amount_to_sell = int(token_balance * (percentage / 100))

        if amount_to_sell == 0:
            return False

        # Execute swap (token -> SOL)
        slippage_bps = 1000  # 10% slippage for limit orders
        success = swap_handler.swap(
            token_address,
            JUPITER_TOKENS['SOL'],
            amount_to_sell,
            slippage_bps,
            simulate=False
        )

        return success

    except Exception as e:
        logger.error(f"Error executing limit sell: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(monitor_limit_orders())
```

### Running the Monitor

1. **Option 1: Separate Process**
   ```bash
   python order_monitor.py &
   ```

2. **Option 2: Docker Container**
   Create a separate container for the order monitor

3. **Option 3: systemd Service**
   Create a systemd service for automatic startup

4. **Option 4: Cloud Function**
   Deploy as AWS Lambda, Google Cloud Function, etc. triggered every minute

## Button Handler Routing

The following button handlers are implemented in `bot_modular.py`:

```python
# Limit order menu
elif action.startswith('limit_menu_'):
    token_address = action.replace('limit_menu_', '')
    await self.show_limit_order_menu(query, user_id, token_address)

# Set price target
elif action.startswith('limit_price_'):
    token_address = action.replace('limit_price_', '')
    await self.ask_limit_price_target(query, user_id, token_address)

# Set market cap target
elif action.startswith('limit_mcap_'):
    token_address = action.replace('limit_mcap_', '')
    await self.ask_limit_mcap_target(query, user_id, token_address)

# Create limit order
elif action.startswith('limit_create_'):
    parts = action.replace('limit_create_', '').split('_')
    order_type = parts[0]  # 'price' or 'market_cap'
    trigger_value = float(parts[1])
    sell_percentage = float(parts[2])
    token_address = '_'.join(parts[3:])
    await self.create_limit_order(query, user_id, order_type, trigger_value, sell_percentage, token_address)

# View limit orders
elif action.startswith('limit_view_'):
    token_address = action.replace('limit_view_', '')
    await self.view_limit_orders(query, user_id, token_address)

# Cancel limit order
elif action.startswith('limit_cancel_'):
    order_id = action.replace('limit_cancel_', '')
    await self.cancel_limit_order(query, user_id, order_id)
```

## Message Input Handling

Users can input price/market cap targets via text messages:

```python
# In handle_message method

# Limit price target input
if input_type == 'limit_price_target':
    try:
        price_target = float(message_text)
        token_address = input_data['token_address']

        # Show sell percentage selection
        await self.ask_limit_sell_percentage(
            update, user_id, token_address, 'price', price_target
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid price. Please enter a number.")

# Limit market cap target input
elif input_type == 'limit_mcap_target':
    try:
        # Parse market cap (supports K, M suffixes)
        mcap_text = message_text.upper().strip()
        if mcap_text.endswith('K'):
            mcap_target = float(mcap_text[:-1]) * 1_000
        elif mcap_text.endswith('M'):
            mcap_target = float(mcap_text[:-1]) * 1_000_000
        else:
            mcap_target = float(mcap_text)

        token_address = input_data['token_address']

        # Show sell percentage selection
        await self.ask_limit_sell_percentage(
            update, user_id, token_address, 'market_cap', mcap_target
        )
    except ValueError:
        await update.message.reply_text("❌ Invalid market cap. Use format: 500K, 1.5M, or 1500000")
```

## Data Storage

Limit orders are stored in `wallets/limit_orders.json`:

```json
{
  "123456789": [
    {
      "order_id": "limit_123456789_So11111_1702345678",
      "user_id": 123456789,
      "token_address": "So11111qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqo",
      "token_symbol": "SOL",
      "chain": "solana",
      "order_type": "price",
      "trigger_value": 0.001,
      "sell_percentage": 50,
      "status": "active",
      "created_at": "2025-12-13T08:30:00",
      "executed_at": null,
      "execution_price": null,
      "execution_market_cap": null,
      "error": null
    }
  ]
}
```

## Testing

1. **Create a test order:**
   - Scan a Solana token
   - Click "⏰ Limit Orders"
   - Set a price target above current price
   - Select sell percentage
   - Verify order is created

2. **View orders:**
   - Click "📋 View Active Orders"
   - Verify your order is listed

3. **Cancel order:**
   - Click "❌ Cancel [Token] Order"
   - Verify order is cancelled

4. **Monitor execution (manual):**
   - Create order with low trigger (easy to hit)
   - Manually check if conditions are met
   - Test the execution flow

## Security Considerations

1. **Private Keys**: Order monitor needs access to private keys - ensure secure storage
2. **Rate Limiting**: Don't check too frequently to avoid API rate limits
3. **Error Handling**: Implement robust error handling for failed swaps
4. **Notifications**: Always notify users of execution success/failure
5. **Audit Log**: Keep logs of all order executions

## Future Enhancements

- [ ] Take-profit + stop-loss combined orders
- [ ] Trailing stop-loss (sell if price drops X% from peak)
- [ ] Buy limit orders (buy when price drops to target)
- [ ] Multi-tier limit orders (sell 25% at $0.01, 25% at $0.02, etc.)
- [ ] Time-based orders (execute at specific time)
- [ ] Web dashboard for order management

## Troubleshooting

**Orders not executing:**
- Ensure order monitor is running
- Check RPC connection
- Verify token has sufficient liquidity
- Check slippage settings

**Orders failing:**
- Insufficient balance
- Token balance changed
- High slippage / price impact
- RPC errors

**Performance:**
- Reduce check interval if hitting rate limits
- Use WebSocket connections for real-time prices
- Implement caching for frequently checked tokens

---

## Summary

The limit order system is now fully implemented with:
✅ Order creation UI
✅ Price-based triggers
✅ Market cap-based triggers
✅ Order storage and management
✅ View and cancel functionality
✅ Integration with trading bot

⚠️ **Next Step**: Implement the order monitoring script to enable automatic execution!
