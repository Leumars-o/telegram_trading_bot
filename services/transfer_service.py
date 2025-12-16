"""
Transfer Service
Handles cryptocurrency transfers between wallets
"""

import logging
from typing import Optional, Dict, Any
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.pubkey import Pubkey
from web3 import Web3
import requests

logger = logging.getLogger(__name__)


class TransferService:
    """Handles transfer operations for different blockchains"""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Transfer Service

        Args:
            config: Bot configuration dictionary
        """
        self.config = config
        self.networks = self._build_network_config()

    def _build_network_config(self) -> Dict[str, Any]:
        """Build network configuration"""
        networks = {}
        for chain_key, chain_config in self.config['chains'].items():
            if chain_config.get('enabled', True):
                networks[chain_key] = {
                    'rpc': chain_config['rpc'],
                    'decimals': chain_config['decimals'],
                }
        return networks

    async def execute_solana_transfer(
        self,
        from_private_key: str,
        to_address: str,
        amount_lamports: int
    ) -> Optional[str]:
        """
        Execute a Solana transfer

        Args:
            from_private_key: Sender's private key (hex format)
            to_address: Recipient's address
            amount_lamports: Amount in lamports

        Returns:
            Transaction signature or None
        """
        try:
            # Import Solana libraries
            from solana.rpc.api import Client
            from solana.transaction import Transaction as SolanaTransaction
            from solana.system_program import TransferParams as SolanaTransferParams, transfer as solana_transfer
            from solders.keypair import Keypair as SoldersKeypair
            from solders.pubkey import Pubkey as SoldersPubkey

            # Initialize client
            client = Client(self.networks['SOL']['rpc'])

            # Load keypair
            private_key_bytes = bytes.fromhex(from_private_key)
            keypair = SoldersKeypair.from_bytes(private_key_bytes[:32])

            # Create transfer instruction
            transfer_ix = solana_transfer(
                SolanaTransferParams(
                    from_pubkey=keypair.pubkey(),
                    to_pubkey=SoldersPubkey.from_string(to_address),
                    lamports=amount_lamports
                )
            )

            # Create and send transaction
            recent_blockhash = client.get_latest_blockhash().value.blockhash
            transaction = SolanaTransaction().add(transfer_ix)
            transaction.recent_blockhash = recent_blockhash
            transaction.fee_payer = keypair.pubkey()

            # Sign and send
            response = client.send_transaction(transaction, keypair)
            signature = str(response.value)

            logger.info(f"Solana transfer successful: {signature}")
            return signature

        except Exception as e:
            logger.error(f"Error executing Solana transfer: {e}", exc_info=True)
            return None

    async def execute_ethereum_transfer(
        self,
        from_private_key: str,
        to_address: str,
        amount_wei: int
    ) -> Optional[str]:
        """
        Execute an Ethereum transfer

        Args:
            from_private_key: Sender's private key
            to_address: Recipient's address
            amount_wei: Amount in wei

        Returns:
            Transaction hash or None
        """
        try:
            # Initialize Web3
            w3 = Web3(Web3.HTTPProvider(self.networks['ETH']['rpc']))

            # Get account from private key
            from eth_account import Account
            account = Account.from_key(from_private_key)

            # Build transaction
            nonce = w3.eth.get_transaction_count(account.address)
            gas_price = w3.eth.gas_price

            transaction = {
                'nonce': nonce,
                'to': to_address,
                'value': amount_wei,
                'gas': 21000,
                'gasPrice': gas_price,
                'chainId': 1  # Mainnet
            }

            # Sign and send
            signed_txn = account.sign_transaction(transaction)
            tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

            logger.info(f"Ethereum transfer successful: {tx_hash.hex()}")
            return tx_hash.hex()

        except Exception as e:
            logger.error(f"Error executing Ethereum transfer: {e}", exc_info=True)
            return None
