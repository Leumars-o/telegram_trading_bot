"""
Token Service
Handles token detection and information fetching from DexScreener
"""

import re
import logging
from typing import Optional, Dict, Any, List
import requests

logger = logging.getLogger(__name__)


class TokenService:
    """Handles token detection and data fetching"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Token Service

        Args:
            config: Bot configuration dictionary
        """
        self.config = config
        self.dexscreener_base_url = "https://api.dexscreener.com/latest/dex/tokens"
        self.supported_chains = self._get_supported_chains()

    def _get_supported_chains(self) -> List[str]:
        """Get list of supported DexScreener chains from config"""
        chains = []
        for chain_config in self.config['chains'].values():
            if chain_config.get('enabled', True) and chain_config.get('dexscreener_chain'):
                chains.append(chain_config['dexscreener_chain'])
        return chains

    def is_contract_address(self, text: str) -> bool:
        """
        Check if the text appears to be a contract address

        Args:
            text: Input text to check

        Returns:
            True if it looks like a contract address
        """
        # Remove whitespace
        text = text.strip()

        # Most blockchain addresses are 32-44 characters alphanumeric
        # Solana: 32-44 base58
        # Ethereum: 42 characters starting with 0x
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
        """
        Auto-detect chain and fetch token data from DexScreener

        Args:
            token_address: Token contract address

        Returns:
            Dictionary with 'chain' and 'data' or None if not found
        """
        try:
            # DexScreener API endpoint - searches across all chains
            url = f"{self.dexscreener_base_url}/{token_address}"
            logger.info(f"Fetching token data from: {url}")

            # Try async aiohttp first, fallback to requests
            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status != 200:
                            logger.error(f"DexScreener API returned status {response.status}")
                            return None

                        data = await response.json()

            except ImportError:
                # Fallback to requests
                logger.info("aiohttp not available, using requests")
                response = requests.get(url, timeout=10)

                if response.status_code != 200:
                    logger.error(f"DexScreener API returned status {response.status_code}")
                    return None

                data = response.json()

            logger.info(f"DexScreener response received")

            # Check if we have valid data
            if not data or 'pairs' not in data:
                logger.error("No pairs found in DexScreener response")
                return None

            pairs = data.get('pairs', [])
            if len(pairs) == 0:
                logger.error("Empty pairs list")
                return None

            # Filter by supported chains (prioritize: solana, ethereum)
            for chain in self.supported_chains:
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

    def parse_token_data(self, token_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse token data from DexScreener response

        Args:
            token_info: Token info from detect_and_fetch_token

        Returns:
            Parsed token information
        """
        try:
            chain = token_info.get('chain', 'unknown')
            pair_data = token_info.get('data', {})

            base_token = pair_data.get('baseToken', {})
            quote_token = pair_data.get('quoteToken', {})

            parsed = {
                'chain': chain.upper(),
                'chain_display': chain.title(),
                'token_name': base_token.get('name', 'Unknown'),
                'token_symbol': base_token.get('symbol', 'TOKEN'),
                'token_address': base_token.get('address', ''),
                'pair_address': pair_data.get('pairAddress', ''),
                'dex': pair_data.get('dexId', 'Unknown'),
                'price_usd': float(pair_data.get('priceUsd', 0)),
                'price_native': float(pair_data.get('priceNative', 0)),
                'liquidity_usd': float(pair_data.get('liquidity', {}).get('usd', 0)),
                'volume_24h': float(pair_data.get('volume', {}).get('h24', 0)),
                'price_change_24h': float(pair_data.get('priceChange', {}).get('h24', 0)),
                'market_cap': float(pair_data.get('marketCap', 0)) if pair_data.get('marketCap') else None,
                'fdv': float(pair_data.get('fdv', 0)) if pair_data.get('fdv') else None,
                'url': pair_data.get('url', ''),
                'info': pair_data.get('info', {}),
            }

            return parsed

        except Exception as e:
            logger.error(f"Error parsing token data: {e}")
            return {}

    def format_large_number(self, num: float) -> str:
        """
        Format large numbers with K/M/B suffixes

        Args:
            num: Number to format

        Returns:
            Formatted string
        """
        if num is None:
            return 'N/A'

        if num >= 1_000_000_000:
            return f"${num / 1_000_000_000:.2f}B"
        elif num >= 1_000_000:
            return f"${num / 1_000_000:.2f}M"
        elif num >= 1_000:
            return f"${num / 1_000:.2f}K"
        else:
            return f"${num:.2f}"

    def get_chain_emoji(self, chain: str) -> str:
        """
        Get emoji for a blockchain

        Args:
            chain: Chain identifier

        Returns:
            Emoji string
        """
        chain_lower = chain.lower()

        for chain_key, chain_config in self.config['chains'].items():
            if chain_config.get('dexscreener_chain', '').lower() == chain_lower:
                return chain_config.get('emoji', '🔹')

        # Default emojis
        emojis = {
            'solana': '🧬',
            'ethereum': '💎',
            'base': '🔵',
            'polygon': '🟣',
            'arbitrum': '🔷',
            'optimism': '🔴',
        }

        return emojis.get(chain_lower, '🔹')
