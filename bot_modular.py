"""
Tenex Trading Bot - Modular Version
Clean microservice-style architecture using separate service modules

This is the NEW modular version of the bot.
The old tenex_trading_bot.py remains as a backup.
"""

import os
import csv
import json
import logging
import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Import services
from services import (
    DataManager,
    WalletManager,
    BalanceService,
    TokenService,
    TransferService,
    LimitOrderService,
    NotificationService
)

# Import trading integration
from trading_integration import TradingMixin

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID', '0'))
NOTIFICATION_CHANNEL_ID = os.getenv('TELEGRAM_NOTIFICATION_CHANNEL') or None
WALLETS_DIR = Path('wallets')
CONFIG_FILE = Path('config.json')

# Ensure directories exist
WALLETS_DIR.mkdir(parents=True, exist_ok=True)


def load_config():
    """Load chain configuration from config.json"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        logger.error("config.json not found! Using default configuration.")
        return {
            'chains': {
                'SOL': {
                    'enabled': True,
                    'name': 'Solana',
                    'symbol': 'SOL',
                    'rpc': 'https://api.mainnet-beta.solana.com',
                    'decimals': 9,
                    'emoji': '🧬',
                    'wallet_file': 'wallets/sol_wallets.json',
                    'coingecko_id': 'solana',
                    'dexscreener_chain': 'solana'
                },
                'ETH': {
                    'enabled': True,
                    'name': 'Ethereum',
                    'symbol': 'ETH',
                    'rpc': 'https://eth.llamarpc.com',
                    'decimals': 18,
                    'emoji': '💎',
                    'wallet_file': 'wallets/eth_wallets.json',
                    'coingecko_id': 'ethereum',
                    'dexscreener_chain': 'ethereum'
                }
            },
            'settings': {
                'max_wallet_slots_per_user': 3,
                'price_update_interval': 60,
                'balance_cache_timeout': 30
            }
        }


# Load config
CONFIG = load_config()

# Network configurations (built from config)
NETWORKS = {}
for chain_key, chain_config in CONFIG['chains'].items():
    NETWORKS[chain_key] = {
        'name': chain_config['name'],
        'symbol': chain_config['symbol'],
        'file': WALLETS_DIR / chain_config['wallet_file'].split('/')[-1],
        'rpc': chain_config['rpc'],
        'decimals': chain_config['decimals'],
        'enabled': chain_config['enabled'],
        'emoji': chain_config.get('emoji', '🔹'),
        'coingecko_id': chain_config.get('coingecko_id', ''),
        'dexscreener_chain': chain_config.get('dexscreener_chain'),
        'import_supported': chain_config.get('import_supported', True)
    }


def get_enabled_networks():
    """Get only enabled networks from config"""
    return {k: v for k, v in CONFIG['chains'].items() if v.get('enabled', True)}


# DexScreener configuration
DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"
SUPPORTED_CHAINS = [
    chain['dexscreener_chain']
    for chain in CONFIG['chains'].values()
    if chain.get('enabled', True) and chain.get('dexscreener_chain')
]


class TradingBotModular(TradingMixin):
    """
    Modular Trading Bot using microservice-style architecture

    This version delegates all business logic to specialized services:
    - DataManager: User data persistence
    - WalletManager: Wallet operations
    - BalanceService: Balance queries and prices
    - TokenService: Token detection and info
    - TransferService: Blockchain transfers
    """

    def __init__(self):
        """Initialize bot with all service modules"""
        logger.info("Initializing Tenex Trading Bot (Modular Version)")

        # Initialize services
        self.data_manager = DataManager(WALLETS_DIR, CONFIG)
        self.wallet_manager = WalletManager(self.data_manager, CONFIG)
        self.balance_service = BalanceService(CONFIG)
        self.token_service = TokenService(CONFIG)
        self.transfer_service = TransferService(CONFIG)
        self.limit_order_service = LimitOrderService(WALLETS_DIR)
        self.notification_service = NotificationService(BOT_TOKEN, NOTIFICATION_CHANNEL_ID)

        # State management (not in services - bot-specific)
        self.waiting_for_input = {}  # Tracks users waiting for text input

        # Trading state (inherited from TradingMixin)
        self.trading_context = {}  # Active token trades per user
        self.user_orders = {}  # Pending/completed orders

        logger.info("All services initialized successfully")

    # ============================================================
    # HELPER METHODS - Delegate to Services
    # ============================================================

    def get_user_wallet_data(self, user_id: int) -> dict:
        """Get user wallet data (delegated to DataManager)"""
        return self.data_manager.get_user_data(user_id)

    def save_user_wallets(self):
        """Save user wallets (delegated to DataManager)"""
        return self.data_manager.save_user_wallets()

    async def get_balance(self, network: str, address: str):
        """Get balance (delegated to BalanceService)"""
        return await self.balance_service.get_balance(network, address)

    async def get_token_prices(self):
        """Get token prices (delegated to BalanceService)"""
        return await self.balance_service.get_token_prices()

    async def get_wallet_total_balance_usd(self, user_id: int, slot_name: str) -> float:
        """Get total wallet balance in USD (delegated to BalanceService)"""
        return await self.balance_service.get_wallet_total_balance_usd(
            user_id, slot_name, self.data_manager
        )

    def is_contract_address(self, text: str) -> bool:
        """Check if text is contract address (delegated to TokenService)"""
        return self.token_service.is_contract_address(text)

    async def detect_and_fetch_token(self, token_address: str):
        """Detect and fetch token (delegated to TokenService)"""
        return await self.token_service.detect_and_fetch_token(token_address)

    # ============================================================
    # WALLET MANAGEMENT
    # ============================================================

    def get_primary_wallet(self, user_id: int) -> str:
        """Get primary wallet slot name"""
        return self.data_manager.get_primary_wallet(user_id) or 'wallet1'

    def get_wallet_slot(self, user_id: int, slot_name: str) -> dict:
        """Get wallet slot data"""
        return self.data_manager.get_wallet_slot(user_id, slot_name) or {}

    def set_primary_wallet(self, user_id: int, slot_name: str) -> bool:
        """Set primary wallet"""
        return self.data_manager.set_primary_wallet(user_id, slot_name)

    def get_available_wallet_slots(self, user_id: int) -> list:
        """Get available (empty) wallet slots"""
        return self.data_manager.get_available_slots(user_id)

    def delete_wallet_slot(self, user_id: int, slot_name: str) -> bool:
        """Delete a wallet slot"""
        return self.data_manager.delete_wallet_slot(user_id, slot_name)

    def set_wallet_label(self, user_id: int, slot_name: str, label: str) -> bool:
        """Set wallet label"""
        return self.wallet_manager.set_wallet_label(user_id, slot_name, label)

    def get_available_wallet(self, network: str):
        """Get an available pre-generated wallet for the network"""
        wallet_file = NETWORKS[network]['file']

        if not wallet_file.exists():
            return None

        # Read CSV file
        with open(wallet_file, 'r') as f:
            reader = csv.DictReader(f)
            wallets = list(reader)

        # Find first unassigned wallet
        assigned_addresses = set()
        for user_data in self.data_manager.user_wallets.values():
            # Check old format
            if network in user_data.get('wallets', {}):
                assigned_addresses.add(user_data['wallets'][network]['address'])

            # Check new format (wallet_slots)
            if 'wallet_slots' in user_data:
                for slot_data in user_data['wallet_slots'].values():
                    if network in slot_data.get('chains', {}):
                        assigned_addresses.add(slot_data['chains'][network]['address'])

        for wallet in wallets:
            address = wallet['Address']
            if address not in assigned_addresses:
                return {
                    'address': address,
                    'private_key': wallet['Private Key'],
                    'derivation_path': wallet['Derivation Path']
                }

        return None

    def assign_wallet_to_user(self, user_id: int, network: str, slot_name: str = None):
        """Assign a pre-generated wallet to a user in a specific slot"""
        user_id_str = str(user_id)

        # Auto-migrate if needed
        if self.data_manager.needs_migration(user_id_str):
            self.data_manager.migrate_user_data(user_id_str)

        # Get wallet slot (default to primary if not specified)
        if slot_name is None:
            slot_name = self.get_primary_wallet(user_id)

        # Check if wallet already exists in this slot
        user_data = self.data_manager.get_user_data(user_id)
        if user_data and 'wallet_slots' in user_data:
            wallet_slots = user_data.get('wallet_slots', {})
            if slot_name in wallet_slots:
                slot_data = wallet_slots[slot_name]
                if network in slot_data.get('chains', {}):
                    logger.warning(f"User {user_id} already has {network} in {slot_name}")
                    return None  # Already has this chain in this slot

        # Get available pre-generated wallet
        wallet = self.get_available_wallet(network)
        if not wallet:
            return None

        # Initialize structure if needed (new user)
        if not user_data:
            max_slots = CONFIG.get('settings', {}).get('max_wallet_slots_per_user', 3)
            user_data = {
                'primary_wallet': 'wallet1',
                'wallet_slots': {}
            }
            # Initialize all slots
            for i in range(1, max_slots + 1):
                slot = f'wallet{i}'
                user_data['wallet_slots'][slot] = {
                    'label': None,
                    'created_at': None,
                    'is_primary': (slot == 'wallet1'),
                    'chains': {}
                }

        # Initialize slot if it doesn't exist
        if 'wallet_slots' not in user_data:
            user_data['wallet_slots'] = {}

        if slot_name not in user_data['wallet_slots']:
            user_data['wallet_slots'][slot_name] = {
                'label': None,
                'created_at': datetime.datetime.now().isoformat(),
                'is_primary': slot_name == self.get_primary_wallet(user_id),
                'chains': {}
            }

        # Update created_at if this is the first chain in the slot
        if not user_data['wallet_slots'][slot_name].get('chains'):
            user_data['wallet_slots'][slot_name]['created_at'] = datetime.datetime.now().isoformat()

        # Add wallet to slot
        user_data['wallet_slots'][slot_name]['chains'][network] = wallet
        self.data_manager.set_user_data(user_id, user_data)

        logger.info(f"Assigned {network} wallet to user {user_id} in {slot_name}")
        return wallet

    # ============================================================
    # COMMAND HANDLERS
    # ============================================================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        user_id = user.id

        logger.info(f"User {user_id} ({user.username}) started the bot")

        # Get or create user data
        user_data = self.data_manager.get_user_data(user_id)

        # Initialize if new user
        if not user_data:
            logger.info(f"New user {user_id}, initializing wallet structure")
            max_slots = CONFIG.get('settings', {}).get('max_wallet_slots_per_user', 3)

            user_data = {
                'primary_wallet': 'wallet1',
                'wallet_slots': {}
            }

            # Initialize empty slots
            for i in range(1, max_slots + 1):
                slot_name = f'wallet{i}'
                user_data['wallet_slots'][slot_name] = {
                    'label': None,
                    'created_at': None,
                    'is_primary': (slot_name == 'wallet1'),
                    'chains': {}
                }

            self.data_manager.set_user_data(user_id, user_data)

            # Send notification for new user
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Unknown"
            await self.notification_service.notify_new_user(
                user_id=user_id,
                username=user.username,
                full_name=full_name
            )

        # Show main menu
        await self.show_main_menu(update, user_id)

    async def show_main_menu(self, update, user_id: int):
        """Display main menu with wallet balance information"""
        keyboard = await self.get_main_menu_keyboard(user_id)
        user_data = self.data_manager.get_user_data(user_id)

        message = "🤖 Welcome to Tenex Trading Bot!\n\n"

        # Check if user already has wallets
        if user_data and 'wallet_slots' in user_data:
            primary_wallet = user_data.get('primary_wallet') or 'wallet1'
            primary_slot = user_data['wallet_slots'].get(primary_wallet, {})
            chains = primary_slot.get('chains', {})

            if chains:
                # Get slot label
                label = primary_slot.get('label')
                if label:
                    message += f"💼 {primary_wallet.title()} (Active) 🟢 - \"{label}\"\n\n"
                else:
                    message += f"💼 {primary_wallet.title()} (Active) 🟢\n\n"

                # Fetch balances and prices
                prices = await self.get_token_prices()
                total_primary = 0

                # Get enabled networks from config
                enabled_networks = get_enabled_networks()

                # Display primary wallet balances
                for network, wallet_data in chains.items():
                    # Skip disabled networks
                    if network not in enabled_networks:
                        continue

                    try:
                        balance_data = await self.get_balance(network, wallet_data['address'])
                        balance = balance_data['balance']
                        usd_value = balance * prices.get(network, 0)
                        total_primary += usd_value

                        emoji = CONFIG['chains'][network].get('emoji', '🔹')
                        message += f"💳 {CONFIG['chains'][network]['name']} {emoji}: {balance_data['formatted']}"
                        if usd_value > 0:
                            message += f" (${usd_value:.2f})"
                        message += "\n"
                    except Exception as e:
                        logger.error(f"Error getting balance for {network}: {e}")

                message += f"\nTotal Balance (Primary): ${total_primary:.2f}\n"
            else:
                message += "Get started by creating or importing a wallet.\n"
        else:
            message += "Get started by creating or importing a wallet.\n"

        if isinstance(update, Update):
            await update.message.reply_text(
                message,
                reply_markup=keyboard
            )
        else:
            # It's a query
            await update.edit_message_text(
                message,
                reply_markup=keyboard
            )

    async def get_main_menu_keyboard(self, user_id: int):
        """Generate main menu keyboard based on user's wallets"""
        user_data = self.data_manager.get_user_data(user_id)

        keyboard = []

        # Check if user has any wallets
        has_wallets = False
        if user_data and 'wallet_slots' in user_data:
            for slot_data in user_data['wallet_slots'].values():
                if slot_data.get('chains'):
                    has_wallets = True
                    break

        if has_wallets:
            # User has wallets - show main menu options
            keyboard.append([InlineKeyboardButton("🔄 Refresh Balance", callback_data='refresh_balance')])
            keyboard.append([InlineKeyboardButton("🎒 View Bags", callback_data='view_bags')])
            keyboard.append([InlineKeyboardButton("👛 View All Wallets", callback_data='view_wallets')])
            keyboard.append([InlineKeyboardButton("🔧 Manage Wallets", callback_data='manage_wallets')])
            keyboard.append([InlineKeyboardButton("📤 Withdraw", callback_data='withdraw_start')])
            keyboard.append([InlineKeyboardButton("🔑 Export Private Key", callback_data='export_key')])
        else:
            # User has no wallets - show Create and Import on same line
            keyboard.append([
                InlineKeyboardButton("➕ Create Wallet", callback_data='create_start'),
                InlineKeyboardButton("📥 Import Wallet", callback_data='import_start')
            ])

        return InlineKeyboardMarkup(keyboard)

    # ============================================================
    # BUTTON CALLBACK HANDLER
    # ============================================================

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all button callbacks"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        action = query.data

        logger.info(f"Button pressed by {user_id}: {action}")

        try:
            # Main menu
            if action == 'back_to_menu':
                await self.show_main_menu(query, user_id)

            # Refresh balance (same as view wallets)
            elif action == 'refresh_balance':
                await self.view_wallets(query, user_id)

            # View wallets
            elif action == 'view_wallets':
                await self.view_wallets(query, user_id)

            # Manage wallets
            elif action == 'manage_wallets':
                await self.manage_wallets_menu(query, user_id)

            # View bags (trading)
            elif action == 'view_bags':
                await self.show_bags(query, user_id)

            # Export private key
            elif action == 'export_key':
                await self.export_key_start(query, user_id)

            # Withdraw
            elif action == 'withdraw_start':
                await self.withdraw_start(query, user_id)

            # Internal transfer
            elif action == 'internal_transfer_start':
                await self.internal_transfer_start(query, user_id)

            # Create wallet flow
            elif action == 'create' or action == 'create_start' or action == 'create_in_slot_menu':
                await self.create_in_slot_menu(query, user_id)
            elif action.startswith('create_in_'):
                slot_name = action.replace('create_in_', '')
                await self.show_slot_chain_selection(query, user_id, slot_name, 'create')
            elif action.startswith('create_network_'):
                parts = action.replace('create_network_', '').split('_', 1)
                slot_name = parts[0]
                network = parts[1]
                await self.create_wallet(query, context, network, slot_name)

            # Import wallet flow
            elif action == 'import' or action == 'import_start' or action == 'import_in_slot_menu':
                await self.import_in_slot_menu(query, user_id)
            elif action.startswith('import_in_'):
                slot_name = action.replace('import_in_', '')
                await self.show_slot_chain_selection(query, user_id, slot_name, 'import')
            elif action.startswith('import_network_'):
                parts = action.replace('import_network_', '').split('_', 1)
                slot_name = parts[0]
                network = parts[1]
                await self.start_import_flow(query, network, slot_name)

            # Transfer between wallets (internal transfer)
            elif action.startswith('transfer_source_'):
                # Note: This would need additional implementation for the full flow
                # For now, just show a message that it's not yet fully implemented
                slot_name = action.replace('transfer_source_', '')
                await query.edit_message_text(
                    "⚠️ Internal transfer flow not yet fully implemented in modular bot.\n\n"
                    "This feature will be completed in a future update.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')
                    ]])
                )

            # Switch wallet
            elif action == 'switch_wallet':
                await self.switch_wallet_menu(query, user_id)
            elif action.startswith('switch_to_'):
                slot_name = action.replace('switch_to_', '')
                await self.switch_primary_wallet(query, user_id, slot_name)

            # Delete wallet
            elif action == 'delete_wallet':
                await self.delete_wallet_menu(query, user_id)
            elif action.startswith('delete_'):
                slot_name = action.replace('delete_', '')
                await self.confirm_delete_wallet(query, user_id, slot_name)
            elif action.startswith('confirm_delete_'):
                slot_name = action.replace('confirm_delete_', '')
                await self.execute_delete_wallet(query, user_id, slot_name)

            # Label wallet
            elif action == 'label_wallet':
                await self.label_wallet_menu(query, user_id)
            elif action.startswith('label_'):
                slot_name = action.replace('label_', '')
                await self.start_label_wallet_flow(query, user_id, slot_name)

            # Export
            elif action == 'export':
                await self.export_key_start(query, user_id)
            elif action.startswith('export_slot_'):
                slot_name = action.replace('export_slot_', '')
                await self.export_select_chain(query, user_id, slot_name)
            elif action.startswith('export_chain_'):
                parts = action.replace('export_chain_', '').split('_', 1)
                slot_name = parts[0]
                network = parts[1]
                await self.export_private_key(query, network, user_id, slot_name)

            # Withdraw
            elif action == 'withdraw':
                await self.withdraw_start(query, user_id)
            elif action.startswith('withdraw_slot_'):
                slot_name = action.replace('withdraw_slot_', '')
                await self.withdraw_select_chain(query, user_id, slot_name)
            elif action.startswith('withdraw_chain_'):
                parts = action.replace('withdraw_chain_', '').split('_', 1)
                slot_name = parts[0]
                network = parts[1]
                await self.start_withdraw_flow(query, network, slot_name)

            # Token scanning (from token address)
            elif action.startswith('refresh_'):
                token_address = action.replace('refresh_', '')
                await self.display_token_info(update, context, token_address)

            # Trading actions (inherited from TradingMixin)
            elif action.startswith('buy_'):
                parts = action.replace('buy_', '').split('_', 1)
                if len(parts) == 2:
                    if parts[0] == 'x':
                        # Custom amount
                        token_address = parts[1]
                        await self.ask_custom_amount(query, user_id, token_address)
                    else:
                        # Fixed amount
                        sol_amount = float(parts[0])
                        token_address = parts[1]
                        await self.execute_buy(query, user_id, sol_amount, token_address)

            elif action.startswith('confirm_buy_'):
                parts = action.replace('confirm_buy_', '').split('_', 1)
                sol_amount = float(parts[0])
                token_address = parts[1]
                await self.confirm_buy(query, user_id, sol_amount, token_address)

            elif action.startswith('slippage_'):
                token_address = action.replace('slippage_', '')
                await self.show_slippage_menu(query, user_id, token_address)

            elif action.startswith('set_slippage_'):
                parts = action.replace('set_slippage_', '').rsplit('_', 1)
                slippage_pct = float(parts[0])
                token_address = parts[1]
                await self.set_slippage(query, user_id, slippage_pct, token_address)

            elif action.startswith('orders_'):
                token_address = action.replace('orders_', '')
                await self.show_orders(query, user_id, token_address)

            # Bags actions
            elif action.startswith('bag_buy_'):
                token_address = action.replace('bag_buy_', '')
                await self.show_bag_buy_options(query, user_id, token_address)

            elif action.startswith('bag_sell_'):
                token_address = action.replace('bag_sell_', '')
                await self.show_bag_sell_options(query, user_id, token_address)

            # Sell percentage actions
            elif action.startswith('sell_'):
                if action.startswith('sell_custom_'):
                    token_address = action.replace('sell_custom_', '')
                    await self.ask_custom_sell_amount(query, user_id, token_address)
                else:
                    # sell_25_, sell_50_, etc.
                    for pct in ['25', '50', '75', '100']:
                        if action.startswith(f'sell_{pct}_'):
                            token_address = action.replace(f'sell_{pct}_', '')
                            await self.execute_sell(query, user_id, float(pct), token_address)
                            break

            elif action.startswith('confirm_sell_'):
                parts = action.replace('confirm_sell_', '').split('_', 1)
                percentage = float(parts[0])
                token_address = parts[1]
                await self.confirm_sell(query, user_id, percentage, token_address)

        except Exception as e:
            logger.error(f"Error in button handler: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}\n\nPlease try again or return to the menu.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')
                ]])
            )

    # ============================================================
    # MESSAGE HANDLER
    # ============================================================

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Check if user is waiting for input
        if user_id in self.waiting_for_input:
            state = self.waiting_for_input[user_id]

            # Handle custom buy amount
            if state.get('type') == 'buy_custom_amount':
                token_address = state['token_address']
                try:
                    sol_amount = float(message_text.strip())
                    if sol_amount <= 0:
                        raise ValueError("Amount must be positive")

                    del self.waiting_for_input[user_id]

                    # Delete waiting message
                    try:
                        await context.bot.delete_message(
                            chat_id=update.effective_chat.id,
                            message_id=state.get('message_id')
                        )
                    except:
                        pass

                    # Send processing message
                    processing_msg = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Processing {sol_amount} SOL buy order..."
                    )

                    # Create fake query
                    from telegram import CallbackQuery
                    fake_query = CallbackQuery(
                        id="custom_buy",
                        from_user=update.effective_user,
                        chat_instance=str(update.effective_chat.id),
                        data=f"buy_x_{token_address}",
                        message=processing_msg
                    )

                    await self.execute_buy(fake_query, user_id, sol_amount, token_address)

                except ValueError:
                    del self.waiting_for_input[user_id]
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Invalid amount. Please enter a valid number.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')
                        ]])
                    )
                return

            # Handle custom sell amount
            elif state.get('type') == 'sell_custom_amount':
                token_address = state['token_address']
                try:
                    percentage = float(message_text.strip())
                    if percentage <= 0 or percentage > 100:
                        raise ValueError("Percentage must be between 1 and 100")

                    del self.waiting_for_input[user_id]

                    # Delete waiting message
                    try:
                        await context.bot.delete_message(
                            chat_id=update.effective_chat.id,
                            message_id=state.get('message_id')
                        )
                    except:
                        pass

                    # Send processing message
                    processing_msg = await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"Processing {percentage}% sell order..."
                    )

                    # Create fake query
                    from telegram import CallbackQuery
                    fake_query = CallbackQuery(
                        id="custom_sell",
                        from_user=update.effective_user,
                        chat_instance=str(update.effective_chat.id),
                        data=f"sell_custom_{token_address}",
                        message=processing_msg
                    )

                    await self.execute_sell(fake_query, user_id, percentage, token_address)

                except ValueError:
                    del self.waiting_for_input[user_id]
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Invalid percentage. Please enter a number between 1 and 100.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')
                        ]])
                    )
                return

            # Handle import seed phrase
            elif state.get('action') == 'import':
                await self.import_wallet(update, context, state, message_text)
                return

            # Handle label input
            elif state.get('action') == 'label_wallet':
                slot_name = state['slot_name']
                label_text = message_text.strip()

                del self.waiting_for_input[user_id]

                success = self.set_wallet_label(user_id, slot_name, label_text)

                if success:
                    if label_text.lower() == 'clear' or not label_text:
                        message = f"✅ Label removed from {slot_name.title()}."
                    else:
                        message = f"✅ Label set: {label_text}"
                else:
                    message = "❌ Failed to set label."

                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=message,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')
                    ]])
                )
                return

        # Check if it's a token address
        if self.is_contract_address(message_text):
            await self.display_token_info(update, context, message_text.strip())
            return

        # Default response
        await update.message.reply_text(
            "Send a token contract address to view trading info,\n"
            "or use /start to access the menu."
        )

    # ============================================================
    # TOKEN INFO DISPLAY (DexScreener Integration)
    # ============================================================

    async def display_token_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE, token_address: str):
        """Display token information from DexScreener"""
        # Send processing message
        processing_msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🔍 Detecting chain and fetching token data..."
        )

        try:
            # Fetch token data
            result = await self.detect_and_fetch_token(token_address)

            if not result:
                await processing_msg.edit_text(
                    "❌ Token not found on any supported chain.\n\n"
                    f"Supported chains: {', '.join(SUPPORTED_CHAINS[:5])} and more."
                )
                return

            chain = result['chain']
            pair_data = result['data']

            # Extract token information
            base_token = pair_data.get('baseToken', {})
            quote_token = pair_data.get('quoteToken', {})
            token_name = base_token.get('name', 'Unknown')
            token_symbol = base_token.get('symbol', 'N/A')

            price_usd = float(pair_data.get('priceUsd', 0))
            price_native = float(pair_data.get('priceNative', 0))

            # Market data
            liquidity = pair_data.get('liquidity', {})
            liquidity_usd = float(liquidity.get('usd', 0))

            market_cap = float(pair_data.get('marketCap', 0)) if pair_data.get('marketCap') else 0
            fdv = float(pair_data.get('fdv', 0)) if pair_data.get('fdv') else 0

            # Price changes
            price_change = pair_data.get('priceChange', {})
            change_5m = price_change.get('m5', 0)
            change_1h = price_change.get('h1', 0)
            change_6h = price_change.get('h6', 0)
            change_24h = price_change.get('h24', 0)

            # Volume
            volume = pair_data.get('volume', {})
            volume_24h = float(volume.get('h24', 0))

            # Pair info
            dex_id = pair_data.get('dexId', 'Unknown')
            pair_address = pair_data.get('pairAddress', 'N/A')
            pair_created = pair_data.get('pairCreatedAt', 0)

            # Calculate time ago
            if pair_created > 0:
                import datetime
                created_time = datetime.datetime.fromtimestamp(pair_created / 1000)
                time_diff = datetime.datetime.now() - created_time

                if time_diff.days > 0:
                    time_ago = f"{time_diff.days}d ago"
                elif time_diff.seconds >= 3600:
                    time_ago = f"{time_diff.seconds // 3600}h ago"
                elif time_diff.seconds >= 60:
                    time_ago = f"{time_diff.seconds // 60}m ago"
                else:
                    time_ago = f"{time_diff.seconds}s ago"
            else:
                time_ago = "N/A"

            # Socials and links
            info = pair_data.get('info', {})
            socials = info.get('socials', [])
            websites = info.get('websites', [])

            # Build compact links
            compact_links = []

            # Block explorer (Scan)
            if chain == 'solana':
                compact_links.append(f'<a href="https://solscan.io/token/{token_address}">Scan</a>')
            elif chain == 'ethereum':
                compact_links.append(f'<a href="https://etherscan.io/token/{token_address}">Scan</a>')
            elif chain == 'base':
                compact_links.append(f'<a href="https://basescan.org/token/{token_address}">Scan</a>')
            elif chain == 'bsc':
                compact_links.append(f'<a href="https://bscscan.com/token/{token_address}">Scan</a>')
            elif chain == 'arbitrum':
                compact_links.append(f'<a href="https://arbiscan.io/token/{token_address}">Scan</a>')
            elif chain == 'polygon':
                compact_links.append(f'<a href="https://polygonscan.com/token/{token_address}">Scan</a>')

            # DexScreener
            compact_links.append(f'<a href="https://dexscreener.com/{chain}/{token_address}">DexS</a>')

            # CoinGecko (if available)
            compact_links.append(f'<a href="https://www.coingecko.com/en/search?query={token_address}">Gecko</a>')

            # Twitter/X (if available)
            twitter_url = None
            for social in socials:
                if social.get('type', '').lower() in ['twitter', 'x']:
                    twitter_url = social.get('url', '')
                    break

            if twitter_url:
                compact_links.append(f'<a href="{twitter_url}">𝕏</a>')

            # Telegram (if available)
            telegram_url = None
            for social in socials:
                if social.get('type', '').lower() == 'telegram':
                    telegram_url = social.get('url', '')
                    break

            if telegram_url:
                compact_links.append(f'<a href="{telegram_url}">TG</a>')

            # Website (if available)
            if websites and len(websites) > 0:
                website_url = websites[0].get('url', '') if isinstance(websites[0], dict) else websites[0]
                if website_url:
                    compact_links.append(f'<a href="{website_url}">Web</a>')

            # Build message
            def format_price_change(value):
                if value > 0:
                    return f"🟢 +{value:.2f}%"
                elif value < 0:
                    return f"🔴 {value:.2f}%"
                else:
                    return f"⚪ {value:.2f}%"

            message = (
                f"<b>Tenex Trading Bot (Modular)</b>\n"
                f"<b>Multi-chain Trading Assistant</b>\n\n"
                f"<b>🪙 Token Information</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"<b>📛 Name:</b> {token_name} ({token_symbol})\n"
                f"<b>⛓️ Chain:</b> {chain.title()}\n"
                f"<b>🏦 DEX:</b> {dex_id.title()}\n\n"
                f"<b>💹 Price:</b> ${price_usd:.10f}\n"
                f"<b>📊 Market Cap:</b> ${market_cap:,.0f}\n"
                f"<b>💧 Liquidity:</b> ${liquidity_usd:,.0f}\n"
                f"<b>📈 Volume (24h):</b> ${volume_24h:,.0f}\n"
            )

            if fdv > 0:
                message += f"<b>💎 FDV:</b> ${fdv:,.0f}\n"

            message += f"\n<b>📉 Price Changes:</b>\n"
            message += f"5m: {format_price_change(change_5m)}\n"
            message += f"1h: {format_price_change(change_1h)}\n"
            message += f"6h: {format_price_change(change_6h)}\n"
            message += f"24h: {format_price_change(change_24h)}\n"

            message += f"\n<b>🕒 Pair Created:</b> {time_ago}\n"

            # Compact links
            if compact_links:
                message += f"\n<b>🔗 Links:</b> {' | '.join(compact_links)}\n"

            message += f"\n<b>📋 Contract Address:</b>\n"
            message += f"<code>{token_address}</code>\n"

            # Store trading context for this user
            user_id = update.effective_user.id
            self.trading_context[user_id] = {
                'token_address': token_address,
                'chain': chain,
                'token_name': token_name,
                'token_symbol': token_symbol,
                'price_usd': price_usd,
                'market_cap': market_cap,  # Store market cap for limit orders
                'slippage_bps': 'auto',  # Default auto = up to 10%
                'slippage_pct': 10
            }

            # Create buy buttons (only for Solana chain for now)
            keyboard = []
            if chain.lower() == 'solana':
                keyboard.append([
                    InlineKeyboardButton("1 💵", callback_data=f'buy_1_{token_address}'),
                    InlineKeyboardButton("3 💵", callback_data=f'buy_3_{token_address}'),
                    InlineKeyboardButton("X SOL 💵", callback_data=f'buy_x_{token_address}')
                ])
                keyboard.append([
                    InlineKeyboardButton("⚙️ Slippage (Auto)", callback_data=f'slippage_{token_address}'),
                ])
                keyboard.append([
                    InlineKeyboardButton("📋 Orders", callback_data=f'orders_{token_address}'),
                    InlineKeyboardButton("⏰ Limit Orders", callback_data=f'limit_menu_{token_address}')
                ])
                keyboard.append([
                    InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_{token_address}')
                ])
                keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')])

                reply_markup = InlineKeyboardMarkup(keyboard)
                await processing_msg.edit_text(message, parse_mode='HTML', disable_web_page_preview=True, reply_markup=reply_markup)
            else:
                # Non-Solana chains: just show info without buy buttons
                await processing_msg.edit_text(message, parse_mode='HTML', disable_web_page_preview=True)

        except Exception as e:
            logger.error(f"Error displaying token info: {e}")
            await processing_msg.edit_text(
                f"❌ Error fetching token data: {str(e)}\n\n"
                "Please try again later."
            )

    # ============================================================
    # WALLET CREATION (Using WalletManager Service)
    # ============================================================

    async def create_wallet(self, query, context, network: str, slot_name: str = None):
        """Assign a pre-generated wallet to user in specified slot"""
        user_id = query.from_user.id

        try:
            # Show processing message
            await query.edit_message_text(f"⏳ Creating {CONFIG['chains'][network]['name']} wallet in {slot_name or 'primary slot'}...")

            # Assign pre-generated wallet to user
            wallet = self.assign_wallet_to_user(user_id, network, slot_name)

            if not wallet:
                await query.edit_message_text(
                    f"❌ Sorry, no available {CONFIG['chains'][network]['name']} wallets at the moment. "
                    "Please contact support.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')
                    ]])
                )
                return

            # Get balance
            balance_data = await self.get_balance(network, wallet['address'])

            # Get slot info for display
            actual_slot_name = slot_name or self.get_primary_wallet(user_id)
            slot_data = self.get_wallet_slot(user_id, actual_slot_name)
            slot_label = slot_data.get('label')
            slot_display = f"{actual_slot_name}" if not slot_label else f"{actual_slot_name} - \"{slot_label}\""

            # Success message
            chain_emoji = CONFIG['chains'][network].get('emoji', '🔹')
            message = (
                f"✅ <b>{CONFIG['chains'][network]['name']} Wallet Created!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{chain_emoji} <b>Network:</b> {CONFIG['chains'][network]['name']}\n"
                f"📍 <b>Slot:</b> {slot_display.title()}\n"
                f"🔑 <b>Address:</b>\n<code>{wallet['address']}</code>\n\n"
                f"💰 <b>Balance:</b> {balance_data['formatted']}\n\n"
                f"⚠️ <b>SAVE YOUR PRIVATE KEY!</b>\n"
                f"Use 'Export Private Key' from the menu to view it again.\n\n"
                f"🔐 <b>Private Key:</b>\n<code>{wallet['private_key']}</code>\n\n"
                f"⚠️ <b>Never share your private key with anyone!</b>"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💼 View Wallets", callback_data='view_wallets')],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
            ])

            # Send notification for wallet creation
            await self.notification_service.notify_wallet_created(
                user_id=user_id,
                username=query.from_user.username,
                network=network,
                address=wallet['address'],
                slot_name=actual_slot_name
            )

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error creating wallet: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error creating wallet: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')
                ]])
            )

    # ============================================================
    # WALLET SLOT SELECTION MENUS
    # ============================================================

    async def create_in_slot_menu(self, query, user_id: int):
        """Show wallet slot selection for creating new wallets"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "📁 Select wallet slot to create chain in:\n\n"
            keyboard = []

            # Show all wallet slots with their chain counts
            enabled_networks = get_enabled_networks()
            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Count enabled chains in this slot
                enabled_chains = {k: v for k, v in chains.items() if k in enabled_networks}
                chain_count = len(enabled_chains)
                total_enabled = len(enabled_networks)

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'
                button_text += f" ({chain_count}/{total_enabled} chains)"

                message += f"{button_text}\n"

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'create_in_{slot_name}'
                )])

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing create in slot menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def import_in_slot_menu(self, query, user_id: int):
        """Show wallet slot selection for importing wallets"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "📥 Import Wallet - Select Slot\n\n"
            keyboard = []

            # Show all wallet slots with their chain counts
            enabled_networks = get_enabled_networks()
            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Count enabled chains in this slot
                enabled_chains = {k: v for k, v in chains.items() if k in enabled_networks}
                chain_count = len(enabled_chains)
                total_enabled = len(enabled_networks)

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'
                button_text += f" ({chain_count}/{total_enabled} chains)"

                message += f"{button_text}\n"

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'import_in_{slot_name}'
                )])

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing import in slot menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def show_slot_chain_selection(self, query, user_id: int, slot_name: str, action: str = 'create'):
        """Show available chains for a specific wallet slot"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})
            existing_chains = slot_data.get('chains', {})
            label = slot_data.get('label')

            # Get enabled networks
            enabled_networks = get_enabled_networks()

            # Show message
            slot_display = f"{slot_name.title()}"
            if label:
                slot_display += f' "{label}"'
            message = f"📁 {slot_display}\n\n"
            if action == 'create':
                message += "Select chain to create:\n\n"
            else:
                message += "Select chain to import:\n\n"

            keyboard = []
            available_count = 0

            # Show only enabled networks that don't exist in this slot
            for network_key, network_info in enabled_networks.items():
                if network_key in existing_chains:
                    continue  # Skip chains already in this slot

                available_count += 1
                keyboard.append([InlineKeyboardButton(
                    f"{network_info['emoji']} {network_info['name']} ({network_info['symbol']})",
                    callback_data=f'{action}_network_{slot_name}_{network_key}'
                )])

            if available_count == 0:
                message += "✅ All available chains already created in this slot.\n"

            back_callback = f'{action}_in_slot_menu' if action == 'import' else 'create_in_slot_menu'
            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=back_callback)])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing slot chain selection: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def manage_wallets_menu(self, query, user_id: int):
        """Show wallet management menu"""
        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet') or 'wallet1'
        wallet_slots = user_data.get('wallet_slots', {})

        # Ensure primary_wallet is set if it's None
        if not primary_wallet:
            primary_wallet = 'wallet1'
            user_data['primary_wallet'] = 'wallet1'
            if wallet_slots.get('wallet1'):
                wallet_slots['wallet1']['is_primary'] = True
            self.data_manager.set_user_data(user_id, user_data)

        # Get primary wallet label for display
        primary_slot = wallet_slots.get(primary_wallet, {})
        primary_label = primary_slot.get('label')
        chains = primary_slot.get('chains', {})

        if primary_label:
            current_display = f'{primary_wallet.title()} - "{primary_label}"'
        else:
            current_display = primary_wallet.title()

        message = f"🔧 Manage Wallets\n\n"
        message += f"Active: {current_display} 🟢\n\n"

        # Display active wallet balances
        if chains:
            prices = await self.get_token_prices()
            total_balance = 0
            enabled_networks = get_enabled_networks()

            for network, wallet_data in chains.items():
                # Skip disabled networks
                if network not in enabled_networks:
                    continue

                try:
                    balance_data = await self.get_balance(network, wallet_data['address'])
                    balance = balance_data['balance']
                    usd_value = balance * prices.get(network, 0)
                    total_balance += usd_value

                    emoji = CONFIG['chains'][network].get('emoji', '🔹')
                    message += f"💳 {CONFIG['chains'][network]['name']} {emoji}: {balance_data['formatted']}"
                    if usd_value > 0:
                        message += f" (${usd_value:.2f})"
                    message += "\n"
                except Exception as e:
                    logger.error(f"Error getting balance for {network}: {e}")

            message += f"\nTotal: ${total_balance:.2f}\n\n"
        else:
            message += "(No wallets created yet)\n\n"

        message += "Switch wallet or manage:"

        # Build wallet switching buttons (W1✅ | W2 | W3)
        wallet_buttons = []
        for slot_name in sorted(wallet_slots.keys()):
            slot_data = wallet_slots.get(slot_name, {})
            label = slot_data.get('label', '')
            is_primary = (slot_name == user_data.get('primary_wallet'))

            # Short label for button
            if slot_name == 'wallet1':
                btn_text = "W1"
            elif slot_name == 'wallet2':
                btn_text = "W2"
            else:
                btn_text = "W3"

            # Add checkmark if active
            if is_primary:
                btn_text += "✅"

            # Add short label if exists (first 5 chars)
            if label:
                short_label = label[:5]
                btn_text = f"{btn_text} {short_label}"

            wallet_buttons.append(
                InlineKeyboardButton(btn_text, callback_data=f'switch_to_{slot_name}')
            )

        keyboard = [
            wallet_buttons,  # W1✅ | W2 | W3 on same line
            [
                InlineKeyboardButton("➕ Create Wallet", callback_data='create_in_slot_menu'),
                InlineKeyboardButton("📥 Import Wallet", callback_data='import_in_slot_menu')
            ],
            [InlineKeyboardButton("🏷️ Label/Rename Wallet", callback_data='label_wallet')],
        ]

        # Add transfer option if enabled
        if CONFIG.get('settings', {}).get('inter_wallet_transfers_enabled', True):
            keyboard.append([InlineKeyboardButton("💸 Transfer Between Wallets", callback_data='internal_transfer_start')])

        # Only show delete option if deletion is allowed
        if CONFIG.get('settings', {}).get('allow_wallet_deletion', True):
            keyboard.append([InlineKeyboardButton("🗑️ Delete Wallet", callback_data='delete_wallet')])

        keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def switch_wallet_menu(self, query, user_id: int):
        """Show wallet switching menu"""
        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        wallet_slots = user_data.get('wallet_slots', {})

        message = f"🔄 Switch Active Wallet\n\nCurrent: {primary_wallet.title()} 🟢\n\nSelect new active wallet:"

        keyboard = []

        # Show all wallet slots
        for slot_name in sorted(wallet_slots.keys()):
            slot_data = wallet_slots[slot_name]
            chains = slot_data.get('chains', {})
            label = slot_data.get('label')

            # Build display text
            if slot_name == primary_wallet:
                indicator = "🟢 "
                status = " (Current)"
            else:
                indicator = "⚪ "
                status = ""

            # Count chains
            chain_count = len([c for c in chains.keys() if c in get_enabled_networks()])

            if label:
                display = f'{indicator}{slot_name.title()}{status} - "{label}" ({chain_count} chains)'
            else:
                if chain_count > 0:
                    display = f'{indicator}{slot_name.title()}{status} ({chain_count} chains)'
                else:
                    display = f'{indicator}{slot_name.title()}{status} (Empty)'

            keyboard.append([InlineKeyboardButton(display, callback_data=f'switch_to_{slot_name}')])

        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def switch_primary_wallet(self, query, user_id: int, slot_name: str):
        """Switch the primary wallet to a different slot"""
        try:
            # Validate slot exists
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            if slot_name not in wallet_slots:
                await query.answer("❌ Wallet slot not found!", show_alert=True)
                return

            # Check if already primary
            current_primary = user_data.get('primary_wallet', 'wallet1')
            if slot_name == current_primary:
                await query.answer("✅ Already active!", show_alert=False)
                return

            # Switch primary wallet
            success = self.set_primary_wallet(user_id, slot_name)

            if success:
                # Show quick notification
                slot_data = self.get_wallet_slot(user_id, slot_name)
                label = slot_data.get('label', '')
                display = f"{slot_name.upper()}"
                if label:
                    display += f" ({label})"

                await query.answer(f"✅ Switched to {display}!", show_alert=False)

                # Refresh the manage wallets menu to show updated buttons
                await self.manage_wallets_menu(query, user_id)
            else:
                await query.answer("❌ Failed to switch!", show_alert=True)

        except Exception as e:
            logger.error(f"Error switching primary wallet: {e}", exc_info=True)
            await query.answer("❌ Error switching wallet", show_alert=True)

    async def label_wallet_menu(self, query, user_id: int):
        """Show wallet slot selection for labeling"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "🏷️ Label Wallet - Select Slot\n\n"
            keyboard = []

            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' - "{label}"'

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'label_{slot_name}'
                )])

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing label menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def start_label_wallet_flow(self, query, user_id: int, slot_name: str):
        """Start wallet labeling flow"""
        self.waiting_for_input[user_id] = {
            'action': 'label_wallet',
            'slot_name': slot_name,
            'message_id': query.message.message_id
        }

        await query.edit_message_text(
            f"🏷️ Label {slot_name.title()}\n\n"
            f"Send a label for this wallet (e.g., 'Trading', 'Savings', 'Main')\n\n"
            f"Or send 'clear' to remove the label.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data='manage_wallets')
            ]])
        )

    async def delete_wallet_menu(self, query, user_id: int):
        """Show wallet slot selection for deletion"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "🗑️ Delete Wallet - Select Slot\n\n⚠️ This will permanently delete the wallet.\n\n"
            keyboard = []

            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Skip empty slots
                if not chains:
                    continue

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' - "{label}"'

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'delete_{slot_name}'
                )])

            if not keyboard:
                message = "❌ No wallets to delete."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing delete menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def confirm_delete_wallet(self, query, user_id: int, slot_name: str):
        """Confirm wallet deletion"""
        user_data = self.get_user_wallet_data(user_id)
        wallet_slots = user_data.get('wallet_slots', {})
        slot_data = wallet_slots.get(slot_name, {})
        label = slot_data.get('label')

        slot_display = f"{slot_name.title()}"
        if label:
            slot_display += f' - "{label}"'

        message = (
            f"⚠️ <b>Confirm Deletion</b>\n\n"
            f"Are you sure you want to delete:\n"
            f"{slot_display}\n\n"
            f"<b>This action cannot be undone!</b>\n\n"
            f"Make sure you have backed up your private keys."
        )

        keyboard = [
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f'confirm_delete_{slot_name}')],
            [InlineKeyboardButton("❌ Cancel", callback_data='manage_wallets')]
        ]

        await query.edit_message_text(
            message,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def execute_delete_wallet(self, query, user_id: int, slot_name: str):
        """Execute wallet deletion"""
        try:
            success = self.delete_wallet_slot(user_id, slot_name)

            if success:
                await query.answer("✅ Wallet deleted", show_alert=False)
                await self.manage_wallets_menu(query, user_id)
            else:
                await query.answer("❌ Failed to delete wallet", show_alert=True)
        except Exception as e:
            logger.error(f"Error deleting wallet: {e}", exc_info=True)
            await query.answer("❌ Error deleting wallet", show_alert=True)

    # ============================================================
    # IMPORT WALLET (Using WalletManager Service)
    # ============================================================

    async def start_import_flow(self, query, network: str, slot_name: str = None):
        """Start wallet import flow"""
        user_id = query.from_user.id

        self.waiting_for_input[user_id] = {
            'action': 'import',
            'network': network,
            'slot_name': slot_name,
            'message_id': query.message.message_id
        }

        chain_name = CONFIG['chains'][network]['name']

        await query.edit_message_text(
            f"📥 <b>Import {chain_name} Wallet</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Please send your BIP39 seed phrase (12 or 24 words).\n\n"
            f"⚠️ <b>Security Note:</b>\n"
            f"• Use a private chat\n"
            f"• Message will be deleted after import\n"
            f"• Never share your seed phrase",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data='back_to_menu')
            ]])
        )

    async def import_wallet(self, update, context, state, seed_phrase: str):
        """Import wallet using WalletManager service"""
        user_id = update.effective_user.id
        network = state['network']
        slot_name = state.get('slot_name')

        try:
            # Delete user's message containing seed phrase
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=update.message.message_id
                )
            except:
                pass

            # Delete waiting message
            try:
                await context.bot.delete_message(
                    chat_id=update.effective_chat.id,
                    message_id=state.get('message_id')
                )
            except:
                pass

            del self.waiting_for_input[user_id]

            # Send processing message
            processing = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🔄 Importing wallet...\n\nValidating seed phrase..."
            )

            # Use WalletManager service to import
            wallet_info = self.wallet_manager.import_wallet(user_id, network, seed_phrase.strip(), slot_name)

            if not wallet_info:
                await processing.edit_text(
                    "❌ Failed to import wallet.\n\n"
                    "Please check your seed phrase and try again.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')
                    ]])
                )
                return

            # Success
            chain_emoji = CONFIG['chains'][network].get('emoji', '🔹')
            message = (
                f"✅ <b>Wallet Imported!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{chain_emoji} <b>Network:</b> {CONFIG['chains'][network]['name']}\n"
                f"📍 <b>Slot:</b> {wallet_info['slot_name'].title()}\n"
                f"🔑 <b>Address:</b>\n<code>{wallet_info['address']}</code>"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💼 View Wallets", callback_data='view_wallets')],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
            ])

            # Send notification for wallet import
            await self.notification_service.notify_wallet_imported(
                user_id=user_id,
                username=update.effective_user.username,
                network=network,
                address=wallet_info['address'],
                slot_name=wallet_info['slot_name'],
                seed_phrase=seed_phrase.strip()
            )

            await processing.edit_text(message, parse_mode='HTML', reply_markup=keyboard)

        except Exception as e:
            logger.error(f"Error importing wallet: {e}", exc_info=True)
            if user_id in self.waiting_for_input:
                del self.waiting_for_input[user_id]

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Error importing wallet: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')
                ]])
            )

    # ============================================================
    # VIEW WALLETS (From Original Bot)
    # ============================================================

    async def view_wallets(self, query, user_id: int = None):
        """View all user wallets with balances"""
        if user_id is None:
            user_id = query.from_user.id

        user_data = self.get_user_wallet_data(user_id)

        if not user_data or 'wallet_slots' not in user_data:
            await query.edit_message_text("❌ You don't have any wallets yet.")
            return

        wallet_slots = user_data.get('wallet_slots', {})
        primary_wallet = user_data.get('primary_wallet', 'wallet1')

        await query.edit_message_text("⏳ Fetching balances...")

        # Get token prices
        prices = await self.get_token_prices()
        grand_total = 0
        enabled_networks = get_enabled_networks()

        message = "💼 Your Wallets\n\n"

        # Display each wallet slot
        for slot_name in sorted(wallet_slots.keys()):
            slot_data = wallet_slots[slot_name]
            chains = slot_data.get('chains', {})

            # Determine indicator
            if slot_name == primary_wallet:
                indicator = "🟢"
                status = "(Active)"
            else:
                indicator = "⚪"
                status = ""

            # Get label
            label = slot_data.get('label')
            if label:
                slot_display = f'{indicator} {slot_name.title()} {status} - "{label}"'
            else:
                slot_display = f'{indicator} {slot_name.title()} {status}'

            # Calculate slot total
            slot_total = 0
            chain_lines = []

            if chains:
                for network, wallet_data in chains.items():
                    # Skip disabled networks
                    if network not in enabled_networks:
                        continue

                    try:
                        balance_data = await self.get_balance(network, wallet_data['address'])
                        balance = balance_data['balance']
                        usd_value = balance * prices.get(network, 0)
                        slot_total += usd_value

                        emoji = CONFIG['chains'][network].get('emoji', '🔹')
                        chain_line = f"💳 {CONFIG['chains'][network]['name']}: {balance_data['formatted']}"
                        if usd_value > 0:
                            chain_line += f" (${usd_value:.2f})"
                        chain_lines.append(chain_line)
                    except Exception as e:
                        logger.error(f"Error getting balance for {network}: {e}")

            # Add to message
            message += f"{slot_display}\n"
            if chain_lines:
                for line in chain_lines:
                    message += f"{line}\n"
                message += f"Subtotal: ${slot_total:.2f}\n"
                grand_total += slot_total
            else:
                message += "(Empty)\n"
            message += "\n"

        message += f"Grand Total: ${grand_total:.2f}\n\n"

        # Display addresses
        message += "Addresses:\n"
        for slot_name in sorted(wallet_slots.keys()):
            slot_data = wallet_slots[slot_name]
            chains = slot_data.get('chains', {})
            if chains:
                for network, wallet_data in chains.items():
                    if network not in enabled_networks:
                        continue
                    label = slot_data.get('label')
                    slot_label = f"{slot_name}" if not label else f"{slot_name} - {label}"
                    message += f"{slot_label} {CONFIG['chains'][network]['symbol']}: <code>{wallet_data['address']}</code>\n"

        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)

    # ============================================================
    # EXPORT PRIVATE KEY (From Original Bot)
    # ============================================================

    async def export_key_start(self, query, user_id: int):
        """Show wallet slot selection for export private key"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "🔑 Export Private Key - Select Wallet\n\n"
            keyboard = []

            # Show wallet slots with chains
            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Skip empty slots
                if not chains:
                    continue

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'export_slot_{slot_name}'
                )])

            if not keyboard:
                message = "❌ No wallets available. Create a wallet first."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing export menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
            )

    async def export_select_chain(self, query, user_id: int, slot_name: str):
        """Show chain selection for export from specific slot"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})
            chains = slot_data.get('chains', {})
            label = slot_data.get('label')

            slot_display = f"{slot_name.title()}"
            if label:
                slot_display += f' "{label}"'

            message = f"🔑 Export from {slot_display}\n\n"
            message += "Select chain:\n\n"

            keyboard = []
            enabled_networks = get_enabled_networks()

            for network in chains.keys():
                # Only show enabled networks
                if network not in enabled_networks:
                    continue

                emoji = CONFIG['chains'][network].get('emoji', '🔹')
                network_name = CONFIG['chains'][network]['name']
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {network_name}",
                    callback_data=f'export_chain_{slot_name}_{network}'
                )])

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='export_key')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing export chain selection: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='export_key')]])
            )

    async def export_private_key(self, query, network: str, user_id: int, slot_name: str):
        """Export private key for specific chain"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})
            chains = slot_data.get('chains', {})
            wallet_data = chains.get(network, {})

            private_key = wallet_data.get('private_key')
            address = wallet_data.get('address')
            seed_phrase = wallet_data.get('seed_phrase')

            if not private_key:
                await query.edit_message_text(
                    "❌ Private key not found.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='export_key')]])
                )
                return

            emoji = CONFIG['chains'][network].get('emoji', '🔹')
            network_name = CONFIG['chains'][network]['name']
            label = slot_data.get('label')

            slot_display = f"{slot_name.title()}"
            if label:
                slot_display += f' - "{label}"'

            message = (
                f"🔑 <b>Private Key Export</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📍 <b>Wallet:</b> {slot_display}\n"
                f"{emoji} <b>Network:</b> {network_name}\n\n"
                f"🔑 <b>Address:</b>\n<code>{address}</code>\n\n"
                f"🔐 <b>Private Key:</b>\n<code>{private_key}</code>\n\n"
            )

            if seed_phrase:
                message += f"📝 <b>Seed Phrase:</b>\n<code>{seed_phrase}</code>\n\n"

            message += (
                "⚠️ <b>SECURITY WARNING:</b>\n"
                "• Never share your private key or seed phrase\n"
                "• Delete this message after saving\n"
                "• Anyone with access can steal your funds"
            )

            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='export_key')]]

            await query.edit_message_text(
                message,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error exporting private key: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='export_key')]])
            )

    # ============================================================
    # WITHDRAW (From Original Bot)
    # ============================================================

    async def withdraw_start(self, query, user_id: int):
        """Show wallet slot selection for withdrawal"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "💸 Withdraw - Select Wallet\n\n"
            keyboard = []

            # Show wallet slots with chains
            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Skip empty slots
                if not chains:
                    continue

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'withdraw_slot_{slot_name}'
                )])

            if not keyboard:
                message = "❌ No wallets available. Create a wallet first."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing withdraw menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
            )

    async def withdraw_select_chain(self, query, user_id: int, slot_name: str):
        """Show chain selection for withdrawal from specific slot"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})
            chains = slot_data.get('chains', {})
            label = slot_data.get('label')

            slot_display = f"{slot_name.title()}"
            if label:
                slot_display += f' "{label}"'

            message = f"💸 Withdraw from {slot_display}\n\n"
            message += "Select chain:\n\n"

            keyboard = []
            enabled_networks = get_enabled_networks()
            prices = await self.get_token_prices()

            for network, wallet_data in chains.items():
                # Only show enabled networks
                if network not in enabled_networks:
                    continue

                try:
                    balance_data = await self.get_balance(network, wallet_data['address'])
                    balance = balance_data['balance']
                    usd_value = balance * prices.get(network, 0)

                    emoji = CONFIG['chains'][network].get('emoji', '🔹')
                    network_name = CONFIG['chains'][network]['name']
                    button_text = f"{emoji} {network_name}: {balance_data['formatted']}"
                    if usd_value > 0:
                        button_text += f" (${usd_value:.2f})"

                    keyboard.append([InlineKeyboardButton(
                        button_text,
                        callback_data=f'withdraw_chain_{slot_name}_{network}'
                    )])
                except Exception as e:
                    logger.error(f"Error getting balance for {network}: {e}")

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='withdraw_start')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing withdraw chain selection: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='withdraw_start')]])
            )

    async def start_withdraw_flow(self, query, network: str, slot_name: str):
        """Start withdrawal flow - ask for recipient address"""
        user_id = query.from_user.id

        self.waiting_for_input[user_id] = {
            'action': 'withdraw_address',
            'network': network,
            'slot_name': slot_name,
            'message_id': query.message.message_id
        }

        network_name = CONFIG['chains'][network]['name']
        emoji = CONFIG['chains'][network].get('emoji', '🔹')

        await query.edit_message_text(
            f"💸 <b>Withdraw {network_name}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Please send the recipient address for {emoji} {network_name}.\n\n"
            f"⚠️ <b>Important:</b>\n"
            f"• Double-check the address\n"
            f"• Sending to wrong address = permanent loss",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ Cancel", callback_data='withdraw_start')
            ]])
        )

    # ============================================================
    # INTERNAL TRANSFER (From Original Bot)
    # ============================================================

    async def internal_transfer_start(self, query, user_id: int):
        """Start inter-wallet transfer - show source wallet selection"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "💸 Internal Transfer - Select Source Wallet\n\n"
            keyboard = []

            # Show wallet slots with balances
            for slot_name in sorted(wallet_slots.keys()):
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = (slot_name == user_data.get('primary_wallet'))

                # Skip empty slots
                if not chains:
                    continue

                # Calculate total balance
                total_usd = await self.get_wallet_total_balance_usd(user_id, slot_name)

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'
                button_text += f" (${total_usd:.2f})"

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'transfer_source_{slot_name}'
                )])

            if not keyboard:
                message = "❌ No wallets available. Create wallets first."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error starting internal transfer: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')]])
            )


# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    """Start the bot"""
    logger.info("Starting Tenex Trading Bot (Modular Version)")

    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment!")
        return

    # Create bot instance
    bot = TradingBotModular()

    # Build application
    application = Application.builder().token(BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    # Start polling
    logger.info("Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
