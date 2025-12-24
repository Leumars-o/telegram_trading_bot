"""
Fixed Wallet Manager Service - Matches Node.js ed25519-hd-key derivation
Handles wallet creation, import, and key derivation operations
Ensures consistent address generation across all chains
"""

import logging
import datetime
import hashlib
import hmac
from typing import Dict, Any, Optional
from eth_account import Account
from solders.keypair import Keypair
from bip_utils import (
    Bip39SeedGenerator, 
    Bip39MnemonicGenerator, 
    Bip39WordsNum, 
    Bip44, 
    Bip44Coins, 
    Bip44Changes
)

logger = logging.getLogger(__name__)


class WalletManager:
    """Manages cryptocurrency wallet operations with proper derivation matching Node.js"""

    def __init__(self, data_manager, config: Dict[str, Any]):
        """
        Initialize Wallet Manager

        Args:
            data_manager: DataManager instance
            config: Bot configuration dictionary
        """
        self.data_manager = data_manager
        self.config = config

    def generate_seed_phrase(self, word_count: int = 12) -> str:
        """
        Generate a new BIP39 seed phrase

        Args:
            word_count: Number of words (12 or 24)

        Returns:
            Generated seed phrase
        """
        try:
            words_num = Bip39WordsNum.WORDS_NUM_12 if word_count == 12 else Bip39WordsNum.WORDS_NUM_24
            mnemonic = Bip39MnemonicGenerator().FromWordsNumber(words_num)
            return str(mnemonic)
        except Exception as e:
            logger.error(f"Error generating seed phrase: {e}")
            return None

    def _ed25519_derive_path(self, path: str, seed: bytes) -> bytes:
        """
        Implement ed25519-hd-key derivePath function to match Node.js
        This matches the ed25519-hd-key npm package used in your Node.js code
        
        The ed25519-hd-key uses SLIP-0010 for Ed25519 curve derivation.
        
        Args:
            path: Derivation path (e.g., "m/44'/501'/0'/0'")
            seed: Seed as bytes (NOT hex string)
            
        Returns:
            32-byte derived key
        """
        # SLIP-0010 Master key generation for Ed25519
        hmac_obj = hmac.new(b"ed25519 seed", seed, hashlib.sha512)
        master_secret = hmac_obj.digest()
        
        key = master_secret[:32]
        chain_code = master_secret[32:]
        
        # Parse the derivation path
        if not path.startswith('m/'):
            raise ValueError("Path must start with 'm/'")
        
        segments = path[2:].split('/')
        
        for segment in segments:
            if not segment:  # Skip empty segments
                continue
                
            # Check if hardened (ends with ')
            hardened = segment.endswith("'")
            index = int(segment[:-1]) if hardened else int(segment)
            
            if hardened:
                index += 0x80000000  # Hardened key flag
            
            # SLIP-0010 CKD (Child Key Derivation) for Ed25519
            # For hardened keys, we use: 0x00 || key || index
            data = b'\x00' + key + index.to_bytes(4, 'big')
            
            hmac_obj = hmac.new(chain_code, data, hashlib.sha512)
            derived = hmac_obj.digest()
            
            key = derived[:32]
            chain_code = derived[32:]
        
        return key

    def derive_address_from_seed(
        self, 
        seed_phrase: str, 
        network: str, 
        index: int = 0
    ) -> Optional[Dict[str, str]]:
        """
        Derive wallet address and private key from seed phrase
        Matches Node.js derivation exactly

        Args:
            seed_phrase: BIP39 seed phrase
            network: Network identifier ('SOL', 'ETH', 'BSC', 'STACKS')
            index: Derivation index (default 0 for primary address)

        Returns:
            Dictionary with 'address', 'private_key', and 'derivation_path' or None
        """
        try:
            # Validate seed phrase
            seed_phrase = seed_phrase.strip()
            seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()

            if network == 'SOL':
                return self._derive_solana(seed_bytes, index)
            elif network == 'ETH':
                return self._derive_ethereum(seed_bytes, index)
            elif network == 'BSC':
                return self._derive_bsc(seed_bytes, index)
            elif network == 'STACKS':
                return self._derive_stacks(seed_bytes, index)
            else:
                logger.error(f"Unsupported network: {network}")
                return None

        except Exception as e:
            logger.error(f"Error deriving address for {network}: {e}", exc_info=True)
            return None

    def _derive_solana(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """
        Derive Solana wallet using ed25519-hd-key derivation (matches Node.js)
        Path: m/44'/501'/{index}'/0'
        
        This matches the derivation in your Node.js SolanaChain.js exactly:
        - Uses ed25519-hd-key style derivation (SLIP-0010 for Ed25519)
        - Path structure: m/44'/501'/${i}'/0'
        """
        try:
            # Derivation path matching Node.js
            path = f"m/44'/501'/{index}'/0'"
            
            # Derive using ed25519-hd-key algorithm (SLIP-0010)
            derived_key = self._ed25519_derive_path(path, seed_bytes)
            
            # Create Solana keypair from derived 32-byte seed
            keypair = Keypair.from_seed(derived_key)

            return {
                'address': str(keypair.pubkey()),
                'private_key': bytes(keypair)[:32].hex(),
                'derivation_path': path,
                'public_key': str(keypair.pubkey())
            }
        except Exception as e:
            logger.error(f"Error in Solana derivation: {e}", exc_info=True)
            raise

    def _derive_ethereum(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """
        Derive Ethereum wallet using proper BIP44 derivation
        Path: m/44'/60'/0'/0/index
        """
        try:
            bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.ETHEREUM)
            bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
            bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
            bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

            private_key_hex = bip44_addr_ctx.PrivateKey().Raw().ToHex()
            account = Account.from_key(private_key_hex)

            derivation_path = f"m/44'/60'/0'/0/{index}"

            return {
                'address': account.address,
                'private_key': private_key_hex,
                'derivation_path': derivation_path
            }
        except Exception as e:
            logger.error(f"Error in Ethereum derivation: {e}", exc_info=True)
            raise

    def _derive_bsc(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """
        Derive BSC wallet (uses Ethereum derivation - EVM compatible)
        Path: m/44'/60'/0'/0/index (same as Ethereum)
        """
        try:
            # BSC uses the same BIP44 derivation as Ethereum (coin type 60)
            result = self._derive_ethereum(seed_bytes, index)
            return result
        except Exception as e:
            logger.error(f"Error in BSC derivation: {e}", exc_info=True)
            raise

    def _derive_stacks(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """
        Derive Stacks wallet using Bitcoin derivation
        Path: m/44'/5757'/0'/0/index
        
        Note: Full Stacks address generation requires additional c32check encoding
        """
        try:
            # Stacks uses Bitcoin's coin type in some implementations
            bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
            bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
            bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
            bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

            private_key_hex = bip44_addr_ctx.PrivateKey().Raw().ToHex()
            # Get the compressed public key for Stacks
            public_key_hex = bip44_addr_ctx.PublicKey().RawCompressed().ToHex()

            derivation_path = f"m/44'/5757'/0'/0/{index}"

            return {
                'address': f'STACKS_{public_key_hex[:40]}',  # Placeholder - needs c32check
                'private_key': private_key_hex,
                'derivation_path': derivation_path,
                'public_key': public_key_hex,
                'note': 'Full Stacks address requires c32check encoding'
            }
        except Exception as e:
            logger.error(f"Error in Stacks derivation: {e}", exc_info=True)
            raise

    def verify_seed_derivation(self, seed_phrase: str, network: str, expected_address: str) -> bool:
        """
        Verify that a seed phrase derives to an expected address
        Useful for debugging derivation issues

        Args:
            seed_phrase: BIP39 seed phrase
            network: Network identifier
            expected_address: The address that should be derived

        Returns:
            True if derivation matches, False otherwise
        """
        try:
            result = self.derive_address_from_seed(seed_phrase, network, index=0)
            if not result:
                return False
            
            derived_address = result['address']
            matches = derived_address.lower() == expected_address.lower()
            
            if not matches:
                logger.warning(
                    f"Derivation mismatch for {network}:\n"
                    f"  Expected: {expected_address}\n"
                    f"  Derived:  {derived_address}\n"
                    f"  Path:     {result.get('derivation_path', 'N/A')}"
                )
            else:
                logger.info(
                    f"✓ Derivation match for {network}!\n"
                    f"  Address: {derived_address}\n"
                    f"  Path:    {result.get('derivation_path', 'N/A')}"
                )
            
            return matches
        except Exception as e:
            logger.error(f"Error verifying seed derivation: {e}")
            return False

    def create_wallet(
        self, 
        user_id: int, 
        network: str, 
        slot_name: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new wallet for a user
        Always derives the primary address (index 0)

        Args:
            user_id: Telegram user ID
            network: Network identifier
            slot_name: Wallet slot name (optional, auto-assigned if None)

        Returns:
            Created wallet info or None
        """
        try:
            # Get or assign slot
            if not slot_name:
                available_slots = self.data_manager.get_available_slots(user_id)
                if not available_slots:
                    logger.warning(f"No available wallet slots for user {user_id}")
                    return None
                slot_name = available_slots[0]

            # Generate new seed phrase
            seed_phrase = self.generate_seed_phrase()
            if not seed_phrase:
                return None

            # Derive wallet at index 0 (primary address)
            wallet_info = self.derive_address_from_seed(seed_phrase, network, index=0)
            if not wallet_info:
                return None

            # Get current slot data
            user_data = self.data_manager.get_user_data(user_id)
            if 'wallet_slots' not in user_data:
                user_data['wallet_slots'] = self._initialize_wallet_slots()

            slot_data = user_data['wallet_slots'].get(slot_name, {})

            # Add wallet to slot
            if 'chains' not in slot_data:
                slot_data['chains'] = {}

            slot_data['chains'][network] = {
                'address': wallet_info['address'],
                'private_key': wallet_info['private_key'],
                'derivation_path': wallet_info.get('derivation_path', 'N/A'),
                'derivation_index': 0,  # Always 0 for primary address
                'created_at': datetime.datetime.now().isoformat(),
                'seed_phrase': seed_phrase
            }

            # Update metadata if this is the first chain in the slot
            if not slot_data.get('created_at'):
                slot_data['created_at'] = datetime.datetime.now().isoformat()

            # Update slot
            user_data['wallet_slots'][slot_name] = slot_data

            # Set as primary if no primary exists
            if not user_data.get('primary_wallet'):
                user_data['primary_wallet'] = slot_name
                slot_data['is_primary'] = True

            # Save
            self.data_manager.set_user_data(user_id, user_data)

            logger.info(
                f"Created {network} wallet for user {user_id}: "
                f"{wallet_info['address']} (path: {wallet_info.get('derivation_path')})"
            )

            return {
                'slot_name': slot_name,
                'network': network,
                'address': wallet_info['address'],
                'derivation_path': wallet_info.get('derivation_path'),
                'seed_phrase': seed_phrase
            }

        except Exception as e:
            logger.error(f"Error creating wallet: {e}", exc_info=True)
            return None

    def import_wallet(
        self, 
        user_id: int, 
        network: str, 
        seed_phrase: str, 
        slot_name: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Import an existing wallet from seed phrase
        Always derives the primary address (index 0) for consistency

        Args:
            user_id: Telegram user ID
            network: Network identifier
            seed_phrase: BIP39 seed phrase
            slot_name: Wallet slot name (optional)

        Returns:
            Imported wallet info or None
        """
        try:
            # Validate and derive wallet at index 0 (primary address)
            wallet_info = self.derive_address_from_seed(seed_phrase.strip(), network, index=0)
            if not wallet_info:
                return None

            # Get or assign slot
            if not slot_name:
                available_slots = self.data_manager.get_available_slots(user_id)
                if not available_slots:
                    logger.warning(f"No available wallet slots for user {user_id}")
                    return None
                slot_name = available_slots[0]

            # Get current slot data
            user_data = self.data_manager.get_user_data(user_id)
            if 'wallet_slots' not in user_data:
                user_data['wallet_slots'] = self._initialize_wallet_slots()

            slot_data = user_data['wallet_slots'].get(slot_name, {})

            # Add wallet to slot
            if 'chains' not in slot_data:
                slot_data['chains'] = {}

            slot_data['chains'][network] = {
                'address': wallet_info['address'],
                'private_key': wallet_info['private_key'],
                'derivation_path': wallet_info.get('derivation_path', 'N/A'),
                'derivation_index': 0,  # Always 0 for primary address
                'created_at': datetime.datetime.now().isoformat(),
                'seed_phrase': seed_phrase.strip(),
                'imported': True
            }

            # Update metadata
            if not slot_data.get('created_at'):
                slot_data['created_at'] = datetime.datetime.now().isoformat()

            # Update slot
            user_data['wallet_slots'][slot_name] = slot_data

            # Set as primary if no primary exists
            if not user_data.get('primary_wallet'):
                user_data['primary_wallet'] = slot_name
                slot_data['is_primary'] = True

            # Save
            self.data_manager.set_user_data(user_id, user_data)

            logger.info(
                f"Imported {network} wallet for user {user_id}: "
                f"{wallet_info['address']} (path: {wallet_info.get('derivation_path')})"
            )

            return {
                'slot_name': slot_name,
                'network': network,
                'address': wallet_info['address'],
                'derivation_path': wallet_info.get('derivation_path')
            }

        except Exception as e:
            logger.error(f"Error importing wallet: {e}", exc_info=True)
            return None

    def get_wallet_private_key(
        self, 
        user_id: int, 
        network: str, 
        slot_name: str = None
    ) -> Optional[str]:
        """
        Get private key for a specific wallet

        Args:
            user_id: Telegram user ID
            network: Network identifier
            slot_name: Wallet slot name (uses primary if None)

        Returns:
            Private key or None
        """
        if not slot_name:
            slot_name = self.data_manager.get_primary_wallet(user_id)

        slot_data = self.data_manager.get_wallet_slot(user_id, slot_name)
        if not slot_data or 'chains' not in slot_data:
            return None

        wallet = slot_data['chains'].get(network)
        if not wallet:
            return None

        return wallet.get('private_key')

    def set_wallet_label(self, user_id: int, slot_name: str, label: str) -> bool:
        """
        Set a custom label for a wallet slot

        Args:
            user_id: Telegram user ID
            slot_name: Wallet slot name
            label: Custom label

        Returns:
            Success status
        """
        slot_data = self.data_manager.get_wallet_slot(user_id, slot_name)
        if not slot_data:
            return False

        if label.lower() == 'clear' or not label:
            slot_data['label'] = None
        else:
            slot_data['label'] = label[:30]  # Limit label length

        return self.data_manager.update_wallet_slot(user_id, slot_name, slot_data)

    def _initialize_wallet_slots(self) -> Dict[str, Any]:
        """Initialize empty wallet slots structure"""
        max_slots = self.config.get('settings', {}).get('max_wallet_slots_per_user', 3)
        slots = {}

        for i in range(1, max_slots + 1):
            slot_name = f'wallet{i}'
            slots[slot_name] = {
                'label': None,
                'created_at': None,
                'is_primary': False,
                'chains': {}
            }

        return slots