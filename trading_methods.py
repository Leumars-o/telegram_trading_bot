"""
Trading methods for Telegram bot - Jupiter Swap Integration
These methods should be added to the TradingBot class
"""

# Add these methods to the TradingBot class before button_handler

    async def execute_buy(self, query, user_id: int, sol_amount: float, token_address: str):
        """Execute a token buy using Jupiter Swap"""
        try:
            # Get trading context
            if user_id not in self.trading_context:
                await query.edit_message_text(
                    "❌ Trading session expired. Please scan the token again.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return

            context = self.trading_context[user_id]
            token_symbol = context.get('token_symbol', 'TOKEN')
            chain = context.get('chain', 'solana')
            slippage_bps = context.get('slippage_pct', 10) * 100  # Convert % to bps

            # Check if user has a Solana wallet
            user_data = self.get_user_wallet_data(user_id)
            if not user_data:
                await query.edit_message_text(
                    "❌ You need to create a wallet first!\n\nUse /start to create a wallet.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return

            # Get primary wallet
            primary_wallet = user_data.get('primary_wallet', 'wallet1')
            primary_slot = user_data['wallet_slots'].get(primary_wallet, {})
            chains = primary_slot.get('chains', {})

            if 'SOL' not in chains:
                await query.edit_message_text(
                    "❌ No Solana wallet found!\n\nPlease create a Solana wallet first.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return

            sol_wallet = chains['SOL']
            private_key = sol_wallet.get('private_key')

            if not private_key:
                await query.edit_message_text(
                    "❌ Could not access wallet private key.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return

            # Show processing message
            await query.edit_message_text(
                f"🔄 Processing buy order...\n\n"
                f"💰 Amount: {sol_amount} SOL\n"
                f"🪙 Token: {token_symbol}\n"
                f"⚙️ Slippage: {slippage_bps/100}%\n\n"
                f"⏳ Getting quote..."
            )

            # Initialize Jupiter Swap
            try:
                swap_handler = JupiterSwap(private_key)
            except Exception as e:
                logger.error(f"Failed to initialize JupiterSwap: {e}")
                await query.edit_message_text(
                    f"❌ Failed to initialize swap handler: {str(e)}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return

            # Get quote
            from jupiter_swap import TOKENS as JUPITER_TOKENS, sol_to_lamports
            input_mint = JUPITER_TOKENS['SOL']
            output_mint = token_address
            amount = sol_to_lamports(sol_amount)

            quote = swap_handler.get_quote(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=int(slippage_bps)
            )

            if not quote:
                await query.edit_message_text(
                    f"❌ Failed to get quote from Jupiter.\n\n"
                    f"Token may have low liquidity or invalid address.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
                )
                return

            # Display quote and ask for confirmation
            in_amount = int(quote['inAmount']) / 1e9
            out_amount = int(quote['outAmount'])
            price_impact = float(quote.get('priceImpactPct', 0))

            # Estimate output tokens (decimals may vary)
            out_formatted = out_amount / 1e6  # Assuming 6 decimals for most tokens

            keyboard = [
                [InlineKeyboardButton("✅ Confirm Buy", callback_data=f'confirm_buy_{sol_amount}_{token_address}')],
                [InlineKeyboardButton("❌ Cancel", callback_data=f'refresh_{token_address}')]
            ]

            await query.edit_message_text(
                f"📊 <b>Buy Order Quote</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💰 You Pay: <b>{in_amount:.9f} SOL</b>\n"
                f"🪙 You Receive: <b>~{out_formatted:,.2f} {token_symbol}</b>\n"
                f"📊 Price Impact: <b>{price_impact:.4f}%</b>\n"
                f"⚙️ Slippage: <b>{slippage_bps/100}%</b>\n\n"
                f"⚠️ <b>Confirm this transaction?</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

            # Store quote in context for confirmation
            self.trading_context[user_id]['pending_quote'] = quote
            self.trading_context[user_id]['pending_amount'] = sol_amount

        except Exception as e:
            logger.error(f"Error in execute_buy: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
            )

    async def confirm_buy(self, query, user_id: int, sol_amount: float, token_address: str):
        """Confirm and execute the buy order"""
        try:
            # Get trading context
            if user_id not in self.trading_context:
                await query.edit_message_text("❌ Trading session expired.")
                return

            context = self.trading_context[user_id]
            quote = context.get('pending_quote')
            token_symbol = context.get('token_symbol', 'TOKEN')

            if not quote:
                await query.edit_message_text("❌ Quote expired. Please try again.")
                return

            # Get wallet
            user_data = self.get_user_wallet_data(user_id)
            primary_wallet = user_data.get('primary_wallet', 'wallet1')
            primary_slot = user_data['wallet_slots'].get(primary_wallet, {})
            sol_wallet = primary_slot['chains']['SOL']
            private_key = sol_wallet.get('private_key')

            # Show processing
            await query.edit_message_text(
                f"⏳ <b>Executing Swap...</b>\n\n"
                f"💰 Amount: {sol_amount} SOL\n"
                f"🪙 Token: {token_symbol}\n\n"
                f"⏳ Please wait...",
                parse_mode='HTML'
            )

            # Initialize and execute swap
            swap_handler = JupiterSwap(private_key)

            # Execute the swap
            from jupiter_swap import TOKENS as JUPITER_TOKENS, sol_to_lamports
            input_mint = JUPITER_TOKENS['SOL']
            output_mint = token_address
            amount = sol_to_lamports(sol_amount)
            slippage_bps = int(context.get('slippage_pct', 10) * 100)

            success = swap_handler.swap(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=slippage_bps,
                simulate=False
            )

            if success:
                # Create order record
                order_id = f"order_{user_id}_{int(datetime.datetime.now().timestamp())}"
                order = {
                    'order_id': order_id,
                    'token_address': token_address,
                    'token_symbol': token_symbol,
                    'amount_sol': sol_amount,
                    'status': 'completed',
                    'timestamp': datetime.datetime.now().isoformat(),
                    'tx_signature': 'check_solscan'  # Would need to capture actual signature
                }

                # Store order
                if user_id not in self.user_orders:
                    self.user_orders[user_id] = []
                self.user_orders[user_id].append(order)

                await query.edit_message_text(
                    f"✅ <b>Buy Order Completed!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💰 Spent: <b>{sol_amount} SOL</b>\n"
                    f"🪙 Token: <b>{token_symbol}</b>\n"
                    f"📋 Status: <b>Success</b>\n\n"
                    f"🔍 Check your transaction on Solscan",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Refresh Token", callback_data=f'refresh_{token_address}')],
                        [InlineKeyboardButton("📋 View Orders", callback_data=f'orders_{token_address}')],
                        [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
                    ])
                )
            else:
                await query.edit_message_text(
                    f"❌ <b>Buy Order Failed</b>\n\n"
                    f"The swap transaction failed. Please try again.",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]])
                )

        except Exception as e:
            logger.error(f"Error in confirm_buy: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error executing buy: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
            )

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
                [InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]
            ]

            await query.edit_message_text(
                f"⚙️ <b>Slippage Settings</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 Token: <b>{token_symbol}</b>\n"
                f"📊 Current: <b>{current_slippage}%</b>\n\n"
                f"Select slippage tolerance:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in show_slippage_menu: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def set_slippage(self, query, user_id: int, slippage_pct: float, token_address: str):
        """Set slippage tolerance"""
        try:
            if user_id in self.trading_context:
                self.trading_context[user_id]['slippage_pct'] = slippage_pct
                self.trading_context[user_id]['slippage_bps'] = 'auto' if slippage_pct == 10 else 'custom'

                await query.answer(f"Slippage set to {slippage_pct}%")
                # Refresh the token info
                await self.display_token_info(query.message, None, token_address)

        except Exception as e:
            logger.error(f"Error in set_slippage: {e}")
            await query.answer("❌ Error setting slippage")

    async def show_orders(self, query, user_id: int, token_address: str):
        """Show user's orders for this token"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')

            orders = self.user_orders.get(user_id, [])
            # Filter orders for this token
            token_orders = [o for o in orders if o.get('token_address') == token_address]

            message = f"📋 <b>Orders for {token_symbol}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

            if not token_orders:
                message += "No orders yet for this token.\n"
            else:
                for idx, order in enumerate(token_orders[-10:], 1):  # Show last 10
                    status_emoji = "✅" if order['status'] == 'completed' else "⏳"
                    message += f"{status_emoji} <b>Order #{idx}</b>\n"
                    message += f"💰 Amount: {order['amount_sol']} SOL\n"
                    message += f"📅 {order['timestamp'][:16]}\n"
                    message += f"Status: {order['status']}\n\n"

            keyboard = [
                [InlineKeyboardButton("🔄 Refresh Orders", callback_data=f'orders_{token_address}')],
                [InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')]
            ]

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Error in show_orders: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")

    async def ask_custom_amount(self, query, user_id: int, token_address: str):
        """Ask user for custom SOL amount"""
        try:
            context = self.trading_context.get(user_id, {})
            token_symbol = context.get('token_symbol', 'TOKEN')

            # Set waiting for input
            self.waiting_for_input[user_id] = {
                'type': 'buy_custom_amount',
                'token_address': token_address,
                'message_id': query.message.message_id
            }

            await query.edit_message_text(
                f"💵 <b>Custom Buy Amount</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🪙 Token: <b>{token_symbol}</b>\n\n"
                f"Enter the amount of SOL you want to spend:\n"
                f"(e.g., 0.1, 0.5, 2)",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f'refresh_{token_address}')]])
            )

        except Exception as e:
            logger.error(f"Error in ask_custom_amount: {e}")
            await query.edit_message_text(f"❌ Error: {str(e)}")
