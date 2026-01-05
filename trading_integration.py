"""
Trading Integration Module for Telegram Bot
Multi-chain swap integration (Jupiter for Solana, 1inch for BSC)
"""

import logging
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from jupiter_swap import JupiterSwap, TOKENS as JUPITER_TOKENS, sol_to_lamports, MIN_SOL_RESERVE
from bsc_swap import BSCSwap, TOKENS as BSC_TOKENS, bnb_to_wei

logger = logging.getLogger(__name__)


class TradingMixin:
    """Mixin class to add trading functionality to TradingBot"""

    async def execute_buy(self, query, user_id: int, sol_amount: float, token_address: str):
        """Execute a token buy using chain-specific swap"""
        try:
            logger.info(f"execute_buy called: user_id={user_id}, sol_amount={sol_amount}, token_address={token_address}")

            if user_id not in self.trading_context:
                await query.edit_message_text("❌ Trading session expired. Please scan the token again.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
                return

            context = self.trading_context[user_id]
            token_symbol = context.get('token_symbol', 'TOKEN')
            chain = context.get('chain', 'solana').lower()
            slippage_bps = int(context.get('slippage_pct', 10) * 100)

            user_data = self.get_user_wallet_data(user_id)
            if not user_data:
                await query.edit_message_text("❌ No wallet found! Please create one first.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
                return

            primary_wallet = user_data.get('primary_wallet', 'wallet1')
            primary_slot = user_data['wallet_slots'].get(primary_wallet, {})
            chains = primary_slot.get('chains', {})

            logger.info(f"Wallet data structure: primary_wallet={primary_wallet}, has_chains={'SOL' in chains}")

            # Route to appropriate chain handler
            if chain == 'solana':
                await self._execute_buy_solana(query, user_id, sol_amount, token_address, token_symbol, slippage_bps, chains)
            elif chain == 'bsc':
                await self._execute_buy_bsc(query, user_id, sol_amount, token_address, token_symbol, slippage_bps, chains)
            else:
                await query.edit_message_text(f"❌ Trading not yet supported on {chain.upper()}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))

        except Exception as e:
            logger.error(f"Error in execute_buy: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))

    async def _execute_buy_solana(self, query, user_id: int, sol_amount: float, token_address: str, token_symbol: str, slippage_bps: int, chains: dict):
        """Execute Solana token buy using Jupiter"""
        if 'SOL' not in chains:
            await query.edit_message_text("❌ No Solana wallet found! Please create one first.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        sol_wallet = chains['SOL']
        private_key = sol_wallet.get('private_key')

        # Validate private key before using it
        if not private_key or not isinstance(private_key, str):
            logger.error(f"Invalid private key retrieved: type={type(private_key)}, value={private_key}")
            await query.edit_message_text(
                f"❌ <b>Wallet Error</b>\n\n"
                f"Failed to retrieve valid private key from wallet.\n"
                f"Please contact support or try recreating your wallet.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        if len(private_key) < 32:
            logger.error(f"Private key too short: length={len(private_key)}, preview={private_key[:10]}...")
            await query.edit_message_text(
                f"❌ <b>Wallet Error</b>\n\n"
                f"Private key format is invalid.\n"
                f"Please contact support or try recreating your wallet.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        logger.info(f"Retrieved private key: length={len(private_key)}, starts_with={private_key[:8]}...")

        await query.edit_message_text(f"🔄 Processing buy order...\n\n💰 Amount: {sol_amount} SOL\n🪙 Token: {token_symbol}\n⚙️ Slippage: {slippage_bps/100}%\n\n⏳ Checking balance...")

        # Initialize swap handler and check balance
        swap_handler = JupiterSwap(private_key)
        sol_balance = swap_handler.get_sol_balance()

        if sol_balance is None:
            await query.edit_message_text("❌ Failed to fetch wallet balance. Please try again.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        balance_sol = sol_balance / 1e9
        user_requested_lamports = sol_to_lamports(sol_amount)

        # Calculate absolute maximum we can swap from current balance
        absolute_max_swappable = sol_balance - MIN_SOL_RESERVE

        # Check if user has enough balance
        if sol_balance < user_requested_lamports:
            await query.edit_message_text(
                f"❌ <b>Insufficient Balance</b>\n\n"
                f"💰 Your balance: <b>{balance_sol:.9f} SOL</b>\n"
                f"💸 You requested: <b>{sol_amount} SOL</b>\n\n"
                f"Please add more SOL to your wallet.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        # Ensure we have enough to do any swap at all
        if absolute_max_swappable <= 1_000_000:  # Less than 0.001 SOL
            await query.edit_message_text(
                f"❌ <b>Balance Too Low</b>\n\n"
                f"💰 Your balance: <b>{balance_sol:.9f} SOL</b>\n\n"
                f"After reserving {MIN_SOL_RESERVE/1e9:.3f} SOL for fees and rent, "
                f"there's not enough left to swap.\n\n"
                f"Minimum balance needed: <b>0.004 SOL</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        # Calculate how much we'll actually swap
        actual_swap_amount = min(user_requested_lamports - MIN_SOL_RESERVE, absolute_max_swappable)

        # Final safety check
        if actual_swap_amount <= 0:
            await query.edit_message_text(
                f"❌ <b>Amount Too Small</b>\n\n"
                f"After reserving {MIN_SOL_RESERVE/1e9:.3f} SOL for fees and rent, "
                f"there's nothing left to swap from {sol_amount} SOL.\n\n"
                f"Please try a larger amount (min 0.004 SOL).",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        actual_swap_sol = actual_swap_amount / 1e9
        reserve_sol = MIN_SOL_RESERVE / 1e9

        await query.edit_message_text(
            f"🔄 Processing buy order...\n\n"
            f"💰 Input: {sol_amount} SOL\n"
            f"📊 Swapping: ~{actual_swap_sol:.6f} SOL\n"
            f"🔒 Reserved: {reserve_sol:.3f} SOL (fees)\n"
            f"🪙 Token: {token_symbol}\n"
            f"⚙️ Slippage: {slippage_bps/100}%\n\n"
            f"⏳ Getting quote...")

        quote = swap_handler.get_quote(JUPITER_TOKENS['SOL'], token_address, actual_swap_amount, slippage_bps)

        if not quote:
            await query.edit_message_text("❌ Failed to get quote from Jupiter. Token may have low liquidity.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        in_amount = int(quote['inAmount']) / 1e9
        out_amount = int(quote['outAmount']) / 1e6
        price_impact = float(quote.get('priceImpactPct', 0))

        keyboard = [[InlineKeyboardButton("✅ Confirm Buy", callback_data=f'confirm_buy_{sol_amount}_{token_address}')],
                    [InlineKeyboardButton("❌ Cancel", callback_data=f'refresh_{token_address}')]]

        await query.edit_message_text(
            f"📊 <b>Buy Order Quote</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 <b>Using: {sol_amount} SOL</b>\n"
            f"   ├─ Swap: {in_amount:.6f} SOL\n"
            f"   └─ Reserved: {reserve_sol:.3f} SOL\n\n"
            f"🪙 You Receive: <b>~{out_amount:,.2f} {token_symbol}</b>\n"
            f"📊 Price Impact: <b>{price_impact:.4f}%</b>\n"
            f"⚙️ Slippage: <b>{slippage_bps/100}%</b>\n\n"
            f"ℹ️ Reserved amount covers transaction fees and rent.\n\n"
            f"⚠️ <b>Confirm this transaction?</b>",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

        self.trading_context[user_id]['pending_quote'] = quote
        self.trading_context[user_id]['pending_amount'] = sol_amount
        self.trading_context[user_id]['actual_swap_amount'] = actual_swap_amount

    async def _execute_buy_bsc(self, query, user_id: int, bnb_amount: float, token_address: str, token_symbol: str, slippage_bps: int, chains: dict):
        """Execute BSC token buy using 1inch"""
        if 'BSC' not in chains:
            await query.edit_message_text("❌ No BSC wallet found! Please create one first.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        bsc_wallet = chains['BSC']
        private_key = bsc_wallet.get('private_key')

        # Convert slippage from basis points to percentage
        slippage_pct = slippage_bps / 100

        await query.edit_message_text(f"🔄 Processing buy order...\n\n💰 Amount: {bnb_amount} BNB\n🪙 Token: {token_symbol}\n⚙️ Slippage: {slippage_pct}%\n\n⏳ Getting quote...")

        swap_handler = BSCSwap(private_key)
        quote = swap_handler.get_quote(BSC_TOKENS['BNB'], token_address, bnb_to_wei(bnb_amount), slippage_pct)

        if not quote:
            await query.edit_message_text("❌ Failed to get quote from 1inch. Token may have low liquidity.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))
            return

        from_amount = int(quote.get('fromTokenAmount', 0)) / 1e18
        to_amount = int(quote.get('toTokenAmount', 0)) / 1e18

        keyboard = [[InlineKeyboardButton("✅ Confirm Buy", callback_data=f'confirm_buy_{bnb_amount}_{token_address}')],
                    [InlineKeyboardButton("❌ Cancel", callback_data=f'refresh_{token_address}')]]

        await query.edit_message_text(
            f"📊 <b>Buy Order Quote</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 You Pay: <b>{from_amount:.6f} BNB</b>\n"
            f"🪙 You Receive: <b>~{to_amount:,.2f} {token_symbol}</b>\n"
            f"⚙️ Slippage: <b>{slippage_pct}%</b>\n\n⚠️ <b>Confirm this transaction?</b>",
            parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

        self.trading_context[user_id]['pending_quote'] = quote
        self.trading_context[user_id]['pending_amount'] = bnb_amount

    async def confirm_buy(self, query, user_id: int, sol_amount: float, token_address: str):
        """Confirm and execute the buy order"""
        try:
            if user_id not in self.trading_context or 'pending_quote' not in self.trading_context[user_id]:
                await query.edit_message_text("❌ Quote expired. Please try again.")
                return

            context = self.trading_context[user_id]
            token_symbol = context.get('token_symbol', 'TOKEN')
            chain = context.get('chain', 'solana').lower()

            # Route to appropriate chain handler
            if chain == 'solana':
                await self._confirm_buy_solana(query, user_id, sol_amount, token_address, token_symbol, context)
            elif chain == 'bsc':
                await self._confirm_buy_bsc(query, user_id, sol_amount, token_address, token_symbol, context)
            else:
                await query.edit_message_text(f"❌ Trading not yet supported on {chain.upper()}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))

        except Exception as e:
            logger.error(f"Error in confirm_buy: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error executing buy: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))

    async def _confirm_buy_solana(self, query, user_id: int, sol_amount: float, token_address: str, token_symbol: str, context: dict):
        """Confirm and execute Solana buy"""
        actual_swap_amount = context.get('actual_swap_amount')

        if actual_swap_amount is None:
            await query.edit_message_text("❌ Quote expired. Please try again.")
            return

        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        private_key = user_data['wallet_slots'][primary_wallet]['chains']['SOL']['private_key']

        swap_sol = actual_swap_amount / 1e9
        await query.edit_message_text(
            f"⏳ <b>Executing Swap...</b>\n\n"
            f"💰 Using: {sol_amount} SOL\n"
            f"📊 Swapping: {swap_sol:.6f} SOL\n"
            f"🪙 Token: {token_symbol}\n\n"
            f"⏳ Please wait...",
            parse_mode='HTML')

        swap_handler = JupiterSwap(private_key)
        slippage_bps = int(context.get('slippage_pct', 10) * 100)

        success = swap_handler.swap(JUPITER_TOKENS['SOL'], token_address, actual_swap_amount, slippage_bps, simulate=False)

        if success:
            order = {'order_id': f"order_{user_id}_{int(datetime.datetime.now().timestamp())}", 'token_address': token_address,
                     'token_symbol': token_symbol, 'amount_sol': sol_amount, 'status': 'completed',
                     'timestamp': datetime.datetime.now().isoformat()}

            if user_id not in self.user_orders:
                self.user_orders[user_id] = []
            self.user_orders[user_id].append(order)

            await query.edit_message_text(
                f"✅ <b>Buy Order Completed!</b>\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Spent: <b>{sol_amount} SOL</b>\n🪙 Token: <b>{token_symbol}</b>\n📋 Status: <b>Success</b>\n\n🔍 Check your transaction on Solscan",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh Token", callback_data=f'refresh_{token_address}')],
                    [InlineKeyboardButton("📋 View Orders", callback_data=f'orders_{token_address}')],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]))
        else:
            await query.edit_message_text("❌ <b>Buy Order Failed</b>\n\nThe swap transaction failed. Please try again.",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]]))

    async def _confirm_buy_bsc(self, query, user_id: int, bnb_amount: float, token_address: str, token_symbol: str, context: dict):
        """Confirm and execute BSC buy"""
        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        private_key = user_data['wallet_slots'][primary_wallet]['chains']['BSC']['private_key']

        await query.edit_message_text(f"⏳ <b>Executing Swap...</b>\n\n💰 Amount: {bnb_amount} BNB\n🪙 Token: {token_symbol}\n\n⏳ Please wait...", parse_mode='HTML')

        swap_handler = BSCSwap(private_key)
        slippage_pct = context.get('slippage_pct', 10)

        success = swap_handler.swap(BSC_TOKENS['BNB'], token_address, bnb_to_wei(bnb_amount), slippage_pct, simulate=False)

        if success:
            order = {'order_id': f"order_{user_id}_{int(datetime.datetime.now().timestamp())}", 'token_address': token_address,
                     'token_symbol': token_symbol, 'amount_sol': bnb_amount, 'status': 'completed',
                     'timestamp': datetime.datetime.now().isoformat()}

            if user_id not in self.user_orders:
                self.user_orders[user_id] = []
            self.user_orders[user_id].append(order)

            await query.edit_message_text(
                f"✅ <b>Buy Order Completed!</b>\n━━━━━━━━━━━━━━━━━━━━\n\n💰 Spent: <b>{bnb_amount} BNB</b>\n🪙 Token: <b>{token_symbol}</b>\n📋 Status: <b>Success</b>\n\n🔍 Check your transaction on BscScan",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh Token", callback_data=f'refresh_{token_address}')],
                    [InlineKeyboardButton("📋 View Orders", callback_data=f'orders_{token_address}')],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]))
        else:
            await query.edit_message_text("❌ <b>Buy Order Failed</b>\n\nThe swap transaction failed. Please try again.",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]]))

    async def show_slippage_menu(self, query, user_id: int, token_address: str):
        """Show slippage configuration menu"""
        try:
            context = self.trading_context.get(user_id, {})
            current_slippage = context.get('slippage_pct', 10)
            token_symbol = context.get('token_symbol', 'TOKEN')

            keyboard = [
                [InlineKeyboardButton(f"{'✓ ' if current_slippage == 10 else ''}Auto (10%)", callback_data=f'set_slippage_10_{token_address}')],
                [InlineKeyboardButton(f"{'✓ ' if current_slippage == 0.5 else ''}0.5%", callback_data=f'set_slippage_0.5_{token_address}')],
                [InlineKeyboardButton(f"{'✓ ' if current_slippage == 1 else ''}1%", callback_data=f'set_slippage_1_{token_address}')],
                [InlineKeyboardButton(f"{'✓ ' if current_slippage == 3 else ''}3%", callback_data=f'set_slippage_3_{token_address}')],
                [InlineKeyboardButton(f"{'✓ ' if current_slippage == 5 else ''}5%", callback_data=f'set_slippage_5_{token_address}')],
                [InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]]

            await query.edit_message_text(f"⚙️ <b>Slippage Settings</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🪙 Token: <b>{token_symbol}</b>\n📊 Current: <b>{current_slippage}%</b>\n\nSelect slippage tolerance:",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Error in show_slippage_menu: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def set_slippage(self, query, user_id: int, slippage_pct: float, token_address: str):
        """Set slippage tolerance"""
        try:
            if user_id in self.trading_context:
                self.trading_context[user_id]['slippage_pct'] = slippage_pct
                await query.answer(f"Slippage set to {slippage_pct}%")
                fake_update = Update(update_id=0, message=query.message)
                fake_update._effective_user = query.from_user
                await self.display_token_info(fake_update, None, token_address)
        except Exception as e:
            logger.error(f"Error in set_slippage: {e}")
            await query.answer("❌ Error setting slippage")

    async def show_orders(self, query, user_id: int, token_address: str):
        """Show user's orders for this token"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')

            orders = self.user_orders.get(user_id, [])
            token_orders = [o for o in orders if o.get('token_address') == token_address]

            message = f"📋 <b>Orders for {token_symbol}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

            if not token_orders:
                message += "No orders yet for this token.\n"
            else:
                for idx, order in enumerate(token_orders[-10:], 1):
                    status_emoji = "✅" if order['status'] == 'completed' else "⏳"
                    message += f"{status_emoji} <b>Order #{idx}</b>\n💰 Amount: {order['amount_sol']} SOL\n📅 {order['timestamp'][:16]}\nStatus: {order['status']}\n\n"

            keyboard = [[InlineKeyboardButton("🔄 Refresh Orders", callback_data=f'orders_{token_address}')],
                        [InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]]

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            logger.error(f"Error in show_orders: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def ask_custom_amount(self, query, user_id: int, token_address: str):
        """Ask user for custom SOL amount"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')

            self.waiting_for_input[user_id] = {'type': 'buy_custom_amount', 'token_address': token_address, 'message_id': query.message.message_id}

            await query.edit_message_text(f"💵 <b>Custom Buy Amount</b>\n━━━━━━━━━━━━━━━━━━━━\n\n🪙 Token: <b>{token_symbol}</b>\n\nEnter the amount of SOL you want to spend:\n(e.g., 0.1, 0.5, 2)",
                parse_mode='HTML', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f'refresh_{token_address}')]]))
        except Exception as e:
            logger.error(f"Error in ask_custom_amount: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def show_bags(self, query, user_id: int):
        """Show all tokens bought by the user (their bags)"""
        try:
            orders = self.user_orders.get(user_id, [])

            if not orders:
                message = "🎒 <b>Your Bags</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
                message += "You haven't bought any tokens yet!\n\n"
                message += "Send a token contract address to start trading."

                keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
                await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))
                return

            # Group orders by token
            tokens = {}
            for order in orders:
                if order['status'] == 'completed':
                    token_addr = order['token_address']
                    if token_addr not in tokens:
                        tokens[token_addr] = {
                            'symbol': order['token_symbol'],
                            'total_sol_spent': 0,
                            'buy_count': 0,
                            'first_buy': order['timestamp']
                        }
                    tokens[token_addr]['total_sol_spent'] += order['amount_sol']
                    tokens[token_addr]['buy_count'] += 1

            message = "🎒 <b>Your Bags</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"<b>Total Tokens:</b> {len(tokens)}\n\n"

            keyboard = []
            for idx, (token_addr, data) in enumerate(tokens.items(), 1):
                symbol = data['symbol']
                total_spent = data['total_sol_spent']
                count = data['buy_count']

                message += f"<b>{idx}. {symbol}</b>\n"
                message += f"   💰 Spent: {total_spent:.4f} SOL\n"
                message += f"   📊 Buys: {count}\n"
                message += f"   📅 First: {data['first_buy'][:10]}\n\n"

                # Add buttons for this token: View, Buy More, Sell
                keyboard.append([
                    InlineKeyboardButton(f"📊 {symbol}", callback_data=f'refresh_{token_addr}'),
                    InlineKeyboardButton(f"💰 Buy", callback_data=f'bag_buy_{token_addr}'),
                    InlineKeyboardButton(f"💸 Sell", callback_data=f'bag_sell_{token_addr}')
                ])

            keyboard.append([
                InlineKeyboardButton("🔄 Refresh Bags", callback_data='view_bags'),
                InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')
            ])

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            logger.error(f"Error in show_bags: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]]))

    async def show_bag_buy_options(self, query, user_id: int, token_address: str):
        """Show buy options for a token from bags"""
        try:
            # Get token info from orders
            orders = self.user_orders.get(user_id, [])
            token_symbol = "TOKEN"
            for order in orders:
                if order['token_address'] == token_address:
                    token_symbol = order['token_symbol']
                    break

            keyboard = [
                [
                    InlineKeyboardButton("1 SOL 💵", callback_data=f'buy_1_{token_address}'),
                    InlineKeyboardButton("3 SOL 💵", callback_data=f'buy_3_{token_address}'),
                    InlineKeyboardButton("X SOL 💵", callback_data=f'buy_x_{token_address}')
                ],
                [InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]
            ]

            message = f"💰 <b>Buy More {token_symbol}</b>\n━━━━━━━━━━━━━━━━━━━━\n\nSelect amount to buy:"

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            logger.error(f"Error in show_bag_buy_options: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def show_bag_sell_options(self, query, user_id: int, token_address: str):
        """Show sell options for a token from bags"""
        try:
            # Get token info from orders
            orders = self.user_orders.get(user_id, [])
            token_symbol = "TOKEN"
            for order in orders:
                if order['token_address'] == token_address:
                    token_symbol = order['token_symbol']
                    break

            # Store in trading context for sell
            if user_id not in self.trading_context:
                self.trading_context[user_id] = {}

            self.trading_context[user_id].update({
                'token_address': token_address,
                'token_symbol': token_symbol,
                'sell_mode': True,
                'slippage_pct': 10
            })

            keyboard = [
                [
                    InlineKeyboardButton("25% 💸", callback_data=f'sell_25_{token_address}'),
                    InlineKeyboardButton("50% 💸", callback_data=f'sell_50_{token_address}')
                ],
                [
                    InlineKeyboardButton("75% 💸", callback_data=f'sell_75_{token_address}'),
                    InlineKeyboardButton("100% 💸", callback_data=f'sell_100_{token_address}')
                ],
                [InlineKeyboardButton("Custom Amount 💸", callback_data=f'sell_custom_{token_address}')],
                [InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]
            ]

            message = (
                f"💸 <b>Sell {token_symbol}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Select percentage to sell:\n"
                f"(This will swap your tokens back to SOL)"
            )

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            logger.error(f"Error in show_bag_sell_options: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def ask_custom_sell_amount(self, query, user_id: int, token_address: str):
        """Ask user for custom sell percentage"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')

            self.waiting_for_input[user_id] = {
                'type': 'sell_custom_amount',
                'token_address': token_address,
                'message_id': query.message.message_id
            }

            await query.edit_message_text(
                f"💸 <b>Custom Sell Amount</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 Token: <b>{token_symbol}</b>\n\n"
                f"Enter percentage to sell (1-100):\n"
                f"(e.g., 10, 25, 33, 80)",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data='view_bags')]])
            )
        except Exception as e:
            logger.error(f"Error in ask_custom_sell_amount: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def execute_sell(self, query, user_id: int, percentage: float, token_address: str):
        """Execute a token sell (reverse swap to native token)"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')
            chain = context.get('chain', 'solana').lower()
            slippage_bps = int(context.get('slippage_pct', 10) * 100)

            # Get wallet
            user_data = self.get_user_wallet_data(user_id)
            if not user_data:
                await query.edit_message_text("❌ No wallet found!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='view_bags')]]))
                return

            primary_wallet = user_data.get('primary_wallet', 'wallet1')
            primary_slot = user_data['wallet_slots'].get(primary_wallet, {})
            chains = primary_slot.get('chains', {})

            # Route to appropriate chain handler
            if chain == 'solana':
                await self._execute_sell_solana(query, user_id, percentage, token_address, token_symbol, slippage_bps, chains, context)
            elif chain == 'bsc':
                await self._execute_sell_bsc(query, user_id, percentage, token_address, token_symbol, slippage_bps, chains, context)
            else:
                await query.edit_message_text(f"❌ Selling not yet supported on {chain.upper()}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='view_bags')]]))

        except Exception as e:
            logger.error(f"Error in execute_sell: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='view_bags')]]))

    async def _execute_sell_solana(self, query, user_id: int, percentage: float, token_address: str, token_symbol: str, slippage_bps: int, chains: dict, context: dict):
        """Execute Solana token sell"""
        if 'SOL' not in chains:
            await query.edit_message_text("❌ No Solana wallet found!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='view_bags')]]))
            return

        sol_wallet = chains['SOL']
        private_key = sol_wallet.get('private_key')

        await query.edit_message_text(
            f"⏳ <b>Preparing Sell Order...</b>\n\n"
            f"💸 Selling {percentage}% of {token_symbol}\n"
            f"⚙️ Slippage: {slippage_bps/100}%\n\n"
            f"⏳ Checking balance...",
            parse_mode='HTML')

        # Get token balance from on-chain
        swap_handler = JupiterSwap(private_key)
        balance_info = swap_handler.get_token_balance(token_address)

        if not balance_info:
            await query.edit_message_text(
                f"❌ <b>Failed to Fetch Balance</b>\n\n"
                f"Could not retrieve your {token_symbol} balance.\n"
                f"Please check your RPC connection.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        token_balance = balance_info['balance']
        token_decimals = balance_info['decimals']
        ui_balance = balance_info['uiAmount']

        if token_balance == 0:
            await query.edit_message_text(
                f"❌ <b>No {token_symbol} Balance</b>\n\n"
                f"You don't have any {token_symbol} tokens to sell.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        # Calculate amount to sell based on percentage
        amount_to_sell = int(token_balance * (percentage / 100))

        if amount_to_sell == 0:
            await query.edit_message_text(
                f"❌ <b>Amount Too Small</b>\n\n"
                f"The calculated amount to sell is too small.\n"
                f"Your balance: {ui_balance:.6f} {token_symbol}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        # Get quote for selling (token → SOL)
        await query.edit_message_text(
            f"⏳ <b>Getting Quote...</b>\n\n"
            f"💰 Your Balance: {ui_balance:.6f} {token_symbol}\n"
            f"💸 Selling {percentage}%: {amount_to_sell / (10 ** token_decimals):.6f} {token_symbol}\n\n"
            f"⏳ Getting best price from Jupiter...",
            parse_mode='HTML')

        quote = swap_handler.get_quote(token_address, JUPITER_TOKENS['SOL'], amount_to_sell, slippage_bps)

        if not quote:
            await query.edit_message_text(
                f"❌ <b>Failed to Get Quote</b>\n\n"
                f"Could not get a quote from Jupiter.\n"
                f"Token may have low liquidity.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        in_amount = int(quote['inAmount']) / (10 ** token_decimals)
        out_amount = int(quote['outAmount']) / 1e9
        price_impact = float(quote.get('priceImpactPct', 0))

        # Show confirmation
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Sell", callback_data=f'confirm_sell_{percentage}_{token_address}')],
            [InlineKeyboardButton("❌ Cancel", callback_data='view_bags')]
        ]

        await query.edit_message_text(
            f"📊 <b>Sell Order Quote</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Your Balance: <b>{ui_balance:.6f} {token_symbol}</b>\n"
            f"💸 You Sell: <b>{in_amount:.6f} {token_symbol}</b> ({percentage}%)\n"
            f"🪙 You Receive: <b>~{out_amount:.9f} SOL</b>\n"
            f"📊 Price Impact: <b>{price_impact:.4f}%</b>\n"
            f"⚙️ Slippage: <b>{slippage_bps/100}%</b>\n\n"
            f"⚠️ <b>Confirm this transaction?</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Store quote for confirmation
        self.trading_context[user_id]['pending_sell_quote'] = quote
        self.trading_context[user_id]['pending_sell_amount'] = amount_to_sell
        self.trading_context[user_id]['pending_sell_percentage'] = percentage

    async def _execute_sell_bsc(self, query, user_id: int, percentage: float, token_address: str, token_symbol: str, slippage_bps: int, chains: dict, context: dict):
        """Execute BSC token sell"""
        if 'BSC' not in chains:
            await query.edit_message_text("❌ No BSC wallet found!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='view_bags')]]))
            return

        bsc_wallet = chains['BSC']
        private_key = bsc_wallet.get('private_key')
        slippage_pct = slippage_bps / 100

        await query.edit_message_text(
            f"⏳ <b>Preparing Sell Order...</b>\n\n"
            f"💸 Selling {percentage}% of {token_symbol}\n"
            f"⚙️ Slippage: {slippage_pct}%\n\n"
            f"⏳ Checking balance..."
        , parse_mode='HTML')

        # Get token balance from on-chain
        swap_handler = BSCSwap(private_key)
        balance_info = swap_handler.get_token_balance(token_address)

        if not balance_info:
            await query.edit_message_text(
                f"❌ <b>Failed to Fetch Balance</b>\n\n"
                f"Could not retrieve your {token_symbol} balance.\n"
                f"Please check your RPC connection.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        token_balance = balance_info['balance']
        token_decimals = balance_info['decimals']
        ui_balance = balance_info['uiAmount']

        if token_balance == 0:
            await query.edit_message_text(
                f"❌ <b>No {token_symbol} Balance</b>\n\n"
                f"You don't have any {token_symbol} tokens to sell.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        # Calculate amount to sell based on percentage
        amount_to_sell = int(token_balance * (percentage / 100))

        if amount_to_sell == 0:
            await query.edit_message_text(
                f"❌ <b>Amount Too Small</b>\n\n"
                f"The calculated amount to sell is too small.\n"
                f"Your balance: {ui_balance:.6f} {token_symbol}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        # Get quote for selling (token → BNB)
        await query.edit_message_text(
            f"⏳ <b>Getting Quote...</b>\n\n"
            f"💰 Your Balance: {ui_balance:.6f} {token_symbol}\n"
            f"💸 Selling {percentage}%: {amount_to_sell / (10 ** token_decimals):.6f} {token_symbol}\n\n"
            f"⏳ Getting best price from 1inch..."
        , parse_mode='HTML')

        quote = swap_handler.get_quote(token_address, BSC_TOKENS['BNB'], amount_to_sell, slippage_pct)

        if not quote:
            await query.edit_message_text(
                f"❌ <b>Failed to Get Quote</b>\n\n"
                f"Could not get a quote from 1inch.\n"
                f"Token may have low liquidity.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )
            return

        from_amount = int(quote.get('fromTokenAmount', 0)) / (10 ** token_decimals)
        to_amount = int(quote.get('toTokenAmount', 0)) / 1e18

        # Show confirmation
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Sell", callback_data=f'confirm_sell_{percentage}_{token_address}')],
            [InlineKeyboardButton("❌ Cancel", callback_data='view_bags')]
        ]

        await query.edit_message_text(
            f"📊 <b>Sell Order Quote</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💰 Your Balance: <b>{ui_balance:.6f} {token_symbol}</b>\n"
            f"💸 You Sell: <b>{from_amount:.6f} {token_symbol}</b> ({percentage}%)\n"
            f"🪙 You Receive: <b>~{to_amount:.6f} BNB</b>\n"
            f"⚙️ Slippage: <b>{slippage_pct}%</b>\n\n"
            f"⚠️ <b>Confirm this transaction?</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        # Store quote for confirmation
        self.trading_context[user_id]['pending_sell_quote'] = quote
        self.trading_context[user_id]['pending_sell_amount'] = amount_to_sell
        self.trading_context[user_id]['pending_sell_percentage'] = percentage

    async def confirm_sell(self, query, user_id: int, percentage: float, token_address: str):
        """Confirm and execute the sell order"""
        try:
            if user_id not in self.trading_context or 'pending_sell_quote' not in self.trading_context[user_id]:
                await query.edit_message_text(
                    "❌ Quote expired. Please try again.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
                )
                return

            context = self.trading_context[user_id]
            token_symbol = context.get('token_symbol', 'TOKEN')
            chain = context.get('chain', 'solana').lower()

            # Route to appropriate chain handler
            if chain == 'solana':
                await self._confirm_sell_solana(query, user_id, percentage, token_address, token_symbol, context)
            elif chain == 'bsc':
                await self._confirm_sell_bsc(query, user_id, percentage, token_address, token_symbol, context)
            else:
                await query.edit_message_text(f"❌ Selling not yet supported on {chain.upper()}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]]))

        except Exception as e:
            logger.error(f"Error in confirm_sell: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]]))

    async def _confirm_sell_solana(self, query, user_id: int, percentage: float, token_address: str, token_symbol: str, context: dict):
        """Confirm and execute Solana sell"""
        amount_to_sell = context.get('pending_sell_amount')

        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        private_key = user_data['wallet_slots'][primary_wallet]['chains']['SOL']['private_key']

        await query.edit_message_text(
            f"⏳ <b>Executing Sell...</b>\n\n"
            f"💸 Selling {percentage}% of {token_symbol}\n\n"
            f"⏳ Please wait...",
            parse_mode='HTML'
        )

        swap_handler = JupiterSwap(private_key)
        slippage_bps = int(context.get('slippage_pct', 10) * 100)

        # Execute reverse swap (token → SOL)
        success = swap_handler.swap(token_address, JUPITER_TOKENS['SOL'], amount_to_sell, slippage_bps, simulate=False)

        if success:
            await query.edit_message_text(
                f"✅ <b>Sell Order Completed!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💸 Sold: <b>{percentage}% of {token_symbol}</b>\n"
                f"🪙 Received: <b>SOL</b>\n"
                f"📋 Status: <b>Success</b>\n\n"
                f"🔍 Check your transaction on Solscan",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎒 View Bags", callback_data='view_bags')],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
                ])
            )
        else:
            await query.edit_message_text(
                f"❌ <b>Sell Order Failed</b>\n\n"
                f"The swap transaction failed. Please try again.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )

    async def _confirm_sell_bsc(self, query, user_id: int, percentage: float, token_address: str, token_symbol: str, context: dict):
        """Confirm and execute BSC sell"""
        amount_to_sell = context.get('pending_sell_amount')

        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        private_key = user_data['wallet_slots'][primary_wallet]['chains']['BSC']['private_key']

        await query.edit_message_text(
            f"⏳ <b>Executing Sell...</b>\n\n"
            f"💸 Selling {percentage}% of {token_symbol}\n\n"
            f"⏳ Please wait...",
            parse_mode='HTML'
        )

        swap_handler = BSCSwap(private_key)
        slippage_pct = context.get('slippage_pct', 10)

        # Execute reverse swap (token → BNB)
        success = swap_handler.swap(token_address, BSC_TOKENS['BNB'], amount_to_sell, slippage_pct, simulate=False)

        if success:
            await query.edit_message_text(
                f"✅ <b>Sell Order Completed!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💸 Sold: <b>{percentage}% of {token_symbol}</b>\n"
                f"🪙 Received: <b>BNB</b>\n"
                f"📋 Status: <b>Success</b>\n\n"
                f"🔍 Check your transaction on BscScan",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎒 View Bags", callback_data='view_bags')],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
                ])
            )
        else:
            await query.edit_message_text(
                f"❌ <b>Sell Order Failed</b>\n\n"
                f"The swap transaction failed. Please try again.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')]])
            )

    # ============================================================
    # LIMIT SELL ORDERS
    # ============================================================

    async def show_limit_order_menu(self, query, user_id: int, token_address: str):
        """Show limit order creation menu"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')
            current_price = context.get('price_usd', 0)

            # Get current market cap from context or fetch it
            current_market_cap = context.get('market_cap', 0)

            keyboard = [
                [InlineKeyboardButton("💰 Set Price Target", callback_data=f'limit_price_{token_address}')],
                [InlineKeyboardButton("📊 Set Market Cap Target", callback_data=f'limit_mcap_{token_address}')],
                [InlineKeyboardButton("📋 View Active Orders", callback_data=f'limit_view_{token_address}')],
                [InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]
            ]

            message = (
                f"⚙️ <b>Limit Sell Orders</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 <b>Token:</b> {token_symbol}\n"
                f"💹 <b>Current Price:</b> ${current_price:.10f}\n"
            )

            if current_market_cap > 0:
                if current_market_cap >= 1_000_000:
                    mcap_display = f"${current_market_cap/1_000_000:.2f}M"
                elif current_market_cap >= 1_000:
                    mcap_display = f"${current_market_cap/1_000:.2f}K"
                else:
                    mcap_display = f"${current_market_cap:.2f}"
                message += f"📊 <b>Market Cap:</b> {mcap_display}\n"

            message += (
                f"\n<b>What would you like to do?</b>\n\n"
                f"• Set a price target to auto-sell when reached\n"
                f"• Set a market cap target to auto-sell when reached\n"
                f"• View and manage your active limit orders"
            )

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in show_limit_order_menu: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def ask_limit_price_target(self, query, user_id: int, token_address: str):
        """Ask user for price target"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')
            current_price = context.get('price_usd', 0)

            self.waiting_for_input[user_id] = {
                'type': 'limit_price_target',
                'token_address': token_address,
                'message_id': query.message.message_id
            }

            message = (
                f"💰 <b>Set Price Target</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 <b>Token:</b> {token_symbol}\n"
                f"💹 <b>Current Price:</b> ${current_price:.10f}\n\n"
                f"Enter your target price in USD:\n"
                f"(e.g., 0.0001, 0.01, 1.5)\n\n"
                f"When the token reaches this price,\n"
                f"you'll be asked for the sell percentage."
            )

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data=f'limit_menu_{token_address}')
                ]])
            )

        except Exception as e:
            logger.error(f"Error in ask_limit_price_target: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def ask_limit_mcap_target(self, query, user_id: int, token_address: str):
        """Ask user for market cap target"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')
            current_market_cap = context.get('market_cap', 0)

            if current_market_cap >= 1_000_000:
                mcap_display = f"${current_market_cap/1_000_000:.2f}M"
            elif current_market_cap >= 1_000:
                mcap_display = f"${current_market_cap/1_000:.2f}K"
            else:
                mcap_display = f"${current_market_cap:.2f}"

            self.waiting_for_input[user_id] = {
                'type': 'limit_mcap_target',
                'token_address': token_address,
                'message_id': query.message.message_id
            }

            message = (
                f"📊 <b>Set Market Cap Target</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 <b>Token:</b> {token_symbol}\n"
                f"📊 <b>Current MCap:</b> {mcap_display}\n\n"
                f"Enter your target market cap in USD:\n"
                f"• Use K for thousands (e.g., 500K)\n"
                f"• Use M for millions (e.g., 1.5M, 10M)\n"
                f"• Or enter full number (e.g., 1500000)\n\n"
                f"When the token reaches this market cap,\n"
                f"you'll be asked for the sell percentage."
            )

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancel", callback_data=f'limit_menu_{token_address}')
                ]])
            )

        except Exception as e:
            logger.error(f"Error in ask_limit_mcap_target: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def ask_limit_sell_percentage(self, query, user_id: int, token_address: str, order_type: str, trigger_value: float):
        """Ask user for sell percentage for limit order"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')

            if order_type == 'price':
                trigger_str = f"${trigger_value:.10f}"
                condition_text = f"price reaches {trigger_str}"
            else:  # market_cap
                if trigger_value >= 1_000_000:
                    trigger_str = f"${trigger_value/1_000_000:.2f}M"
                elif trigger_value >= 1_000:
                    trigger_str = f"${trigger_value/1_000:.2f}K"
                else:
                    trigger_str = f"${trigger_value:.2f}"
                condition_text = f"market cap reaches {trigger_str}"

            # Show quick percentage buttons
            keyboard = [
                [
                    InlineKeyboardButton("25% 💸", callback_data=f'limit_create_{order_type}_{trigger_value}_25_{token_address}'),
                    InlineKeyboardButton("50% 💸", callback_data=f'limit_create_{order_type}_{trigger_value}_50_{token_address}')
                ],
                [
                    InlineKeyboardButton("75% 💸", callback_data=f'limit_create_{order_type}_{trigger_value}_75_{token_address}'),
                    InlineKeyboardButton("100% 💸", callback_data=f'limit_create_{order_type}_{trigger_value}_100_{token_address}')
                ],
                [InlineKeyboardButton("Custom % 💸", callback_data=f'limit_custom_{order_type}_{trigger_value}_{token_address}')],
                [InlineKeyboardButton("❌ Cancel", callback_data=f'limit_menu_{token_address}')]
            ]

            message = (
                f"💸 <b>Select Sell Percentage</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 <b>Token:</b> {token_symbol}\n"
                f"🎯 <b>Trigger:</b> When {condition_text}\n\n"
                f"<b>How much should we sell?</b>\n"
                f"Select percentage of your holdings to sell:"
            )

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in ask_limit_sell_percentage: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def create_limit_order(self, query, user_id: int, order_type: str, trigger_value: float, sell_percentage: float, token_address: str):
        """Create a limit sell order"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')
            chain = context.get('chain', 'solana')

            # Use the limit order service (needs to be initialized in bot)
            if not hasattr(self, 'limit_order_service'):
                await query.edit_message_text(
                    "❌ Limit order service not available",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')
                    ]])
                )
                return

            order = self.limit_order_service.create_limit_order(
                user_id=user_id,
                token_address=token_address,
                token_symbol=token_symbol,
                order_type=order_type,
                trigger_value=trigger_value,
                sell_percentage=sell_percentage,
                chain=chain
            )

            if order_type == 'price':
                trigger_str = f"${trigger_value:.10f}"
                condition_text = f"Price ≥ {trigger_str}"
            else:  # market_cap
                if trigger_value >= 1_000_000:
                    trigger_str = f"${trigger_value/1_000_000:.2f}M"
                elif trigger_value >= 1_000:
                    trigger_str = f"${trigger_value/1_000:.2f}K"
                else:
                    trigger_str = f"${trigger_value:.2f}"
                condition_text = f"Market Cap ≥ {trigger_str}"

            message = (
                f"✅ <b>Limit Order Created!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 <b>Token:</b> {token_symbol}\n"
                f"🎯 <b>Condition:</b> {condition_text}\n"
                f"💸 <b>Sell Amount:</b> {sell_percentage}%\n"
                f"📋 <b>Order ID:</b> <code>{order['order_id']}</code>\n\n"
                f"✨ Your order is now active!\n"
                f"We'll automatically sell when the condition is met.\n\n"
                f"💡 <i>Tip: Monitor your orders from the Limit Orders menu</i>"
            )

            keyboard = [
                [InlineKeyboardButton("📋 View Orders", callback_data=f'limit_view_{token_address}')],
                [InlineKeyboardButton("➕ Add Another", callback_data=f'limit_menu_{token_address}')],
                [InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]
            ]

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in create_limit_order: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error creating limit order: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data=f'limit_menu_{token_address}')
                ]])
            )

    async def view_limit_orders(self, query, user_id: int, token_address: str = None):
        """View active limit orders for a token or all tokens"""
        try:
            if not hasattr(self, 'limit_order_service'):
                await query.edit_message_text("❌ Limit order service not available")
                return

            if token_address:
                # Show orders for specific token
                orders = self.limit_order_service.get_active_orders_by_token(user_id, token_address)
                context = self.trading_context.get(user_id, {})
                token_symbol = context.get('token_symbol', 'TOKEN')
                title = f"Limit Orders for {token_symbol}"
                back_callback = f'limit_menu_{token_address}'
            else:
                # Show all orders
                orders = self.limit_order_service.get_user_orders(user_id, status='active')
                title = "All Active Limit Orders"
                back_callback = 'view_bags'

            message = f"📋 <b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

            if not orders:
                message += "No active limit orders.\n\n"
                message += "💡 Create a limit order to auto-sell at your target price or market cap!"
            else:
                for idx, order in enumerate(orders, 1):
                    summary = self.limit_order_service.get_order_summary(order)
                    created = order['created_at'][:16].replace('T', ' ')
                    message += f"<b>{idx}.</b> {summary}\n"
                    message += f"   📅 Created: {created}\n\n"

            keyboard = []

            # Add cancel buttons for each order
            if orders:
                for order in orders[:5]:  # Show up to 5 orders for cancellation
                    order_id = order['order_id']
                    symbol = order['token_symbol']
                    keyboard.append([
                        InlineKeyboardButton(
                            f"❌ Cancel {symbol} Order",
                            callback_data=f'limit_cancel_{order_id}'
                        )
                    ])

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=back_callback)])

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in view_limit_orders: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def cancel_limit_order(self, query, user_id: int, order_id: str):
        """Cancel a limit order"""
        try:
            if not hasattr(self, 'limit_order_service'):
                await query.edit_message_text("❌ Limit order service not available")
                return

            success = self.limit_order_service.cancel_order(user_id, order_id)

            if success:
                await query.answer("✅ Order cancelled", show_alert=False)
                # Refresh the orders view
                await self.view_limit_orders(query, user_id, token_address=None)
            else:
                await query.answer("❌ Failed to cancel order", show_alert=True)

        except Exception as e:
            logger.error(f"Error in cancel_limit_order: {e}", exc_info=True)
            await query.answer(f"❌ Error: {str(e)}", show_alert=True)
