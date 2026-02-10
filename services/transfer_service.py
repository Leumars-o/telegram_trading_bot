"""
Transfer Service
Handles cryptocurrency transfers between wallets
"""

import base64
import logging
from typing import Optional, Dict, Any
from solders.keypair import Keypair
from solders.transaction import Transaction
from solders.system_program import transfer, TransferParams
from solders.pubkey import Pubkey
from solders.hash import Hash
from solders.message import Message
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
            rpc_url = self.networks['SOL']['rpc']

            # Load keypair from hex private key
            private_key_bytes = bytes.fromhex(from_private_key)
            if len(private_key_bytes) == 32:
                keypair = Keypair.from_seed(private_key_bytes)
            else:
                keypair = Keypair.from_bytes(private_key_bytes)

            # Create transfer instruction
            transfer_ix = transfer(
                TransferParams(
                    from_pubkey=keypair.pubkey(),
                    to_pubkey=Pubkey.from_string(to_address),
                    lamports=amount_lamports
                )
            )

            # Get recent blockhash via RPC
            blockhash_resp = requests.post(rpc_url, json={
                'jsonrpc': '2.0', 'id': 1,
                'method': 'getLatestBlockhash',
                'params': [{'commitment': 'confirmed'}]
            })
            blockhash_data = blockhash_resp.json()
            recent_blockhash = Hash.from_string(
                blockhash_data['result']['value']['blockhash']
            )

            # Build and sign transaction
            msg = Message.new_with_blockhash(
                [transfer_ix], keypair.pubkey(), recent_blockhash
            )
            tx = Transaction([keypair], msg, recent_blockhash)

            # Send transaction via RPC
            tx_bytes = bytes(tx)
            tx_base64 = base64.b64encode(tx_bytes).decode('utf-8')

            send_resp = requests.post(rpc_url, json={
                'jsonrpc': '2.0', 'id': 1,
                'method': 'sendTransaction',
                'params': [
                    tx_base64,
                    {
                        'encoding': 'base64',
                        'skipPreflight': False,
                        'preflightCommitment': 'confirmed',
                        'maxRetries': 3
                    }
                ]
            })
            send_data = send_resp.json()

            if 'error' in send_data:
                logger.error(f"Solana RPC error: {send_data['error']}")
                return None

            signature = send_data['result']
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
            from web3 import Web3
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
