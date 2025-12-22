"""
BSC Swap Script - Swap BNB to BEP20 Tokens
Uses 1inch API v5 for optimal routing and pricing on Binance Smart Chain
"""

import os
import sys
import json
import time
import logging
from typing import Optional, Dict, Any
import requests
from web3 import Web3
from eth_account import Account
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
ONEINCH_API_BASE = "https://api.1inch.dev/swap/v5.2/56"  # 56 = BSC Chain ID
ONEINCH_API_KEY = os.getenv('ONEINCH_API_KEY', '')  # Get free key at https://portal.1inch.dev/
BSC_RPC_URL = os.getenv('BSC_RPC_URL', 'https://bsc-dataseed.binance.org')

# Validate API key
if not ONEINCH_API_KEY:
    logger.warning("="*60)
    logger.warning("ONEINCH_API_KEY is not set!")
    logger.warning("1inch API key recommended for better rate limits.")
    logger.warning("Get a FREE API key at: https://portal.1inch.dev/")
    logger.warning("Add it to your .env file: ONEINCH_API_KEY=your_key_here")
    logger.warning("="*60)

# Common token addresses on BSC
TOKENS = {
    'BNB': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',  # Native BNB
    'WBNB': '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c',  # Wrapped BNB
    'USDT': '0x55d398326f99059fF775485246999027B3197955',  # Tether USD
    'USDC': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',  # USD Coin
    'BUSD': '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56',  # Binance USD
    'CAKE': '0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82',  # PancakeSwap
    'ETH': '0x2170Ed0880ac9A755fd29B2688956BD959F933F8',  # Binance-Peg Ethereum
}


