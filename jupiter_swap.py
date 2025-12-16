"""
Jupiter Swap Script - Swap SOL to SPL Tokens
Uses Jupiter Aggregator API v6 for optimal routing and pricing
"""

import os
import sys
import json
import time
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import requests
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.pubkey import Pubkey
from solders.message import MessageV0
from solders.hash import Hash
from solders.instruction import Instruction
from base58 import b58decode, b58encode
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
JUPITER_API_BASE = "https://api.jup.ag/swap/v1"
JUPITER_API_KEY = os.getenv('JUPITER_API_KEY', '')  # REQUIRED - Get free key at https://portal.jup.ag/
HELIUS_RPC_URL = os.getenv('HELIUS_RPC_URL', '')
SOLANA_RPC = HELIUS_RPC_URL if HELIUS_RPC_URL else os.getenv('SOLANA_RPC', 'https://api.mainnet-beta.solana.com')

# Validate API key
if not JUPITER_API_KEY:
    logger.warning("="*60)
    logger.warning("JUPITER_API_KEY is not set!")
    logger.warning("Jupiter now requires an API key for all requests.")
    logger.warning("Get a FREE API key at: https://portal.jup.ag/")
    logger.warning("Add it to your .env file: JUPITER_API_KEY=your_key_here")
    logger.warning("See API_KEY_SETUP.md for detailed instructions.")
    logger.warning("="*60)

# Common token addresses on Solana
TOKENS = {
    'SOL': 'So11111111111111111111111111111111111111112',  # Wrapped SOL
    'USDC': 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    'USDT': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
    'BONK': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
    'JUP': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
    'RAY': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
    'WIF': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',
}


