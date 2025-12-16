"""
Telegram Trading Bot - Wallet Management
Manages crypto wallets for SOL, Stacks, and ETH networks
"""

import os
import csv
import json
import logging
import re
import ssl
import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv, set_key
from eth_account import Account
from web3 import Web3
from solders.keypair import Keypair
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins, Bip44Changes
from typing import Optional, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

# Import Jupiter Swap
from jupiter_swap import JupiterSwap, TOKENS as JUPITER_TOKENS, sol_to_lamports

# Import Trading Integration
from trading_integration import TradingMixin

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Custom SSL adapter for compatibility with various SSL/TLS servers
class SSLAdapter(HTTPAdapter):
    """Custom HTTPAdapter with modern TLS configuration"""
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.load_default_certs()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

# Create a session with custom SSL adapter
def create_secure_session():
    """Create a requests session with proper SSL/TLS configuration"""
    session = requests.Session()
    session.mount('https://', SSLAdapter())
    return session

# Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID', '0'))
WALLETS_DIR = Path('wallets')
USER_WALLETS_FILE = WALLETS_DIR / 'user_wallets.json'
ENV_FILE = Path('.env')
CONFIG_FILE = Path('config.json')

# Load configuration from file
def load_config():
    """Load chain configuration from config.json"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config
    else:
        logger.error("config.json not found! Using default configuration.")
        # Fallback to default config
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
                'max_wallets_per_user': 3,
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
    """Get only enabled networks"""
    return {k: v for k, v in NETWORKS.items() if v.get('enabled', True)}

# DexScreener configuration
DEXSCREENER_BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"
SUPPORTED_CHAINS = [
    chain['dexscreener_chain']
    for chain in NETWORKS.values()
    if chain.get('enabled', True) and chain.get('dexscreener_chain')
]

class TradingBot(TradingMixin):
    def __init__(self):
        self.waiting_for_input = {}
        self.user_wallets = self.load_user_wallets()
        # Trading context: stores active token trades for each user
        self.trading_context = {}  # {user_id: {token_address, chain, slippage, etc}}
        # Orders tracking: stores pending/completed orders
        self.user_orders = {}  # {user_id: [{order_id, token, amount, status, etc}]}

    def load_user_wallets(self):
        """Load user wallet assignments"""
        if USER_WALLETS_FILE.exists():
            with open(USER_WALLETS_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_user_wallets(self):
        """Save user wallet assignments"""
        with open(USER_WALLETS_FILE, 'w') as f:
            json.dump(self.user_wallets, f, indent=2)

    def needs_migration(self, user_id_str: str) -> bool:
        """Check if user data needs migration to new multi-wallet format"""
        if user_id_str not in self.user_wallets:
            return False

        user_data = self.user_wallets[user_id_str]

        # Old format has 'wallets' but not 'wallet_slots'
        return 'wallets' in user_data and 'wallet_slots' not in user_data

    def migrate_user_data(self, user_id_str: str) -> bool:
        """Migrate user from old single-wallet to new multi-wallet structure"""
        if user_id_str not in self.user_wallets:
            return False

        user_data = self.user_wallets[user_id_str]

        if 'wallets' not in user_data:
            return False  # Nothing to migrate

        # Get max slots from config
        max_slots = CONFIG.get('settings', {}).get('max_wallet_slots_per_user', 3)

        # Create new structure
        new_data = {
            'primary_wallet': 'wallet1',
            'wallet_slots': {}
        }

        # Migrate existing wallets to wallet1
        new_data['wallet_slots']['wallet1'] = {
            'label': None,
            'created_at': datetime.datetime.now().isoformat(),
            'is_primary': True,
            'chains': user_data['wallets']  # Move old wallets here
        }

        # Initialize empty wallet slots
        for i in range(2, max_slots + 1):
            slot_name = f'wallet{i}'
            new_data['wallet_slots'][slot_name] = {
                'label': None,
                'created_at': None,
                'is_primary': False,
                'chains': {}
            }

        # Keep backup of old data
        new_data['_old_wallets'] = user_data['wallets']
        new_data['_migrated'] = True
        new_data['_migrated_at'] = datetime.datetime.now().isoformat()

        # Replace user data
        self.user_wallets[user_id_str] = new_data
        self.save_user_wallets()

        logger.info(f"Migrated user {user_id_str} to multi-wallet structure")
        return True

    def get_user_wallet_data(self, user_id: int) -> dict:
        """Get user wallet data, auto-migrating if needed"""
        user_id_str = str(user_id)

        if self.needs_migration(user_id_str):
            self.migrate_user_data(user_id_str)

        return self.user_wallets.get(user_id_str, {})

    def get_primary_wallet(self, user_id: int) -> str:
        """Get the primary wallet slot name for a user"""
        user_data = self.get_user_wallet_data(user_id)
        return user_data.get('primary_wallet', 'wallet1')

    def get_wallet_slot(self, user_id: int, slot_name: str) -> dict:
        """Get specific wallet slot data"""
        user_data = self.get_user_wallet_data(user_id)
        wallet_slots = user_data.get('wallet_slots', {})
        return wallet_slots.get(slot_name, {})

    def set_primary_wallet(self, user_id: int, slot_name: str) -> bool:
        """Set a wallet slot as primary"""
        user_id_str = str(user_id)
        user_data = self.get_user_wallet_data(user_id)

        if 'wallet_slots' not in user_data:
            return False

        if slot_name not in user_data['wallet_slots']:
            return False

        # Update primary_wallet field
        user_data['primary_wallet'] = slot_name

        # Update is_primary flags on all slots
        for slot in user_data['wallet_slots'].values():
            slot['is_primary'] = False

        user_data['wallet_slots'][slot_name]['is_primary'] = True

        # Save changes
        self.user_wallets[user_id_str] = user_data
        self.save_user_wallets()

        logger.info(f"Set {slot_name} as primary wallet for user {user_id}")
        return True

    def get_available_wallet_slots(self, user_id: int) -> list:
        """Get list of available (empty or partially filled) wallet slots"""
        user_data = self.get_user_wallet_data(user_id)
        wallet_slots = user_data.get('wallet_slots', {})

        available_slots = []
        for slot_name, slot_data in wallet_slots.items():
            # Slot is available if it has no chains or has fewer chains than enabled networks
            chains = slot_data.get('chains', {})
            enabled_networks = get_enabled_networks()
            if len(chains) < len(enabled_networks):
                available_slots.append(slot_name)

        return available_slots

    def delete_wallet_slot(self, user_id: int, slot_name: str) -> bool:
        """Delete a wallet slot (clear all chain data)"""
        user_id_str = str(user_id)
        user_data = self.get_user_wallet_data(user_id)

        if 'wallet_slots' not in user_data:
            return False

        if slot_name not in user_data['wallet_slots']:
            return False

        # Validation: Cannot delete primary wallet
        if user_data.get('primary_wallet') == slot_name:
            raise Exception("Cannot delete primary wallet. Please switch to another wallet first.")

        # Validation: Cannot delete if it's the only wallet with chains
        non_empty_slots = [
            s for s, data in user_data['wallet_slots'].items()
            if data.get('chains', {})
        ]

        if len(non_empty_slots) <= 1 and user_data['wallet_slots'][slot_name].get('chains', {}):
            raise Exception("Cannot delete your only wallet")

        # Clear the slot
        user_data['wallet_slots'][slot_name] = {
            'label': None,
            'created_at': None,
            'is_primary': False,
            'chains': {}
        }

        # Save changes
        self.user_wallets[user_id_str] = user_data
        self.save_user_wallets()

        logger.info(f"Deleted wallet slot {slot_name} for user {user_id}")
        return True

    async def get_wallet_total_balance_usd(self, user_id: int, slot_name: str) -> float:
        """Calculate total USD value of all chains in a wallet slot"""
        slot_data = self.get_wallet_slot(user_id, slot_name)
        chains = slot_data.get('chains', {})

        if not chains:
            return 0.0

        # Get current prices
        prices = await self.get_token_prices()
        total_usd = 0.0

        # Calculate balance for each chain
        for network, wallet_data in chains.items():
            if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                continue

            try:
                balance_data = await self.get_balance(network, wallet_data['address'])
                balance = balance_data.get('balance', 0)
                price = prices.get(network, 0)
                total_usd += balance * price
            except Exception as e:
                logger.error(f"Error getting balance for {network} in slot {slot_name}: {e}")

        return total_usd

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
        for user_data in self.user_wallets.values():
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
        if self.needs_migration(user_id_str):
            self.migrate_user_data(user_id_str)

        # Get wallet slot (default to primary if not specified)
        if slot_name is None:
            slot_name = self.get_primary_wallet(user_id)

        # Check if wallet already exists in this slot
        if user_id_str in self.user_wallets:
            wallet_slots = self.user_wallets[user_id_str].get('wallet_slots', {})
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
        if user_id_str not in self.user_wallets:
            max_slots = CONFIG.get('settings', {}).get('max_wallet_slots_per_user', 3)
            self.user_wallets[user_id_str] = {
                'primary_wallet': 'wallet1',
                'wallet_slots': {}
            }
            # Initialize all slots
            for i in range(1, max_slots + 1):
                slot = f'wallet{i}'
                self.user_wallets[user_id_str]['wallet_slots'][slot] = {
                    'label': None,
                    'created_at': None,
                    'is_primary': (slot == 'wallet1'),
                    'chains': {}
                }

        # Initialize slot if it doesn't exist
        if slot_name not in self.user_wallets[user_id_str]['wallet_slots']:
            self.user_wallets[user_id_str]['wallet_slots'][slot_name] = {
                'label': None,
                'created_at': datetime.datetime.now().isoformat(),
                'is_primary': slot_name == self.get_primary_wallet(user_id),
                'chains': {}
            }

        # Update created_at if this is the first chain in the slot
        if not self.user_wallets[user_id_str]['wallet_slots'][slot_name].get('chains'):
            self.user_wallets[user_id_str]['wallet_slots'][slot_name]['created_at'] = datetime.datetime.now().isoformat()

        # Add wallet to slot
        self.user_wallets[user_id_str]['wallet_slots'][slot_name]['chains'][network] = wallet
        self.save_user_wallets()

        logger.info(f"Assigned {network} wallet to user {user_id} in {slot_name}")
        return wallet

    async def get_token_prices(self):
        """Get current token prices in USD"""
        try:
            # Get CoinGecko IDs for enabled chains
            enabled_networks = get_enabled_networks()
            coingecko_ids = [
                network['coingecko_id']
                for network in enabled_networks.values()
                if network.get('coingecko_id')
            ]

            if not coingecko_ids:
                return {}

            ids = ','.join(coingecko_ids)
            url = f'https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd'
            session = create_secure_session()
            response = session.get(url, timeout=10)
            data = response.json()

            # Map back to network keys
            prices = {}
            for network_key, network in enabled_networks.items():
                coingecko_id = network.get('coingecko_id')
                if coingecko_id:
                    prices[network_key] = data.get(coingecko_id, {}).get('usd', 0)
                else:
                    prices[network_key] = 0

            return prices
        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {k: 0 for k in get_enabled_networks().keys()}

    async def get_balance(self, network: str, address: str):
        """Get balance for an address on a specific network"""
        try:
            logger.info(f"Fetching balance for {network} address: {address}")
            if network == 'SOL':
                return await self.get_solana_balance(address)
            elif network == 'ETH':
                return await self.get_ethereum_balance(address)
            elif network == 'STACKS':
                return await self.get_stacks_balance(address)
        except Exception as e:
            logger.error(f"Error getting balance for {network}: {e}", exc_info=True)
            return {'balance': 0, 'formatted': 'Error'}

    async def get_solana_balance(self, address: str):
        """Get Solana balance"""
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            session = create_secure_session()
            response = session.post(NETWORKS['SOL']['rpc'], json=payload, timeout=10)
            data = response.json()

            if 'result' in data and 'value' in data['result']:
                balance_lamports = data['result']['value']
                balance_sol = balance_lamports / 1_000_000_000
                return {
                    'balance': balance_sol,
                    'formatted': f"{balance_sol:.6f} SOL"
                }
            return {'balance': 0, 'formatted': '0 SOL'}
        except Exception as e:
            logger.error(f"Solana balance error: {e}")
            return {'balance': 0, 'formatted': 'Error'}

    async def get_ethereum_balance(self, address: str):
        """Get Ethereum balance"""
        try:
            w3 = Web3(Web3.HTTPProvider(NETWORKS['ETH']['rpc']))
            balance_wei = w3.eth.get_balance(address)
            balance_eth = w3.from_wei(balance_wei, 'ether')
            return {
                'balance': float(balance_eth),
                'formatted': f"{balance_eth:.6f} ETH"
            }
        except Exception as e:
            logger.error(f"Ethereum balance error: {e}")
            return {'balance': 0, 'formatted': 'Error'}

    async def get_stacks_balance(self, address: str):
        """Get Stacks balance"""
        try:
            # Check if address is valid (Stacks addresses start with SP or SM)
            if not address or address.startswith('Stacks address derivation'):
                logger.warning(f"Invalid Stacks address: {address}")
                return {'balance': 0, 'formatted': 'N/A (Import not supported)'}

            url = f"{NETWORKS['STACKS']['rpc']}/v2/accounts/{address}"
            logger.info(f"Fetching Stacks balance from: {url}")

            # Use secure session for SSL/TLS compatibility
            session = create_secure_session()
            response = session.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"Stacks API error: {response.status_code}, Response: {response.text}")
                return {'balance': 0, 'formatted': '0 STX'}

            data = response.json()
            logger.info(f"Stacks API response: {data}")

            # Stacks API returns balance in the "balance" field (in microSTX)
            if 'balance' in data:
                balance_ustx = int(data['balance'], 16) if isinstance(data['balance'], str) else int(data['balance'])
                balance_stx = balance_ustx / 1_000_000
                return {
                    'balance': balance_stx,
                    'formatted': f"{balance_stx:.6f} STX"
                }
            return {'balance': 0, 'formatted': '0 STX'}
        except Exception as e:
            logger.error(f"Stacks balance error: {e}", exc_info=True)
            return {'balance': 0, 'formatted': 'Error'}

    def derive_address_from_seed(self, seed_phrase: str, network: str, index: int = 0):
        """Derive main wallet address from seed phrase"""
        try:
            seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()

            if network == 'SOL':
                bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
                bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
                bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
                bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

                private_key_bytes = bip44_addr_ctx.PrivateKey().Raw().ToBytes()
                keypair = Keypair.from_bytes(private_key_bytes[:32])

                return {
                    'address': str(keypair.pubkey()),
                    'private_key': private_key_bytes.hex()
                }

            elif network == 'ETH':
                bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
                bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
                bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
                bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

                private_key = bip44_addr_ctx.PrivateKey().Raw().ToHex()
                account = Account.from_key(private_key)

                return {
                    'address': account.address,
                    'private_key': private_key
                }

            elif network == 'STACKS':
                bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
                bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
                bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
                bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

                private_key = bip44_addr_ctx.PrivateKey().Raw().ToHex()

                return {
                    'address': 'Stacks address derivation requires additional setup',
                    'private_key': private_key
                }

        except Exception as e:
            logger.error(f"Error deriving address: {e}")
            return None

    def is_contract_address(self, text: str) -> bool:
        """Check if the text appears to be a contract address"""
        # Remove whitespace
        text = text.strip()

        # Most blockchain addresses are 32-44 characters alphanumeric
        # Solana: 32-44 base58
        # Ethereum: 42 characters starting with 0x
        # General pattern: alphanumeric string between 32-66 characters

        if len(text) < 26 or len(text) > 66:
            return False

        # Check if it's mostly alphanumeric (allowing 0x prefix)
        clean_text = text.replace('0x', '').replace('0X', '')

        # Must be mostly alphanumeric
        if not re.match(r'^[a-zA-Z0-9]+$', clean_text):
            return False

        # Should have a mix of letters and numbers (not just numbers)
        has_letter = bool(re.search(r'[a-zA-Z]', clean_text))
        has_number = bool(re.search(r'[0-9]', clean_text))

        return has_letter and has_number

    async def detect_and_fetch_token(self, token_address: str) -> Optional[Dict[str, Any]]:
        """Auto-detect chain and fetch token data from DexScreener"""
        try:
            # DexScreener API endpoint - searches across all chains
            url = f"{DEXSCREENER_BASE_URL}/{token_address}"

            logger.info(f"Fetching token data from: {url}")

            # Try to use aiohttp for async request
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=10) as response:
                        if response.status != 200:
                            logger.error(f"DexScreener API returned status {response.status}")
                            return None

                        data = await response.json()

            except ImportError:
                # Fallback to requests
                logger.info("aiohttp not available, using requests")
                session = create_secure_session()
                response = session.get(url, timeout=10)

                if response.status_code != 200:
                    logger.error(f"DexScreener API returned status {response.status_code}")
                    return None

                data = response.json()

            logger.info(f"DexScreener response: {data}")

            # Check if we have valid data
            if not data or 'pairs' not in data:
                logger.error("No pairs found in DexScreener response")
                return None

            pairs = data.get('pairs', [])
            if len(pairs) == 0:
                logger.error("Empty pairs list")
                return None

            # Filter by supported chains (prioritize order: solana, ethereum)
            for chain in SUPPORTED_CHAINS:
                for pair in pairs:
                    chain_id = pair.get('chainId', '').lower()
                    if chain_id == chain:
                        logger.info(f"Found pair on {chain}: {pair.get('pairAddress')}")
                        return {'chain': chain, 'data': pair}

            # If no match in supported chains, return first pair
            logger.info(f"No exact chain match, using first pair from {pairs[0].get('chainId')}")
            return {'chain': pairs[0].get('chainId', 'unknown'), 'data': pairs[0]}

        except Exception as e:
            logger.error(f"Error in detect_and_fetch_token: {e}", exc_info=True)
            return None

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
            # Note: Would need token ID for accurate link, using search as fallback
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
                f"<b>Tenet Trading Bot #1 V1.2</b>\n"
                f"<b>The Ultimate Degen Trading Partner</b>\n\n"
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
                    InlineKeyboardButton("🔄 Refresh", callback_data=f'refresh_{token_address}')
                ])
                keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')])

                reply_markup = InlineKeyboardMarkup(keyboard)
                # Update message with buttons
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

    async def get_main_menu_keyboard(self, user_id: int):
        """Generate main menu keyboard based on user's wallets"""
        user_data = self.get_user_wallet_data(user_id)

        keyboard = []

        # Check if user has any wallets
        has_wallets = False
        if user_data and 'wallet_slots' in user_data:
            for slot_data in user_data['wallet_slots'].values():
                if slot_data.get('chains'):
                    has_wallets = True
                    break

        if has_wallets:
            # User has wallets
            keyboard.append([InlineKeyboardButton("🔄 Refresh Balance", callback_data='refresh_balance')])
            keyboard.append([InlineKeyboardButton("🎒 View Bags", callback_data='view_bags')])
            keyboard.append([InlineKeyboardButton("👛 View All Wallets", callback_data='view_wallets')])
            keyboard.append([InlineKeyboardButton("🔧 Manage Wallets", callback_data='manage_wallets')])

            # Check if inter-wallet transfers are enabled
            if CONFIG.get('settings', {}).get('inter_wallet_transfers_enabled', True):
                keyboard.append([InlineKeyboardButton("💸 Transfer Between Wallets", callback_data='internal_transfer_start')])

            keyboard.append([InlineKeyboardButton("📤 Withdraw", callback_data='withdraw_start')])
            keyboard.append([InlineKeyboardButton("🔑 Export Private Key", callback_data='export_key')])
        else:
            # User has no wallets - show Create and Import on same line
            keyboard.append([
                InlineKeyboardButton("➕ Create Wallet", callback_data='create_start'),
                InlineKeyboardButton("📥 Import Wallet", callback_data='import_start')
            ])

        return InlineKeyboardMarkup(keyboard)

    async def manage_wallets_menu(self, query, user_id: int):
        """Show wallet management menu"""
        user_data = self.get_user_wallet_data(user_id)
        primary_wallet = user_data.get('primary_wallet', 'wallet1')
        wallet_slots = user_data.get('wallet_slots', {})

        # Get primary wallet label for display
        primary_slot = wallet_slots.get(primary_wallet, {})
        primary_label = primary_slot.get('label')
        if primary_label:
            current_display = f'{primary_wallet.title()} - "{primary_label}"'
        else:
            current_display = primary_wallet.title()

        message = (
            f"🔧 Manage Wallets\n\n"
            f"Active: {current_display} 🟢\n\n"
            f"Switch wallet or manage:"
        )

        # Build wallet switching buttons (W1✅ | W2 | W3)
        wallet_buttons = []
        for slot_name in ['wallet1', 'wallet2', 'wallet3']:
            slot_data = wallet_slots.get(slot_name, {})
            label = slot_data.get('label', '')
            is_primary = slot_data.get('is_primary', False)

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
            [InlineKeyboardButton("🏷️ Label/Rename Wallet", callback_data='label_wallet_menu')],
        ]

        # Add transfer option if enabled
        if CONFIG.get('settings', {}).get('inter_wallet_transfers_enabled', True):
            keyboard.append([InlineKeyboardButton("💸 Transfer Between Wallets", callback_data='internal_transfer_start')])

        # Only show delete option if deletion is allowed
        if CONFIG.get('settings', {}).get('allow_wallet_deletion', True):
            keyboard.append([InlineKeyboardButton("🗑️ Delete Wallet", callback_data='delete_wallet_menu')])

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

    async def create_in_slot_menu(self, query, user_id: int):
        """Show wallet slot selection for creating new wallets"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "📁 Select wallet slot to create chain in:\n\n"
            keyboard = []

            # Show all wallet slots with their chain counts
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

                # Count enabled chains in this slot
                enabled_chains = {k: v for k, v in chains.items() if k in NETWORKS and NETWORKS[k].get('enabled', True)}
                chain_count = len(enabled_chains)
                total_enabled = len(get_enabled_networks())

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'
                button_text += f" ({chain_count}/{total_enabled} chains)"

                message += f"{button_text}\n"

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'select_slot_{slot_name}'
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

    async def show_slot_chain_selection(self, query, user_id: int, slot_name: str):
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
            message += "Select chain to create:\n\n"

            keyboard = []
            available_count = 0

            # Show only enabled networks that don't exist in this slot
            for network_key, network_info in enabled_networks.items():
                if network_key in existing_chains:
                    continue  # Skip chains already in this slot

                available_count += 1
                keyboard.append([InlineKeyboardButton(
                    f"{network_info['emoji']} {network_info['name']} ({network_info['symbol']})",
                    callback_data=f'create_slot_{slot_name}_{network_key.lower()}'
                )])

            if available_count == 0:
                message += "✅ All available chains already created in this slot.\n"

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='create_in_slot_menu')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing slot chain selection: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='create_in_slot_menu')]])
            )

    async def import_in_slot_menu(self, query, user_id: int):
        """Show wallet slot selection for importing wallets"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "📥 Import Wallet - Select Slot\n\n"
            keyboard = []

            # Show all wallet slots with their chain counts
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

                # Count enabled chains in this slot
                enabled_chains = {k: v for k, v in chains.items() if k in NETWORKS and NETWORKS[k].get('enabled', True)}
                chain_count = len(enabled_chains)
                total_enabled = len(get_enabled_networks())

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'
                button_text += f" ({chain_count}/{total_enabled} chains)"

                message += f"{button_text}\n"

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'import_select_slot_{slot_name}'
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

    async def show_slot_chain_selection_for_import(self, query, user_id: int, slot_name: str):
        """Show available chains for importing in specific wallet slot"""
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
            message = f"📥 Import into {slot_display}\n\n"
            message += "Select chain to import:\n\n"

            keyboard = []
            available_count = 0

            # Show only enabled networks that don't exist in this slot AND support import
            for network_key, network_info in enabled_networks.items():
                # Skip if chain already exists in this slot
                if network_key in existing_chains:
                    continue

                # Skip if import not supported for this chain
                if not network_info.get('import_supported', True):
                    continue

                available_count += 1
                keyboard.append([InlineKeyboardButton(
                    f"{network_info['emoji']} {network_info['name']} ({network_info['symbol']})",
                    callback_data=f'import_slot_{slot_name}_{network_key.lower()}'
                )])

            if available_count == 0:
                message += "✅ All importable chains already exist in this slot.\n"

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='import_in_slot_menu')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing slot chain selection for import: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='import_in_slot_menu')]])
            )

    async def label_wallet_menu(self, query, user_id: int):
        """Show wallet slot selection for labeling"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "🏷️ Select wallet to label/rename:\n\n"
            keyboard = []

            # Show all wallet slots
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

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
                    callback_data=f'label_{slot_name}'
                )])

            if not keyboard:
                message = "❌ No wallets to label. Create a wallet first."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing label wallet menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def start_label_wallet_flow(self, query, user_id: int, slot_name: str):
        """Start the wallet labeling flow - prompt for label text"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})

            if not slot_data or not slot_data.get('chains'):
                await query.edit_message_text(
                    f"❌ {slot_name.title()} doesn't exist or is empty.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='label_wallet_menu')]])
                )
                return

            current_label = slot_data.get('label', 'None')

            message = f"🏷️ Label for {slot_name.title()}\n\n"
            message += f"Current label: {current_label}\n\n"
            message += "Please send a new label (max 20 characters).\n"
            message += "Send 'clear' to remove the label."

            # Set waiting state
            self.waiting_for_input[user_id] = {
                'action': 'label_wallet',
                'slot_name': slot_name
            }

            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='label_wallet_menu')]]
            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error starting label wallet flow: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='label_wallet_menu')]])
            )

    def set_wallet_label(self, user_id: int, slot_name: str, label: str) -> bool:
        """Set or clear wallet label"""
        try:
            user_id_str = str(user_id)
            user_data = self.get_user_wallet_data(user_id)

            if 'wallet_slots' not in user_data:
                return False

            if slot_name not in user_data['wallet_slots']:
                return False

            # Clear label if 'clear' or empty
            if label.lower() == 'clear' or not label.strip():
                user_data['wallet_slots'][slot_name]['label'] = None
            else:
                # Limit to 20 characters
                label = label.strip()[:20]
                user_data['wallet_slots'][slot_name]['label'] = label

            # Save to file
            self.user_wallets[user_id_str] = user_data
            self.save_user_wallets()

            return True
        except Exception as e:
            logger.error(f"Error setting wallet label: {e}", exc_info=True)
            return False

    async def delete_wallet_menu(self, query, user_id: int):
        """Show wallet slot selection for deletion"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            primary_wallet = user_data.get('primary_wallet', 'wallet1')

            message = "🗑️ Select wallet to delete:\n\n"
            message += "⚠️ Warning: This will permanently remove all chain data from the wallet slot.\n\n"
            keyboard = []

            # Count non-empty wallets
            non_empty_count = sum(1 for slot in wallet_slots.values() if slot.get('chains'))

            # Show all wallet slots
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

                # Skip empty slots
                if not chains:
                    continue

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' - "{label}"'

                # Check if can be deleted
                if is_primary:
                    button_text += " (Switch first)"
                    # Disabled - cannot delete primary
                    continue
                elif non_empty_count == 1:
                    button_text += " (Last wallet)"
                    # Disabled - cannot delete only wallet
                    continue

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'delete_wallet_{slot_name}'
                )])

            if not keyboard:
                if non_empty_count == 1:
                    message = "❌ Cannot delete your only wallet.\n\n"
                    message += "💡 Create additional wallets first, or switch the primary wallet before deleting."
                else:
                    message = "❌ No wallets available for deletion.\n\n"
                    message += "💡 Switch the primary wallet first to delete it."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')])

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing delete wallet menu: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='manage_wallets')]])
            )

    async def confirm_delete_wallet(self, query, user_id: int, slot_name: str):
        """Show confirmation dialog for wallet deletion"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})

            if not slot_data or not slot_data.get('chains'):
                await query.edit_message_text(
                    f"❌ {slot_name.title()} doesn't exist or is already empty.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='delete_wallet_menu')]])
                )
                return

            # Check if primary (shouldn't happen, but double-check)
            if slot_data.get('is_primary', False):
                await query.edit_message_text(
                    f"❌ Cannot delete primary wallet. Please switch to a different wallet first.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='delete_wallet_menu')]])
                )
                return

            # Calculate total balance
            total_usd = await self.get_wallet_total_balance_usd(user_id, slot_name)

            # Build confirmation message
            label = slot_data.get('label')
            message = f"🗑️ Delete {slot_name.title()}"
            if label:
                message += f' - "{label}"'
            message += "?\n\n"

            # Show balances
            chains = slot_data.get('chains', {})
            prices = await self.get_token_prices()

            message += "Current balances:\n"
            for network, wallet_data in chains.items():
                if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                    continue

                try:
                    balance_data = await self.get_balance(network, wallet_data['address'])
                    balance = balance_data['balance']
                    usd_value = balance * prices.get(network, 0)

                    emoji = NETWORKS[network].get('emoji', '🔹')
                    message += f"  {emoji} {NETWORKS[network]['name']}: {balance_data['formatted']}"
                    if usd_value > 0:
                        message += f" (${usd_value:.2f})"
                    message += "\n"
                except Exception as e:
                    logger.error(f"Error getting balance for {network}: {e}")

            message += f"\n💰 Total Value: ${total_usd:.2f}\n\n"

            # Warning
            if total_usd > 0.01:
                message += "⚠️ WARNING: This wallet has funds!\n"
                message += "⚠️ Make sure to withdraw or transfer funds before deleting.\n\n"

            message += "⚠️ This action will:\n"
            message += "• Remove all chain addresses from this slot\n"
            message += "• Delete all private keys\n"
            message += "• Make this slot available for reuse\n\n"
            message += "This action cannot be undone!"

            keyboard = [
                [InlineKeyboardButton("❌ Cancel", callback_data='delete_wallet_menu')],
                [InlineKeyboardButton("⚠️ Confirm Delete", callback_data=f'confirm_delete_{slot_name}')]
            ]

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error showing delete confirmation: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='delete_wallet_menu')]])
            )

    async def execute_delete_wallet(self, query, user_id: int, slot_name: str):
        """Execute wallet deletion after confirmation"""
        try:
            # Perform deletion using existing helper method
            success = self.delete_wallet_slot(user_id, slot_name)

            if success:
                message = f"✅ {slot_name.title()} has been deleted.\n\n"
                message += f"The slot is now empty and can be reused."

                keyboard = [
                    [InlineKeyboardButton("➕ Create New Wallet", callback_data='create_in_slot_menu')],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
                ]

                await query.edit_message_text(
                    message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to delete {slot_name.title()}. Please try again.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='delete_wallet_menu')]])
                )
        except Exception as e:
            logger.error(f"Error executing wallet deletion: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='delete_wallet_menu')]])
            )

    async def internal_transfer_start(self, query, user_id: int):
        """Start inter-wallet transfer - show source wallet selection"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "💸 Internal Transfer - Select Source Wallet\n\n"
            keyboard = []

            # Show wallet slots with balances
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

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

    async def internal_transfer_select_source(self, query, user_id: int, source_slot: str):
        """Show chain selection for source wallet"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(source_slot, {})
            chains = slot_data.get('chains', {})
            label = slot_data.get('label')

            slot_display = f"{source_slot.title()}"
            if label:
                slot_display += f' "{label}"'

            message = f"💸 Transfer from {slot_display}\n\n"
            message += "Select chain to transfer:\n\n"

            keyboard = []
            prices = await self.get_token_prices()

            for network, wallet_data in chains.items():
                if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                    continue

                try:
                    balance_data = await self.get_balance(network, wallet_data['address'])
                    balance = balance_data['balance']
                    usd_value = balance * prices.get(network, 0)

                    emoji = NETWORKS[network].get('emoji', '🔹')
                    button_text = f"{emoji} {NETWORKS[network]['name']}: {balance_data['formatted']}"
                    if usd_value > 0:
                        button_text += f" (${usd_value:.2f})"

                    # Only show chains with balance > 0
                    if balance > 0:
                        keyboard.append([InlineKeyboardButton(
                            button_text,
                            callback_data=f'transfer_chain_{network.lower()}'
                        )])
                except Exception as e:
                    logger.error(f"Error getting balance for {network}: {e}")

            if not keyboard:
                message += "❌ No chains with balance to transfer."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')])

            # Store source in waiting state
            self.waiting_for_input[user_id] = {
                'action': 'internal_transfer',
                'source_slot': source_slot,
                'step': 'select_chain'
            }

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error selecting transfer source: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')]])
            )

    async def internal_transfer_select_chain(self, query, user_id: int, network: str):
        """Show destination wallet selection"""
        try:
            state = self.waiting_for_input.get(user_id, {})
            source_slot = state.get('source_slot')

            if not source_slot:
                await query.edit_message_text(
                    "❌ Error: Transfer state lost. Please start again.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')]])
                )
                return

            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = f"💸 Transfer {NETWORKS[network]['name']} from {source_slot.title()}\n\n"
            message += "Select destination wallet:\n\n"

            keyboard = []

            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                # Skip source wallet
                if slot_name == source_slot:
                    continue

                slot_data = wallet_slots.get(slot_name, {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

                # Skip if slot doesn't exist (need at least created_at)
                if not slot_data.get('chains') and not slot_data.get('created_at'):
                    continue

                # Build button text
                indicator = "🟢" if is_primary else "⚪"
                button_text = f"{indicator} {slot_name.title()}"
                if label:
                    button_text += f' "{label}"'

                keyboard.append([InlineKeyboardButton(
                    button_text,
                    callback_data=f'transfer_dest_{slot_name}'
                )])

            if not keyboard:
                message += "❌ No other wallets available. Create another wallet first."

            keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data=f'transfer_source_{source_slot}')])

            # Update state
            self.waiting_for_input[user_id] = {
                'action': 'internal_transfer',
                'source_slot': source_slot,
                'network': network,
                'step': 'select_dest'
            }

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error selecting transfer chain: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')]])
            )

    async def internal_transfer_select_dest(self, query, user_id: int, dest_slot: str):
        """Prompt for transfer amount"""
        try:
            state = self.waiting_for_input.get(user_id, {})
            source_slot = state.get('source_slot')
            network = state.get('network')

            if not source_slot or not network:
                await query.edit_message_text(
                    "❌ Error: Transfer state lost. Please start again.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')]])
                )
                return

            # Get source wallet info
            user_data = self.get_user_wallet_data(user_id)
            source_wallet = user_data['wallet_slots'][source_slot]['chains'][network]
            balance_data = await self.get_balance(network, source_wallet['address'])
            balance = balance_data['balance']

            # Get prices
            prices = await self.get_token_prices()
            usd_value = balance * prices.get(network, 0)

            source_label = user_data['wallet_slots'][source_slot].get('label', '')
            dest_label = user_data['wallet_slots'][dest_slot].get('label', '')

            message = f"💸 Transfer {NETWORKS[network]['name']}\n\n"
            message += f"From: {source_slot.title()}"
            if source_label:
                message += f' "{source_label}"'
            message += f"\nTo: {dest_slot.title()}"
            if dest_label:
                message += f' "{dest_label}"'
            message += f"\n\nAvailable balance: {balance_data['formatted']}"
            if usd_value > 0:
                message += f" (${usd_value:.2f})"
            message += f"\n\nEnter amount to transfer (or 'max' for full balance):"

            # Update state
            self.waiting_for_input[user_id] = {
                'action': 'internal_transfer',
                'source_slot': source_slot,
                'dest_slot': dest_slot,
                'network': network,
                'step': 'amount'
            }

            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data='internal_transfer_start')]]

            await query.edit_message_text(
                message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error selecting transfer destination: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')]])
            )

    async def execute_solana_transfer(self, from_private_key: str, to_address: str, amount_lamports: int):
        """Sign and broadcast Solana transaction"""
        try:
            from solana.rpc.api import Client
            from solana.transaction import Transaction
            from solana.system_program import TransferParams, transfer
            from solders.keypair import Keypair
            from solders.pubkey import Pubkey

            # Initialize client
            client = Client(NETWORKS['SOL']['rpc'])

            # Create keypair from private key
            keypair = Keypair.from_bytes(bytes.fromhex(from_private_key))

            # Build transaction
            tx = Transaction().add(transfer(TransferParams(
                from_pubkey=keypair.pubkey(),
                to_pubkey=Pubkey.from_string(to_address),
                lamports=amount_lamports
            )))

            # Send transaction
            result = client.send_transaction(tx, keypair)
            return {'success': True, 'signature': result['result']}
        except Exception as e:
            logger.error(f"Solana transfer error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def execute_ethereum_transfer(self, from_private_key: str, to_address: str, amount_wei: int):
        """Sign and broadcast Ethereum transaction"""
        try:
            from web3 import Web3

            # Initialize Web3
            w3 = Web3(Web3.HTTPProvider(NETWORKS['ETH']['rpc']))

            # Get account from private key
            if not from_private_key.startswith('0x'):
                from_private_key = '0x' + from_private_key
            account = w3.eth.account.from_key(from_private_key)

            # Get nonce
            nonce = w3.eth.get_transaction_count(account.address)

            # Build transaction
            tx = {
                'nonce': nonce,
                'to': to_address,
                'value': amount_wei,
                'gas': 21000,
                'gasPrice': w3.eth.gas_price,
                'chainId': 1  # Mainnet
            }

            # Sign transaction
            signed_tx = w3.eth.account.sign_transaction(tx, from_private_key)

            # Send transaction
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            return {'success': True, 'tx_hash': tx_hash.hex()}
        except Exception as e:
            logger.error(f"Ethereum transfer error: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    async def execute_internal_transfer(self, update, context, state, amount_str: str):
        """Execute internal transfer between wallet slots"""
        user_id = update.effective_user.id
        source_slot = state['source_slot']
        dest_slot = state['dest_slot']
        network = state['network']

        try:
            # Get user data
            user_data = self.get_user_wallet_data(user_id)
            source_wallet = user_data['wallet_slots'][source_slot]['chains'][network]

            # Get balance
            balance_data = await self.get_balance(network, source_wallet['address'])
            balance = balance_data['balance']

            # Parse amount
            if amount_str.lower() == 'max':
                # Use max balance minus estimated fees
                if network == 'SOL':
                    # Reserve 0.001 SOL for fees
                    amount = max(0, balance - 0.001)
                elif network == 'ETH':
                    # Reserve 0.0001 ETH for fees
                    amount = max(0, balance - 0.0001)
                else:
                    amount = balance
            else:
                try:
                    amount = float(amount_str)
                except ValueError:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text="❌ Invalid amount. Please enter a number or 'max'."
                    )
                    return

            # Validate amount
            if amount <= 0:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Amount must be greater than 0."
                )
                return

            if amount > balance:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Insufficient balance. Available: {balance_data['formatted']}"
                )
                return

            # Create destination wallet if it doesn't exist
            dest_chains = user_data['wallet_slots'][dest_slot].get('chains', {})
            if network not in dest_chains:
                # Assign wallet from pool
                self.assign_wallet_to_user(user_id, network, dest_slot)
                user_data = self.get_user_wallet_data(user_id)  # Refresh
                dest_wallet = user_data['wallet_slots'][dest_slot]['chains'][network]
            else:
                dest_wallet = dest_chains[network]

            # Clear waiting state
            del self.waiting_for_input[user_id]

            # Send processing message
            msg = await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⏳ Processing transfer of {amount} {NETWORKS[network]['symbol']}..."
            )

            # Execute transaction based on network
            if network == 'SOL':
                # Convert to lamports
                amount_lamports = int(amount * 10**9)
                result = await self.execute_solana_transfer(
                    source_wallet['private_key'],
                    dest_wallet['address'],
                    amount_lamports
                )
            elif network == 'ETH':
                # Convert to wei
                amount_wei = int(amount * 10**18)
                result = await self.execute_ethereum_transfer(
                    source_wallet['private_key'],
                    dest_wallet['address'],
                    amount_wei
                )
            else:
                await msg.edit_text(f"❌ Transfers not supported for {network} yet.")
                return

            # Show result
            if result['success']:
                message = f"✅ Transfer successful!\n\n"
                message += f"Amount: {amount} {NETWORKS[network]['symbol']}\n"
                message += f"From: {source_slot.title()} → To: {dest_slot.title()}\n\n"
                if 'signature' in result:
                    message += f"Transaction: {result['signature']}"
                elif 'tx_hash' in result:
                    message += f"Transaction: {result['tx_hash']}"

                keyboard = [
                    [InlineKeyboardButton("💸 Transfer Again", callback_data='internal_transfer_start')],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
                ]
                await msg.edit_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                error_msg = f"❌ Transfer failed: {result.get('error', 'Unknown error')}"
                keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data='internal_transfer_start')]]
                await msg.edit_text(error_msg, reply_markup=InlineKeyboardMarkup(keyboard))

        except Exception as e:
            logger.error(f"Error executing internal transfer: {e}", exc_info=True)
            # Clear waiting state
            if user_id in self.waiting_for_input:
                del self.waiting_for_input[user_id]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Error: {str(e)}"
            )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show main menu"""
        user_id = update.effective_user.id
        user_data = self.get_user_wallet_data(user_id)

        welcome_message = "🤖 Welcome to Tenex Trading Bot!\n\n"

        # Check if user already has wallets
        if user_data and 'wallet_slots' in user_data:
            primary_wallet = user_data.get('primary_wallet', 'wallet1')
            primary_slot = user_data['wallet_slots'].get(primary_wallet, {})
            chains = primary_slot.get('chains', {})

            if chains:
                # Get slot label
                label = primary_slot.get('label')
                if label:
                    welcome_message += f"💼 {primary_wallet.title()} (Active) 🟢 - \"{label}\"\n\n"
                else:
                    welcome_message += f"💼 {primary_wallet.title()} (Active) 🟢\n\n"

                # Fetch balances and prices
                prices = await self.get_token_prices()
                total_primary = 0

                # Display primary wallet balances
                for network, wallet_data in chains.items():
                    # Skip disabled networks
                    if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                        continue

                    try:
                        balance_data = await self.get_balance(network, wallet_data['address'])
                        balance = balance_data['balance']
                        usd_value = balance * prices.get(network, 0)
                        total_primary += usd_value

                        emoji = NETWORKS[network].get('emoji', '🔹')
                        welcome_message += f"💳 {NETWORKS[network]['name']} {emoji}: {balance_data['formatted']}"
                        if usd_value > 0:
                            welcome_message += f" (${usd_value:.2f})"
                        welcome_message += "\n"
                    except Exception as e:
                        logger.error(f"Error getting balance for {network}: {e}")

                welcome_message += f"\nTotal Balance (Primary): ${total_primary:.2f}\n"
            else:
                welcome_message += "Get started by creating or importing a wallet.\n"
        else:
            welcome_message += "Get started by creating or importing a wallet.\n"

        reply_markup = await self.get_main_menu_keyboard(user_id)
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks"""
        query = update.callback_query
        await query.answer()

        action = query.data
        user_id = query.from_user.id

        try:
            # Main menu actions
            if action == 'create_start' or action == 'add_wallet':
                await self.show_network_selection(query, 'create', user_id)
            elif action == 'import_start':
                await self.show_network_selection(query, 'import', user_id)
            elif action == 'refresh_balance' or action == 'view_wallets':
                await self.view_wallets(query)
            elif action == 'back_to_menu':
                await self.show_main_menu(query, user_id)

            # Wallet management menu
            elif action == 'manage_wallets':
                await self.manage_wallets_menu(query, user_id)
            elif action == 'switch_wallet_menu':
                await self.switch_wallet_menu(query, user_id)
            elif action.startswith('switch_to_wallet'):
                slot_name = action.replace('switch_to_', '')
                await self.switch_primary_wallet(query, user_id, slot_name)
            elif action == 'create_in_slot_menu':
                await self.create_in_slot_menu(query, user_id)
            elif action.startswith('select_slot_'):
                slot_name = action.replace('select_slot_', '')
                await self.show_slot_chain_selection(query, user_id, slot_name)
            elif action.startswith('create_slot_'):
                # Parse: create_slot_wallet1_sol → wallet1, SOL
                parts = action.replace('create_slot_', '').split('_')
                slot_name = parts[0]  # wallet1
                network = parts[1].upper()  # SOL
                await self.create_wallet(query, context, network, slot_name)
            elif action == 'import_in_slot_menu':
                await self.import_in_slot_menu(query, user_id)
            elif action.startswith('import_select_slot_'):
                # import_select_slot_wallet1 → wallet1
                slot_name = action.replace('import_select_slot_', '')
                await self.show_slot_chain_selection_for_import(query, user_id, slot_name)
            elif action.startswith('import_slot_'):
                # Parse: import_slot_wallet1_sol → wallet1, SOL
                parts = action.replace('import_slot_', '').split('_')
                slot_name = parts[0]  # wallet1
                network = parts[1].upper()  # SOL
                await self.start_import_flow(query, network, slot_name)
            elif action == 'label_wallet_menu':
                await self.label_wallet_menu(query, user_id)
            elif action.startswith('label_wallet'):
                slot_name = action.replace('label_', '')
                await self.start_label_wallet_flow(query, user_id, slot_name)
            elif action == 'delete_wallet_menu':
                await self.delete_wallet_menu(query, user_id)
            elif action.startswith('delete_wallet_') and not action.startswith('confirm_delete'):
                slot_name = action.replace('delete_wallet_', '')
                await self.confirm_delete_wallet(query, user_id, slot_name)
            elif action.startswith('confirm_delete_wallet'):
                slot_name = action.replace('confirm_delete_', '')
                await self.execute_delete_wallet(query, user_id, slot_name)

            # Create/Import with specific network
            elif action.startswith('create_'):
                network = action.split('_')[1].upper()
                await self.create_wallet(query, context, network)
            elif action.startswith('import_'):
                network = action.split('_')[1].upper()
                await self.start_import_flow(query, network)

            # Export/Withdraw
            elif action == 'export_key':
                await self.export_key_start(query, user_id)
            elif action.startswith('export_slot_'):
                # export_slot_wallet1 → wallet1
                slot_name = action.replace('export_slot_', '')
                await self.export_select_chain(query, user_id, slot_name)
            elif action.startswith('export_') and action.count('_') == 2:
                # export_wallet1_sol → wallet1, SOL
                parts = action.replace('export_', '').split('_')
                slot_name = parts[0]
                network = parts[1].upper()
                await self.export_private_key(query, network, user_id, slot_name)
            elif action == 'withdraw_start':
                await self.withdraw_start(query, user_id)
            elif action.startswith('withdraw_slot_'):
                # withdraw_slot_wallet1 → wallet1
                slot_name = action.replace('withdraw_slot_', '')
                await self.withdraw_select_chain(query, user_id, slot_name)
            elif action.startswith('withdraw_') and action.count('_') == 2:
                # withdraw_wallet1_sol → wallet1, SOL
                parts = action.replace('withdraw_', '').split('_')
                slot_name = parts[0]
                network = parts[1].upper()
                await self.start_withdraw_flow(query, network, slot_name)

            # Inter-wallet transfer
            elif action == 'internal_transfer_start':
                await self.internal_transfer_start(query, user_id)
            elif action.startswith('transfer_source_'):
                slot_name = action.replace('transfer_source_', '')
                await self.internal_transfer_select_source(query, user_id, slot_name)
            elif action.startswith('transfer_chain_'):
                network = action.replace('transfer_chain_', '').upper()
                await self.internal_transfer_select_chain(query, user_id, network)
            elif action.startswith('transfer_dest_'):
                slot_name = action.replace('transfer_dest_', '')
                await self.internal_transfer_select_dest(query, user_id, slot_name)

            # Trading actions
            elif action.startswith('buy_1_'):
                token_address = action.replace('buy_1_', '')
                await self.execute_buy(query, user_id, 1.0, token_address)
            elif action.startswith('buy_3_'):
                token_address = action.replace('buy_3_', '')
                await self.execute_buy(query, user_id, 3.0, token_address)
            elif action.startswith('buy_x_'):
                token_address = action.replace('buy_x_', '')
                await self.ask_custom_amount(query, user_id, token_address)
            elif action.startswith('confirm_buy_'):
                parts = action.replace('confirm_buy_', '').split('_', 1)
                sol_amount = float(parts[0])
                token_address = parts[1]
                await self.confirm_buy(query, user_id, sol_amount, token_address)
            elif action.startswith('slippage_'):
                token_address = action.replace('slippage_', '')
                await self.show_slippage_menu(query, user_id, token_address)
            elif action.startswith('set_slippage_'):
                parts = action.replace('set_slippage_', '').split('_', 1)
                slippage_pct = float(parts[0])
                token_address = parts[1]
                await self.set_slippage(query, user_id, slippage_pct, token_address)
            elif action.startswith('orders_'):
                token_address = action.replace('orders_', '')
                await self.show_orders(query, user_id, token_address)
            elif action.startswith('refresh_'):
                token_address = action.replace('refresh_', '')
                # Create a fake update object to reuse display_token_info
                from telegram import Message
                fake_update = Update(update_id=0, message=query.message)
                await self.display_token_info(fake_update, None, token_address)
            elif action == 'view_bags':
                await self.show_bags(query, user_id)

            # Bag buy/sell actions
            elif action.startswith('bag_buy_'):
                token_address = action.replace('bag_buy_', '')
                await self.show_bag_buy_options(query, user_id, token_address)
            elif action.startswith('bag_sell_'):
                token_address = action.replace('bag_sell_', '')
                await self.show_bag_sell_options(query, user_id, token_address)

            # Sell percentage actions
            elif action.startswith('sell_25_'):
                token_address = action.replace('sell_25_', '')
                await self.execute_sell(query, user_id, 25, token_address)
            elif action.startswith('sell_50_'):
                token_address = action.replace('sell_50_', '')
                await self.execute_sell(query, user_id, 50, token_address)
            elif action.startswith('sell_75_'):
                token_address = action.replace('sell_75_', '')
                await self.execute_sell(query, user_id, 75, token_address)
            elif action.startswith('sell_100_'):
                token_address = action.replace('sell_100_', '')
                await self.execute_sell(query, user_id, 100, token_address)
            elif action.startswith('sell_custom_'):
                token_address = action.replace('sell_custom_', '')
                await self.ask_custom_sell_amount(query, user_id, token_address)
            elif action.startswith('confirm_sell_'):
                parts = action.replace('confirm_sell_', '').split('_', 1)
                percentage = float(parts[0])
                token_address = parts[1]
                await self.confirm_sell(query, user_id, percentage, token_address)

        except Exception as e:
            logger.error(f"Error in button handler: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Error: {str(e)}\n\nPlease try again or return to the menu.",
                                         reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]))

    async def show_network_selection(self, query, action_type: str, user_id: int):
        """Show network selection menu"""
        user_id_str = str(user_id)
        user_wallets = self.user_wallets.get(user_id_str, {}).get('wallets', {})
        enabled_networks = get_enabled_networks()

        keyboard = []

        # Show only enabled networks that user doesn't have yet
        for network_key, network_info in enabled_networks.items():
            if action_type == 'create' and network_key in user_wallets:
                continue  # Skip networks user already has when creating

            # Skip networks where import is not supported
            if action_type == 'import' and not network_info.get('import_supported', True):
                continue

            keyboard.append([InlineKeyboardButton(
                f"{network_info['name']} ({network_info['symbol']})",
                callback_data=f'{action_type}_{network_key.lower()}'
            )])

        keyboard.append([InlineKeyboardButton("⬅️ Back", callback_data='back_to_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)

        action_text = "create" if action_type == "create" else "import"
        await query.edit_message_text(
            f"Select network to {action_text} wallet:",
            reply_markup=reply_markup
        )

    async def create_wallet(self, query, context, network: str, slot_name: str = None):
        """Assign a pre-generated wallet to user in specified slot"""
        user_id = query.from_user.id
        user_id_str = str(user_id)

        # Get slot name (default to primary)
        if slot_name is None:
            slot_name = self.get_primary_wallet(user_id)

        # Check if user already has this network in this slot
        user_data = self.get_user_wallet_data(user_id)
        if 'wallet_slots' in user_data:
            wallet_slots = user_data.get('wallet_slots', {})
            if slot_name in wallet_slots:
                slot_data = wallet_slots[slot_name]
                if network in slot_data.get('chains', {}):
                    await query.edit_message_text(
                        f"❌ You already have a {NETWORKS[network]['name']} wallet in {slot_name}."
                    )
                    return

        await query.edit_message_text(f"⏳ Creating {NETWORKS[network]['name']} wallet in {slot_name}...")

        wallet = self.assign_wallet_to_user(user_id, network, slot_name)

        if not wallet:
            await query.edit_message_text(
                f"❌ Sorry, no available {NETWORKS[network]['name']} wallets at the moment. "
                "Please contact support."
            )
            return

        # Get balance
        balance_data = await self.get_balance(network, wallet['address'])

        # Get slot label for display
        slot_data = self.get_wallet_slot(user_id, slot_name)
        slot_label = slot_data.get('label')
        slot_display = f"{slot_name}" if not slot_label else f"{slot_name} - \"{slot_label}\""

        message = (
            f"✅ {NETWORKS[network]['name']} Wallet Created!\n\n"
            f"Wallet: {slot_display}\n"
            f"Address:\n`{wallet['address']}`\n\n"
            f"Balance: {balance_data['formatted']}\n\n"
            f"⚠️ SAVE YOUR PRIVATE KEY!\n"
            f"Use 'Export Private Key' from the menu to view it again.\n\n"
            f"Private Key:\n`{wallet['private_key']}`\n\n"
            f"⚠️ Never share your private key with anyone!"
        )

        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    async def start_import_flow(self, query, network: str, slot_name: str = None):
        """Start import wallet flow"""
        user_id = query.from_user.id
        user_data = self.get_user_wallet_data(user_id)

        # Get slot name (default to primary if not specified)
        if slot_name is None:
            slot_name = user_data.get('primary_wallet', 'wallet1')

        # Check if user already has this chain in this specific slot
        wallet_slots = user_data.get('wallet_slots', {})
        slot_data = wallet_slots.get(slot_name, {})
        existing_chains = slot_data.get('chains', {})

        if network in existing_chains:
            await query.edit_message_text(
                f"❌ You already have a {NETWORKS[network]['name']} wallet in {slot_name.title()}.\n\n"
                f"💡 Try importing into a different wallet slot or use a different chain.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='import_in_slot_menu')]])
            )
            return

        # Store state with slot information
        self.waiting_for_input[user_id] = {
            'action': 'import',
            'network': network,
            'slot_name': slot_name
        }

        slot_label = slot_data.get('label', '')
        slot_display = f"{slot_name.title()}"
        if slot_label:
            slot_display += f' "{slot_label}"'

        await query.edit_message_text(
            f"🔐 Import {NETWORKS[network]['name']} into {slot_display}\n\n"
            f"Please send your 12 or 24-word seed phrase.\n\n"
            f"⚠️ Your message will be deleted immediately for security.\n"
            f"⚠️ Never share your seed phrase with anyone!"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        message_text = update.message.text

        # Check if user is in input waiting state
        if user_id in self.waiting_for_input:
            state = self.waiting_for_input[user_id]

            # Delete user message for security
            try:
                await update.message.delete()
            except:
                pass

            try:
                # Check for custom buy amount first (uses 'type' instead of 'action')
                if state.get('type') == 'buy_custom_amount':
                    # Process custom buy amount
                    token_address = state['token_address']
                    try:
                        sol_amount = float(message_text.strip())
                        if sol_amount <= 0:
                            raise ValueError("Amount must be positive")

                        # Clear waiting state
                        del self.waiting_for_input[user_id]

                        # Delete the original waiting message if possible
                        try:
                            await context.bot.delete_message(
                                chat_id=update.effective_chat.id,
                                message_id=state.get('message_id')
                            )
                        except:
                            pass

                        # Send new message that will be edited
                        processing_msg = await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"Processing {sol_amount} SOL buy order..."
                        )

                        # Create a fake query for execute_buy with the processing message
                        from telegram import CallbackQuery
                        fake_query = CallbackQuery(
                            id="custom_buy",
                            from_user=update.effective_user,
                            chat_instance=str(update.effective_chat.id),
                            data=f"buy_x_{token_address}",
                            message=processing_msg
                        )

                        # Execute buy with custom amount
                        await self.execute_buy(fake_query, user_id, sol_amount, token_address)

                    except ValueError as e:
                        del self.waiting_for_input[user_id]
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ Invalid amount. Please enter a valid number (e.g., 0.1, 0.5, 2)",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Back", callback_data=f'refresh_{token_address}')
                            ]])
                        )
                    return

                # Check for custom sell amount
                if state.get('type') == 'sell_custom_amount':
                    # Process custom sell percentage
                    token_address = state['token_address']
                    try:
                        percentage = float(message_text.strip())
                        if percentage <= 0 or percentage > 100:
                            raise ValueError("Percentage must be between 1 and 100")

                        # Clear waiting state
                        del self.waiting_for_input[user_id]

                        # Delete the original waiting message if possible
                        try:
                            await context.bot.delete_message(
                                chat_id=update.effective_chat.id,
                                message_id=state.get('message_id')
                            )
                        except:
                            pass

                        # Send new message that will be edited
                        processing_msg = await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"Processing {percentage}% sell order..."
                        )

                        # Create a fake query for execute_sell with the processing message
                        from telegram import CallbackQuery
                        fake_query = CallbackQuery(
                            id="custom_sell",
                            from_user=update.effective_user,
                            chat_instance=str(update.effective_chat.id),
                            data=f"sell_custom_{token_address}",
                            message=processing_msg
                        )

                        # Execute sell with custom percentage
                        await self.execute_sell(fake_query, user_id, percentage, token_address)

                    except ValueError as e:
                        del self.waiting_for_input[user_id]
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ Invalid percentage. Please enter a number between 1 and 100 (e.g., 10, 25, 50)",
                            reply_markup=InlineKeyboardMarkup([[
                                InlineKeyboardButton("⬅️ Back to Bags", callback_data='view_bags')
                            ]])
                        )
                    return

                # Now check for other actions
                if state.get('action') == 'import':
                    await self.import_wallet(update, context, state, message_text)
                elif state.get('action') == 'withdraw':
                    await self.process_withdraw(update, context, state, message_text)
                elif state.get('action') == 'label_wallet':
                    # Process wallet label
                    slot_name = state['slot_name']
                    label_text = message_text.strip()

                    # Clear waiting state
                    del self.waiting_for_input[user_id]

                    # Set the label
                    success = self.set_wallet_label(user_id, slot_name, label_text)

                    if success:
                        if label_text.lower() == 'clear' or not label_text:
                            message = f"✅ Label removed from {slot_name.title()}."
                        else:
                            message = f"✅ {slot_name.title()} labeled as \"{label_text[:20]}\"."

                        keyboard = [
                            [InlineKeyboardButton("🏷️ Label Another", callback_data='label_wallet_menu')],
                            [InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]
                        ]
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=message,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"❌ Failed to set label for {slot_name.title()}."
                        )
                elif state.get('action') == 'internal_transfer' and state.get('step') == 'amount':
                    # Process internal transfer amount
                    await self.execute_internal_transfer(update, context, state, message_text)
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"❌ Error: {str(e)}"
                )
            return

        # Check if message is a contract address
        if self.is_contract_address(message_text):
            logger.info(f"Detected contract address: {message_text}")
            await self.display_token_info(update, context, message_text.strip())
            return

    async def import_wallet(self, update, context, state, seed_phrase: str):
        """Import wallet from seed phrase"""
        user_id = update.effective_user.id
        user_id_str = str(user_id)
        network = state['network']
        slot_name = state.get('slot_name')  # Get slot from state

        # Default to primary if not specified
        if slot_name is None:
            slot_name = self.get_primary_wallet(user_id)

        # Validate seed phrase
        words = seed_phrase.strip().split()
        if len(words) not in [12, 24]:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Invalid seed phrase. Must be 12 or 24 words."
            )
            return

        msg = await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⏳ Importing {NETWORKS[network]['name']} wallet into {slot_name}..."
        )

        # Derive main wallet address
        wallet_data = self.derive_address_from_seed(seed_phrase, network, 0)

        if not wallet_data:
            await msg.edit_text("❌ Error deriving wallet from seed phrase.")
            return

        # Store seed phrase in .env with slot-specific key
        env_key = f"{user_id}_{slot_name}_{network}_SEED_PHRASE"
        set_key(ENV_FILE, env_key, seed_phrase)

        # Get balance
        balance_data = await self.get_balance(network, wallet_data['address'])

        # Auto-migrate if needed
        if self.needs_migration(user_id_str):
            self.migrate_user_data(user_id_str)

        # Initialize structure if needed (new user)
        if user_id_str not in self.user_wallets:
            max_slots = CONFIG.get('settings', {}).get('max_wallet_slots_per_user', 3)
            self.user_wallets[user_id_str] = {
                'primary_wallet': 'wallet1',
                'wallet_slots': {}
            }
            # Initialize all slots
            for i in range(1, max_slots + 1):
                slot = f'wallet{i}'
                self.user_wallets[user_id_str]['wallet_slots'][slot] = {
                    'label': None,
                    'created_at': None,
                    'is_primary': (slot == 'wallet1'),
                    'chains': {}
                }

        # Initialize slot if it doesn't exist
        if slot_name not in self.user_wallets[user_id_str]['wallet_slots']:
            self.user_wallets[user_id_str]['wallet_slots'][slot_name] = {
                'label': None,
                'created_at': datetime.datetime.now().isoformat(),
                'is_primary': slot_name == self.get_primary_wallet(user_id),
                'chains': {}
            }

        # Update created_at if this is the first chain in the slot
        if not self.user_wallets[user_id_str]['wallet_slots'][slot_name].get('chains'):
            self.user_wallets[user_id_str]['wallet_slots'][slot_name]['created_at'] = datetime.datetime.now().isoformat()

        # Save imported wallet to slot
        self.user_wallets[user_id_str]['wallet_slots'][slot_name]['chains'][network] = {
            'address': wallet_data['address'],
            'private_key': wallet_data['private_key'],
            'imported': True
        }
        self.save_user_wallets()

        del self.waiting_for_input[user_id]

        # Get slot label for display
        slot_data = self.get_wallet_slot(user_id, slot_name)
        slot_label = slot_data.get('label')
        slot_display = f"{slot_name}" if not slot_label else f"{slot_name} - \"{slot_label}\""

        message = (
            f"✅ {NETWORKS[network]['name']} Wallet Imported!\n\n"
            f"Wallet: {slot_display}\n"
            f"Address:\n`{wallet_data['address']}`\n\n"
            f"Balance: {balance_data['formatted']}\n\n"
            f"Your seed phrase has been securely stored."
        )

        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await msg.edit_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    async def view_wallets(self, query):
        """View all user wallets with balances"""
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
                    if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                        continue

                    try:
                        balance_data = await self.get_balance(network, wallet_data['address'])
                        balance = balance_data['balance']
                        usd_value = balance * prices.get(network, 0)
                        slot_total += usd_value

                        emoji = NETWORKS[network].get('emoji', '🔹')
                        chain_line = f"💳 {NETWORKS[network]['name']}: {balance_data['formatted']}"
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
                    if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                        continue
                    label = slot_data.get('label')
                    slot_label = f"{slot_name}" if not label else f"{slot_name} - {label}"
                    message += f"{slot_label} {NETWORKS[network]['symbol']}: <code>{wallet_data['address']}</code>\n"

        keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)

    async def export_key_start(self, query, user_id: int):
        """Show wallet slot selection for export private key"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "🔑 Export Private Key - Select Wallet\n\n"
            keyboard = []

            # Show wallet slots with chains
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

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

                emoji = NETWORKS[network].get('emoji', '🔹')
                keyboard.append([InlineKeyboardButton(
                    f"{emoji} {NETWORKS[network]['name']} ({NETWORKS[network]['symbol']})",
                    callback_data=f'export_{slot_name}_{network.lower()}'
                )])

            if not keyboard:
                message += "❌ No chains available in this wallet."

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

    async def export_private_key(self, query, network: str, user_id: int, slot_name: str = None):
        """Export private key for a specific network and slot"""
        try:
            user_data = self.get_user_wallet_data(user_id)

            # Default to primary if slot not specified
            if slot_name is None:
                slot_name = user_data.get('primary_wallet', 'wallet1')

            wallet_slots = user_data.get('wallet_slots', {})
            slot_data = wallet_slots.get(slot_name, {})
            chains = slot_data.get('chains', {})

            if network not in chains:
                await query.edit_message_text(
                    f"❌ You don't have a {NETWORKS[network]['name']} wallet in {slot_name}.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='export_key')]])
                )
                return

            wallet_data = chains[network]

            message = (
                f"🔑 {NETWORKS[network]['name']} Private Key\n"
                f"Wallet: {slot_name.title()}\n\n"
                f"Address:\n`{wallet_data['address']}`\n\n"
                f"Private Key:\n`{wallet_data['private_key']}`\n\n"
                f"⚠️ NEVER share your private key with anyone!\n"
                f"⚠️ Anyone with this key has full access to your funds!"
            )

            keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error exporting private key: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error: {str(e)}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='export_key')]])
            )

    async def withdraw_start(self, query, user_id: int):
        """Show wallet slot selection for withdrawal"""
        try:
            user_data = self.get_user_wallet_data(user_id)
            wallet_slots = user_data.get('wallet_slots', {})

            message = "💸 Withdraw - Select Wallet\n\n"
            keyboard = []

            # Show wallet slots with chains
            for slot_name in ['wallet1', 'wallet2', 'wallet3']:
                slot_data = wallet_slots.get(slot_name, {})
                chains = slot_data.get('chains', {})
                label = slot_data.get('label')
                is_primary = slot_data.get('is_primary', False)

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

                    emoji = NETWORKS[network].get('emoji', '🔹')
                    button_text = f"{emoji} {NETWORKS[network]['name']}: {balance_data['formatted']}"
                    if usd_value > 0:
                        button_text += f" (${usd_value:.2f})"

                    keyboard.append([InlineKeyboardButton(
                        button_text,
                        callback_data=f'withdraw_{slot_name}_{network.lower()}'
                    )])
                except Exception as e:
                    logger.error(f"Error getting balance for {network}: {e}")

            if not keyboard:
                message += "❌ No chains available in this wallet."

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

    async def start_withdraw_flow(self, query, network: str, slot_name: str = None):
        """Start withdrawal flow"""
        user_id = query.from_user.id
        user_data = self.get_user_wallet_data(user_id)

        # Default to primary if slot not specified
        if slot_name is None:
            slot_name = user_data.get('primary_wallet', 'wallet1')

        self.waiting_for_input[user_id] = {
            'action': 'withdraw',
            'network': network,
            'slot_name': slot_name,
            'step': 'address'
        }

        await query.edit_message_text(
            f"💸 Withdraw {NETWORKS[network]['symbol']} from {slot_name.title()}\n\n"
            f"Please send the recipient address:"
        )

    async def process_withdraw(self, update, context, state, message_text: str):
        """Process withdrawal input"""
        user_id = update.effective_user.id
        network = state['network']
        slot_name = state.get('slot_name')

        if state['step'] == 'address':
            # Store recipient address
            state['recipient'] = message_text
            state['step'] = 'amount'
            self.waiting_for_input[user_id] = state

            # Get current balance from slot
            user_data = self.get_user_wallet_data(user_id)

            # Default to primary if slot not in state
            if slot_name is None:
                slot_name = user_data.get('primary_wallet', 'wallet1')
                state['slot_name'] = slot_name
                self.waiting_for_input[user_id] = state

            wallet_data = user_data['wallet_slots'][slot_name]['chains'][network]
            balance_data = await self.get_balance(network, wallet_data['address'])

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📊 Current balance: {balance_data['formatted']}\n\n"
                     f"Please send the amount to withdraw:"
            )

        elif state['step'] == 'amount':
            # Process withdrawal
            amount = message_text
            recipient = state['recipient']

            del self.waiting_for_input[user_id]

            # For now, just show confirmation (actual withdrawal requires transaction signing)
            message = (
                f"💸 Withdrawal Initiated\n\n"
                f"Network: {NETWORKS[network]['name']}\n"
                f"To: `{recipient}`\n"
                f"Amount: {amount} {NETWORKS[network]['symbol']}\n\n"
                f"⚠️ Note: Actual transaction signing will be implemented.\n"
                f"This is a placeholder for the withdrawal flow."
            )

            keyboard = [[InlineKeyboardButton("⬅️ Back to Menu", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

    async def show_main_menu(self, query, user_id: int):
        """Show main menu"""
        user_data = self.get_user_wallet_data(user_id)

        message = "🤖 Tenex Trading Bot\n\n"

        # Check if user already has wallets
        if user_data and 'wallet_slots' in user_data:
            primary_wallet = user_data.get('primary_wallet', 'wallet1')
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

                # Display primary wallet balances
                for network, wallet_data in chains.items():
                    # Skip disabled networks
                    if network not in NETWORKS or not NETWORKS[network].get('enabled', True):
                        continue

                    try:
                        balance_data = await self.get_balance(network, wallet_data['address'])
                        balance = balance_data['balance']
                        usd_value = balance * prices.get(network, 0)
                        total_primary += usd_value

                        emoji = NETWORKS[network].get('emoji', '🔹')
                        message += f"💳 {NETWORKS[network]['name']} {emoji}: {balance_data['formatted']}"
                        if usd_value > 0:
                            message += f" (${usd_value:.2f})"
                        message += "\n"
                    except Exception as e:
                        logger.error(f"Error getting balance for {network}: {e}")

                message += f"\nTotal Balance (Primary): ${total_primary:.2f}\n"
            else:
                message += "Get started by creating or importing a wallet."
        else:
            message += "Get started by creating or importing a wallet."

        reply_markup = await self.get_main_menu_keyboard(user_id)
        await query.edit_message_text(message, reply_markup=reply_markup)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return

    if not ADMIN_ID or ADMIN_ID == 0:
        print("Error: TELEGRAM_ADMIN_ID not found in .env file")
        return

    # Ensure wallets directory exists
    WALLETS_DIR.mkdir(exist_ok=True)

    bot = TradingBot()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))

    logger.info("💰 Trading Bot started!")
    logger.info(f"Admin ID: {ADMIN_ID}")

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