class BSCSwap:
    """BSC Swap handler using 1inch aggregator"""

    def __init__(self, private_key: str, rpc_url: str = BSC_RPC_URL):
        """
        Initialize BSC Swap handler

        Args:
            private_key: Hex encoded private key (with or without 0x prefix)
            rpc_url: BSC RPC endpoint
        """
        self.rpc_url = rpc_url
        self.session = requests.Session()
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        # Load account from private key
        try:
            # Remove 0x prefix if present
            if private_key.startswith('0x'):
                private_key = private_key[2:]

            self.account = Account.from_key(private_key)
            self.wallet_address = self.account.address
            logger.info(f"Initialized wallet: {self.wallet_address}")

            # Check if connected to BSC
            if not self.w3.is_connected():
                raise ConnectionError("Failed to connect to BSC RPC")

            chain_id = self.w3.eth.chain_id
            if chain_id != 56:
                logger.warning(f"Warning: Connected to chain ID {chain_id}, expected 56 (BSC Mainnet)")

        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise ValueError(f"Invalid private key format: {e}")

    def get_bnb_balance(self) -> float:
        """
        Get BNB balance for the wallet

        Returns:
            BNB balance in ether units
        """
        try:
            balance_wei = self.w3.eth.get_balance(self.wallet_address)
            balance_bnb = self.w3.from_wei(balance_wei, 'ether')
            return float(balance_bnb)
        except Exception as e:
            logger.error(f"Failed to get BNB balance: {e}")
            return 0.0

    def get_token_balance(self, token_address: str) -> Optional[Dict[str, Any]]:
        """
        Get BEP20 token balance for the wallet

        Args:
            token_address: Token contract address

        Returns:
            Dict with balance info or None if error
        """
        try:
            # Skip for native BNB
            if token_address.lower() == TOKENS['BNB'].lower():
                balance = self.get_bnb_balance()
                return {
                    'balance': int(balance * 1e18),
                    'decimals': 18,
                    'uiAmount': balance
                }

            # ERC20 ABI for balanceOf and decimals
            erc20_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function"
                },
                {
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "type": "function"
                }
            ]

            token_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=erc20_abi
            )

            balance = token_contract.functions.balanceOf(self.wallet_address).call()
            decimals = token_contract.functions.decimals().call()
            ui_amount = balance / (10 ** decimals)

            return {
                'balance': balance,
                'decimals': decimals,
                'uiAmount': ui_amount
            }

        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            return None

    def get_quote(
        self,
        from_token: str,
        to_token: str,
        amount: int,
        slippage: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get swap quote from 1inch

        Args:
            from_token: Input token address
            to_token: Output token address
            amount: Amount in smallest unit (wei for BNB)
            slippage: Slippage tolerance in percent (1.0 = 1%)

        Returns:
            Quote data or None if failed
        """
        try:
            params = {
                'src': from_token,
                'dst': to_token,
                'amount': str(amount),
                'from': self.wallet_address,
                'slippage': str(slippage),
                'disableEstimate': 'false',
                'allowPartialFill': 'false',
            }

            headers = {
                'Accept': 'application/json',
            }
            if ONEINCH_API_KEY:
                headers['Authorization'] = f'Bearer {ONEINCH_API_KEY}'

            logger.info(f"Requesting quote for {amount} wei...")
            response = self.session.get(
                f"{ONEINCH_API_BASE}/quote",
                params=params,
                headers=headers
            )
            response.raise_for_status()

            quote = response.json()

            # Display quote info
            from_amount = int(quote.get('fromTokenAmount', 0))
            to_amount = int(quote.get('toTokenAmount', 0))

            logger.info(f"Quote received:")
            logger.info(f"  Input: {from_amount / 1e18:.9f} BNB")
            logger.info(f"  Output: ~{to_amount / 1e18:.6f} tokens")

            return quote

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None

    def get_swap_transaction(
        self,
        from_token: str,
        to_token: str,
        amount: int,
        slippage: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Get swap transaction from 1inch

        Args:
            from_token: Input token address
            to_token: Output token address
            amount: Amount in smallest unit (wei for BNB)
            slippage: Slippage tolerance in percent

        Returns:
            Transaction data or None if failed
        """
        try:
            params = {
                'src': from_token,
                'dst': to_token,
                'amount': str(amount),
                'from': self.wallet_address,
                'slippage': str(slippage),
                'disableEstimate': 'true',
                'allowPartialFill': 'false',
            }

            headers = {
                'Accept': 'application/json',
            }
            if ONEINCH_API_KEY:
                headers['Authorization'] = f'Bearer {ONEINCH_API_KEY}'

            logger.info("Requesting swap transaction...")
            response = self.session.get(
                f"{ONEINCH_API_BASE}/swap",
                params=params,
                headers=headers
            )
            response.raise_for_status()

            result = response.json()

            if 'tx' not in result:
                logger.error("No transaction data returned from 1inch")
                return None

            logger.info("Swap transaction received")
            return result

        except Exception as e:
            logger.error(f"Failed to get swap transaction: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None

    def send_transaction(self, tx_data: Dict[str, Any]) -> Optional[str]:
        """
        Sign and send transaction to BSC network

        Args:
            tx_data: Transaction data from 1inch

        Returns:
            Transaction hash or None if failed
        """
        try:
            # Extract transaction parameters
            tx = tx_data['tx']
            transaction = {
                'from': self.wallet_address,
                'to': Web3.to_checksum_address(tx['to']),
                'value': int(tx.get('value', 0)),
                'gas': int(tx['gas']),
                'gasPrice': int(tx['gasPrice']),
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                'data': tx['data'],
                'chainId': 56
            }

            logger.info("Signing transaction...")
            signed_tx = self.account.sign_transaction(transaction)

            logger.info("Sending transaction to network...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"Transaction sent: {tx_hash_hex}")
            return tx_hash_hex

        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            return None

    def get_transaction_status(self, tx_hash: str, max_attempts: int = 30) -> bool:
        """
        Poll transaction status until confirmed

        Args:
            tx_hash: Transaction hash
            max_attempts: Maximum polling attempts

        Returns:
            True if confirmed, False otherwise
        """
        logger.info(f"Polling transaction status: {tx_hash}")

        for attempt in range(max_attempts):
            try:
                receipt = self.w3.eth.get_transaction_receipt(tx_hash)

                if receipt:
                    if receipt['status'] == 1:
                        logger.info(f"Transaction confirmed! Block: {receipt['blockNumber']}")
                        return True
                    else:
                        logger.error(f"Transaction failed! Status: {receipt['status']}")
                        return False

                logger.info(f"Attempt {attempt + 1}/{max_attempts}: Pending...")
                time.sleep(3)

            except Exception as e:
                # Receipt not found yet
                logger.info(f"Attempt {attempt + 1}/{max_attempts}: Not mined yet...")
                time.sleep(3)

        logger.warning("Transaction confirmation timeout")
        return False

    def swap(
        self,
        from_token: str,
        to_token: str,
        amount: int,
        slippage: float = 1.0,
        simulate: bool = False
    ) -> bool:
        """
        Execute a token swap

        Args:
            from_token: Input token address
            to_token: Output token address
            amount: Amount in smallest unit (wei for BNB)
            slippage: Slippage tolerance in percent
            simulate: If True, only get quote without executing

        Returns:
            True if successful, False otherwise
        """
        # Get quote first
        quote = self.get_quote(from_token, to_token, amount, slippage)
        if not quote:
            return False

        if simulate:
            logger.info("Simulation mode - transaction not executed")
            return True

        # Get swap transaction
        swap_data = self.get_swap_transaction(from_token, to_token, amount, slippage)
        if not swap_data:
            return False

        # Send transaction
        tx_hash = self.send_transaction(swap_data)
        if not tx_hash:
            return False

        # Wait for confirmation
        confirmed = self.get_transaction_status(tx_hash)

        if confirmed:
            logger.info(f"Swap successful!")
            logger.info(f"Explorer: https://bscscan.com/tx/{tx_hash}")
            return True
        else:
            logger.error("Swap failed or timed out")
            return False


def bnb_to_wei(bnb_amount: float) -> int:
    """Convert BNB to wei"""
    return int(bnb_amount * 1e18)


def get_token_address(token_symbol: str) -> Optional[str]:
    """Get token address by symbol"""
    token_upper = token_symbol.upper()
    if token_upper in TOKENS:
        return TOKENS[token_upper]

    # If not found, assume it's an address
    if len(token_symbol) > 30:
        return token_symbol

    return None


def main():
    """Main execution function"""
    print("=" * 60)
    print("BSC Swap - BNB to Token Swapper (via 1inch)")
    print("=" * 60)
    print()

    # Get private key
    private_key = input("Enter your private key (hex): ").strip()
    if not private_key:
        logger.error("Private key is required")
        return

    # Initialize swap handler
    try:
        swap_handler = BSCSwap(private_key)
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        return

    # Show BNB balance
    bnb_balance = swap_handler.get_bnb_balance()
    print(f"\nYour BNB Balance: {bnb_balance:.6f} BNB\n")

    # Get swap parameters
    print("Available tokens:")
    for symbol, address in TOKENS.items():
        print(f"  {symbol}: {address}")
    print()

    # From token (default BNB)
    from_token_input = input("From token (default: BNB): ").strip() or 'BNB'
    from_token = get_token_address(from_token_input)
    if not from_token:
        logger.error(f"Unknown token: {from_token_input}")
        return

    # To token
    to_token_input = input("To token (symbol or address): ").strip()
    if not to_token_input:
        logger.error("To token is required")
        return

    to_token = get_token_address(to_token_input)
    if not to_token:
        logger.error(f"Unknown token: {to_token_input}")
        return

    # Amount
    try:
        amount_str = input(f"Amount in {from_token_input}: ").strip()
        amount_float = float(amount_str)
        amount = bnb_to_wei(amount_float)
    except ValueError:
        logger.error("Invalid amount")
        return

    # Slippage
    try:
        slippage_str = input("Slippage % (default: 1.0): ").strip() or "1.0"
        slippage = float(slippage_str)
    except ValueError:
        logger.error("Invalid slippage")
        return

    # Simulate option
    simulate_input = input("Simulate only? (y/N): ").strip().lower()
    simulate = simulate_input == 'y'

    # Execute swap
    print("\n" + "=" * 60)
    print("Executing swap...")
    print("=" * 60)
    print()

    success = swap_handler.swap(
        from_token=from_token,
        to_token=to_token,
        amount=amount,
        slippage=slippage,
        simulate=simulate
    )

    if success:
        print("\n" + "=" * 60)
        print("Swap completed successfully!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Swap failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
