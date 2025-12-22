"""
Balance Service
Handles balance checking and price fetching for all supported networks
"""

import logging
import requests
from typing import Dict, Any
from web3 import Web3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

logger = logging.getLogger(__name__)


class SSLAdapter(HTTPAdapter):
    """Custom HTTPAdapter with modern TLS configuration"""
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.load_default_certs()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)


def create_secure_session():
    """Create a requests session with proper SSL/TLS configuration"""
    session = requests.Session()
    session.mount('https://', SSLAdapter())
    return session


class BalanceService:
    """Handles balance queries and price fetching"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Balance Service

        Args:
            config: Bot configuration dictionary
        """
        self.config = config
        self.networks = self._build_network_config()

    def _build_network_config(self) -> Dict[str, Any]:
        """Build network configuration from config"""
        networks = {}
        for chain_key, chain_config in self.config['chains'].items():
            if chain_config.get('enabled', True):
                networks[chain_key] = {
                    'name': chain_config['name'],
                    'symbol': chain_config['symbol'],
                    'rpc': chain_config['rpc'],
                    'decimals': chain_config['decimals'],
                    'coingecko_id': chain_config.get('coingecko_id', ''),
                }
        return networks

    async def get_token_prices(self) -> Dict[str, float]:
        """
        Get current token prices in USD from CoinGecko

        Returns:
            Dictionary mapping network keys to USD prices
        """
        try:
            # Collect CoinGecko IDs
            coingecko_ids = [
                network['coingecko_id']
                for network in self.networks.values()
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
            for network_key, network in self.networks.items():
                coingecko_id = network.get('coingecko_id')
                if coingecko_id:
                    prices[network_key] = data.get(coingecko_id, {}).get('usd', 0)
                else:
                    prices[network_key] = 0

            return prices

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            return {k: 0 for k in self.networks.keys()}

    async def get_balance(self, network: str, address: str) -> Dict[str, Any]:
        """
        Get balance for an address on a specific network

        Args:
            network: Network identifier ('SOL', 'ETH', 'BSC', 'STACKS')
            address: Wallet address

        Returns:
            Dictionary with 'balance' (float) and 'formatted' (str)
        """
        try:
            logger.info(f"Fetching balance for {network} address: {address}")

            if network == 'SOL':
                return await self.get_solana_balance(address)
            elif network == 'ETH':
                return await self.get_ethereum_balance(address)
            elif network == 'BSC':
                return await self.get_bsc_balance(address)
            elif network == 'STACKS':
                return await self.get_stacks_balance(address)
            else:
                logger.error(f"Unsupported network: {network}")
                return {'balance': 0, 'formatted': 'Unsupported network'}

        except Exception as e:
            logger.error(f"Error getting balance for {network}: {e}", exc_info=True)
            return {'balance': 0, 'formatted': 'Error'}

    async def get_solana_balance(self, address: str) -> Dict[str, Any]:
        """
        Get Solana balance

        Args:
            address: Solana wallet address

        Returns:
            Balance information
        """
        try:
            rpc_url = self.networks['SOL']['rpc']
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }

            session = create_secure_session()
            response = session.post(rpc_url, json=payload, timeout=10)
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

    async def get_ethereum_balance(self, address: str) -> Dict[str, Any]:
        """
        Get Ethereum balance

        Args:
            address: Ethereum wallet address

        Returns:
            Balance information
        """
        try:
            rpc_url = self.networks['ETH']['rpc']
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            balance_wei = w3.eth.get_balance(address)
            balance_eth = w3.from_wei(balance_wei, 'ether')

            return {
                'balance': float(balance_eth),
                'formatted': f"{balance_eth:.6f} ETH"
            }

        except Exception as e:
            logger.error(f"Ethereum balance error: {e}")
            return {'balance': 0, 'formatted': 'Error'}

    async def get_bsc_balance(self, address: str) -> Dict[str, Any]:
        """
        Get BSC (Binance Smart Chain) balance

        Args:
            address: BSC wallet address

        Returns:
            Balance information
        """
        try:
            rpc_url = self.networks['BSC']['rpc']
            w3 = Web3(Web3.HTTPProvider(rpc_url))
            balance_wei = w3.eth.get_balance(address)
            balance_bnb = w3.from_wei(balance_wei, 'ether')

            return {
                'balance': float(balance_bnb),
                'formatted': f"{balance_bnb:.6f} BNB"
            }

        except Exception as e:
            logger.error(f"BSC balance error: {e}")
            return {'balance': 0, 'formatted': 'Error'}

    async def get_stacks_balance(self, address: str) -> Dict[str, Any]:
        """
        Get Stacks balance

        Args:
            address: Stacks wallet address

        Returns:
            Balance information
        """
        try:
            # Check if address is valid
            if not address or address.startswith('Stacks address derivation'):
                logger.warning(f"Invalid Stacks address: {address}")
                return {'balance': 0, 'formatted': 'N/A (Import not supported)'}

            rpc_url = self.networks['STACKS']['rpc']
            url = f"{rpc_url}/v2/accounts/{address}"
            logger.info(f"Fetching Stacks balance from: {url}")

            session = create_secure_session()
            response = session.get(url, timeout=10)

            if response.status_code != 200:
                logger.error(f"Stacks API error: {response.status_code}")
                return {'balance': 0, 'formatted': '0 STX'}

            data = response.json()

            # Stacks API returns balance in microSTX
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

    async def get_wallet_total_balance_usd(self, user_id: int, slot_name: str, data_manager) -> float:
        """
        Calculate total USD balance for a wallet slot

        Args:
            user_id: Telegram user ID
            slot_name: Wallet slot name
            data_manager: DataManager instance

        Returns:
            Total balance in USD
        """
        try:
            slot_data = data_manager.get_wallet_slot(user_id, slot_name)
            if not slot_data or 'chains' not in slot_data:
                return 0.0

            # Get current prices
            prices = await self.get_token_prices()
            total_usd = 0.0

            # Sum up balances from all chains
            for network, wallet in slot_data['chains'].items():
                if network not in self.networks:
                    continue

                address = wallet.get('address')
                if not address:
                    continue

                # Get balance
                balance_info = await self.get_balance(network, address)
                balance = balance_info.get('balance', 0)

                # Convert to USD
                price = prices.get(network, 0)
                total_usd += balance * price

            return total_usd

        except Exception as e:
            logger.error(f"Error calculating total balance: {e}")
            return 0.0
