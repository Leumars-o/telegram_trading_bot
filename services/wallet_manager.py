"""
Wallet Manager Service
Handles wallet creation, import, and key derivation operations
"""

import logging
import datetime
from typing import Dict, Any, Optional
from eth_account import Account
from solders.keypair import Keypair
from bip_utils import Bip39SeedGenerator, Bip39MnemonicGenerator, Bip39WordsNum, Bip44, Bip44Coins, Bip44Changes

logger = logging.getLogger(__name__)


class WalletManager:
    """Manages cryptocurrency wallet operations"""

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

    def derive_address_from_seed(self, seed_phrase: str, network: str, index: int = 0) -> Optional[Dict[str, str]]:
        """
        Derive wallet address and private key from seed phrase

        Args:
            seed_phrase: BIP39 seed phrase
            network: Network identifier ('SOL', 'ETH', 'STACKS')
            index: Derivation index (default 0)

        Returns:
            Dictionary with 'address' and 'private_key' or None
        """
        try:
            seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()

            if network == 'SOL':
                return self._derive_solana(seed_bytes, index)
            elif network == 'ETH':
                return self._derive_ethereum(seed_bytes, index)
            elif network == 'STACKS':
                return self._derive_stacks(seed_bytes, index)
            else:
                logger.error(f"Unsupported network: {network}")
                return None

        except Exception as e:
            logger.error(f"Error deriving address for {network}: {e}")
            return None

    def _derive_solana(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """Derive Solana wallet"""
        bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.SOLANA)
        bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
        bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
        bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

        private_key_bytes = bip44_addr_ctx.PrivateKey().Raw().ToBytes()
        # Use from_seed() for 32-byte seed instead of from_bytes() which expects 64 bytes
        keypair = Keypair.from_seed(private_key_bytes[:32])

        return {
            'address': str(keypair.pubkey()),
            'private_key': private_key_bytes[:32].hex()
        }

    def _derive_ethereum(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """Derive Ethereum wallet"""
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

    def _derive_stacks(self, seed_bytes: bytes, index: int = 0) -> Dict[str, str]:
        """Derive Stacks wallet"""
        bip44_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.BITCOIN)
        bip44_acc_ctx = bip44_ctx.Purpose().Coin().Account(0)
        bip44_chg_ctx = bip44_acc_ctx.Change(Bip44Changes.CHAIN_EXT)
        bip44_addr_ctx = bip44_chg_ctx.AddressIndex(index)

        private_key = bip44_addr_ctx.PrivateKey().Raw().ToHex()

        return {
            'address': 'Stacks address derivation requires additional setup',
            'private_key': private_key
        }

    def create_wallet(self, user_id: int, network: str, slot_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Create a new wallet for a user

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

            # Derive wallet
            wallet_info = self.derive_address_from_seed(seed_phrase, network)
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

            return {
                'slot_name': slot_name,
                'network': network,
                'address': wallet_info['address'],
                'seed_phrase': seed_phrase
            }

        except Exception as e:
            logger.error(f"Error creating wallet: {e}")
            return None

    def import_wallet(self, user_id: int, network: str, seed_phrase: str, slot_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Import an existing wallet from seed phrase

        Args:
            user_id: Telegram user ID
            network: Network identifier
            seed_phrase: BIP39 seed phrase
            slot_name: Wallet slot name (optional)

        Returns:
            Imported wallet info or None
        """
        try:
            # Validate and derive wallet
            wallet_info = self.derive_address_from_seed(seed_phrase, network)
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
                'created_at': datetime.datetime.now().isoformat(),
                'seed_phrase': seed_phrase,
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

            return {
                'slot_name': slot_name,
                'network': network,
                'address': wallet_info['address']
            }

        except Exception as e:
            logger.error(f"Error importing wallet: {e}")
            return None

    def get_wallet_private_key(self, user_id: int, network: str, slot_name: str = None) -> Optional[str]:
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