class JupiterSwap:
    """Jupiter Swap handler for Solana token swaps"""

    def __init__(self, private_key: str, rpc_url: str = SOLANA_RPC):
        """
        Initialize Jupiter Swap handler

        Args:
            private_key: Base58 or hex encoded private key
            rpc_url: Solana RPC endpoint
        """
        self.rpc_url = rpc_url
        self.session = requests.Session()

        # Load keypair from private key
        try:
            # Try hex format first
            if len(private_key) == 128:
                key_bytes = bytes.fromhex(private_key)
            else:
                # Try base58
                key_bytes = b58decode(private_key)

            self.keypair = Keypair.from_bytes(key_bytes)
            self.wallet_address = str(self.keypair.pubkey())
            logger.info(f"Initialized wallet: {self.wallet_address}")
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")
            raise ValueError(f"Invalid private key format: {e}")

    def get_token_balance(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """
        Get SPL token balance for the wallet

        Args:
            token_mint: Token mint address

        Returns:
            Dict with balance info or None if not found/error
            {
                'balance': int (raw token amount in smallest unit),
                'decimals': int,
                'uiAmount': float (human-readable amount),
                'tokenAccount': str (token account address)
            }
        """
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'getTokenAccountsByOwner',
                'params': [
                    self.wallet_address,
                    {
                        'mint': token_mint
                    },
                    {
                        'encoding': 'jsonParsed'
                    }
                ]
            }

            logger.info(f"Fetching token balance for {token_mint[:8]}...")
            response = self.session.post(
                self.rpc_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            result = response.json()

            if 'error' in result:
                logger.error(f"RPC error: {result['error']}")
                return None

            accounts = result.get('result', {}).get('value', [])

            if not accounts:
                logger.warning(f"No token account found for {token_mint[:8]}...")
                return {
                    'balance': 0,
                    'decimals': 6,
                    'uiAmount': 0.0,
                    'tokenAccount': None
                }

            # Get the first account (should only be one for a given mint)
            account = accounts[0]
            token_amount = account['account']['data']['parsed']['info']['tokenAmount']
            token_account_address = account['pubkey']

            balance_info = {
                'balance': int(token_amount['amount']),
                'decimals': token_amount['decimals'],
                'uiAmount': float(token_amount['uiAmount'] or 0),
                'tokenAccount': token_account_address
            }

            logger.info(f"Token balance: {balance_info['uiAmount']:.6f}")
            return balance_info

        except Exception as e:
            logger.error(f"Failed to get token balance: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Get swap quote from Jupiter

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Slippage tolerance in basis points (50 = 0.5%)

        Returns:
            Quote data or None if failed
        """
        try:
            params = {
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': amount,
                'slippageBps': slippage_bps,
                'onlyDirectRoutes': 'false',
                'asLegacyTransaction': 'false'
            }

            # Prepare headers with optional API key
            headers = {}
            if JUPITER_API_KEY:
                headers['x-api-key'] = JUPITER_API_KEY

            logger.info(f"Requesting quote for {amount} lamports...")
            response = self.session.get(f"{JUPITER_API_BASE}/quote", params=params, headers=headers)
            response.raise_for_status()

            quote = response.json()

            # Display quote info
            in_amount = int(quote['inAmount'])
            out_amount = int(quote['outAmount'])
            price_impact = float(quote.get('priceImpactPct', 0))

            logger.info(f"Quote received:")
            logger.info(f"  Input: {in_amount / 1e9:.9f} SOL")
            logger.info(f"  Output: {out_amount / 1e6:.6f} tokens")
            logger.info(f"  Price Impact: {price_impact:.4f}%")
            logger.info(f"  Routes: {len(quote.get('routePlan', []))}")

            return quote
        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
                # Check for 401 Unauthorized
                if e.response.status_code == 401:
                    logger.error("="*60)
                    logger.error("API KEY REQUIRED!")
                    logger.error("Get a FREE API key at: https://portal.jup.ag/")
                    logger.error("Add to .env: JUPITER_API_KEY=your_key_here")
                    logger.error("See API_KEY_SETUP.md for instructions.")
                    logger.error("="*60)
            return None

    def get_swap_transaction(
        self,
        quote: Dict[str, Any],
        user_public_key: str,
        wrap_unwrap_sol: bool = True,
        priority_fee: Optional[int] = None
    ) -> Optional[str]:
        """
        Get swap transaction from Jupiter

        Args:
            quote: Quote data from get_quote
            user_public_key: User's wallet address
            wrap_unwrap_sol: Automatically wrap/unwrap SOL
            priority_fee: Optional priority fee in lamports

        Returns:
            Serialized transaction or None if failed
        """
        try:
            payload = {
                'quoteResponse': quote,
                'userPublicKey': user_public_key,
                'wrapAndUnwrapSol': wrap_unwrap_sol,
                'dynamicComputeUnitLimit': True,
                'prioritizationFeeLamports': priority_fee or 'auto'
            }

            # Prepare headers with optional API key
            headers = {'Content-Type': 'application/json'}
            if JUPITER_API_KEY:
                headers['x-api-key'] = JUPITER_API_KEY

            logger.info("Requesting swap transaction...")
            response = self.session.post(
                f"{JUPITER_API_BASE}/swap",
                json=payload,
                headers=headers
            )
            response.raise_for_status()

            result = response.json()
            swap_transaction = result.get('swapTransaction')

            if not swap_transaction:
                logger.error("No transaction returned from Jupiter")
                return None

            logger.info("Swap transaction received")
            return swap_transaction
        except Exception as e:
            logger.error(f"Failed to get swap transaction: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None

    def send_transaction(self, signed_tx: str) -> Optional[str]:
        """
        Send signed transaction to Solana network

        Args:
            signed_tx: Base64 encoded signed transaction

        Returns:
            Transaction signature or None if failed
        """
        try:
            payload = {
                'jsonrpc': '2.0',
                'id': 1,
                'method': 'sendTransaction',
                'params': [
                    signed_tx,
                    {
                        'encoding': 'base64',
                        'skipPreflight': False,
                        'preflightCommitment': 'confirmed',
                        'maxRetries': 3
                    }
                ]
            }

            logger.info("Sending transaction to network...")
            response = self.session.post(
                self.rpc_url,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()

            result = response.json()

            if 'error' in result:
                logger.error(f"Transaction error: {result['error']}")
                return None

            signature = result.get('result')
            logger.info(f"Transaction sent: {signature}")
            return signature
        except Exception as e:
            logger.error(f"Failed to send transaction: {e}")
            return None

    def get_transaction_status(self, signature: str, max_attempts: int = 30) -> bool:
        """
        Poll transaction status until confirmed

        Args:
            signature: Transaction signature
            max_attempts: Maximum polling attempts

        Returns:
            True if confirmed, False otherwise
        """
        logger.info(f"Polling transaction status: {signature}")

        for attempt in range(max_attempts):
            try:
                payload = {
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getSignatureStatuses',
                    'params': [[signature]]
                }

                response = self.session.post(
                    self.rpc_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )
                response.raise_for_status()

                result = response.json()

                if 'result' in result and result['result']['value']:
                    status = result['result']['value'][0]

                    if status is None:
                        logger.info(f"Attempt {attempt + 1}/{max_attempts}: Not found yet...")
                    elif status.get('err'):
                        logger.error(f"Transaction failed: {status['err']}")
                        return False
                    elif status.get('confirmationStatus') in ['confirmed', 'finalized']:
                        logger.info(f"Transaction confirmed! Status: {status['confirmationStatus']}")
                        return True
                    else:
                        logger.info(f"Attempt {attempt + 1}/{max_attempts}: {status.get('confirmationStatus', 'processing')}")

                time.sleep(2)
            except Exception as e:
                logger.error(f"Error checking status: {e}")
                time.sleep(2)

        logger.warning("Transaction confirmation timeout")
        return False

    def swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
        simulate: bool = False
    ) -> bool:
        """
        Execute a token swap

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Slippage tolerance in basis points
            simulate: If True, only simulate without executing

        Returns:
            True if successful, False otherwise
        """
        # Get quote
        quote = self.get_quote(input_mint, output_mint, amount, slippage_bps)
        if not quote:
            return False

        if simulate:
            logger.info("Simulation mode - transaction not executed")
            return True

        # Get swap transaction
        swap_tx = self.get_swap_transaction(quote, self.wallet_address)
        if not swap_tx:
            return False

        # Deserialize and sign transaction
        try:
            logger.info("Signing transaction...")
            tx_bytes = base64.b64decode(swap_tx)
            transaction = VersionedTransaction.from_bytes(tx_bytes)

            # Get the message from the unsigned transaction
            message = transaction.message

            # Create a new signed transaction with the message and keypair
            # In solders, signing happens in the constructor
            signed_transaction = VersionedTransaction(message, [self.keypair])

            # Serialize signed transaction
            signed_tx = base64.b64encode(bytes(signed_transaction)).decode('utf-8')

            # Send transaction
            signature = self.send_transaction(signed_tx)
            if not signature:
                return False

            # Wait for confirmation
            confirmed = self.get_transaction_status(signature)

            if confirmed:
                logger.info(f"Swap successful!")
                logger.info(f"Explorer: https://solscan.io/tx/{signature}")
                return True
            else:
                logger.error("Swap failed or timed out")
                return False

        except Exception as e:
            logger.error(f"Failed to sign/send transaction: {e}")
            return False


def sol_to_lamports(sol_amount: float) -> int:
    """Convert SOL to lamports"""
    return int(sol_amount * 1e9)


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
    print("Jupiter Swap - SOL to Token Swapper")
    print("=" * 60)
    print()

    # Get private key
    private_key = input("Enter your private key (hex or base58): ").strip()
    if not private_key:
        logger.error("Private key is required")
        return

    # Initialize swap handler
    try:
        swap_handler = JupiterSwap(private_key)
    except Exception as e:
        logger.error(f"Failed to initialize: {e}")
        return

    # Get swap parameters
    print("\nAvailable tokens:")
    for symbol, address in TOKENS.items():
        print(f"  {symbol}: {address}")
    print()

    # Input token (default SOL)
    input_token = input("Input token (default: SOL): ").strip() or 'SOL'
    input_mint = get_token_address(input_token)
    if not input_mint:
        logger.error(f"Unknown token: {input_token}")
        return

    # Output token
    output_token = input("Output token (symbol or address): ").strip()
    if not output_token:
        logger.error("Output token is required")
        return

    output_mint = get_token_address(output_token)
    if not output_mint:
        logger.error(f"Unknown token: {output_token}")
        return

    # Amount
    try:
        amount_str = input(f"Amount in {input_token}: ").strip()
        amount_float = float(amount_str)

        # Convert to lamports if input is SOL
        if input_token.upper() == 'SOL':
            amount = sol_to_lamports(amount_float)
        else:
            # For other tokens, assume 6 decimals (most SPL tokens)
            amount = int(amount_float * 1e6)
    except ValueError:
        logger.error("Invalid amount")
        return

    # Slippage
    try:
        slippage_str = input("Slippage % (default: 0.5): ").strip() or "0.5"
        slippage_pct = float(slippage_str)
        slippage_bps = int(slippage_pct * 100)
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
        input_mint=input_mint,
        output_mint=output_mint,
        amount=amount,
        slippage_bps=slippage_bps,
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
