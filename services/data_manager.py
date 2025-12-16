"""
Data Manager Service
Handles all data persistence operations for user wallets and trading data
"""

import json
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DataManager:
    """Manages persistent storage of user wallet data"""

    def __init__(self, wallets_dir: Path, config: Dict[str, Any]):
        """
        Initialize Data Manager

        Args:
            wallets_dir: Directory path for wallet storage
            config: Bot configuration dictionary
        """
        self.wallets_dir = wallets_dir
        self.config = config
        self.user_wallets_file = wallets_dir / 'user_wallets.json'
        self.user_wallets = self.load_user_wallets()

        # Ensure wallets directory exists
        self.wallets_dir.mkdir(parents=True, exist_ok=True)

    def load_user_wallets(self) -> Dict[str, Any]:
        """Load user wallet assignments from file"""
        if self.user_wallets_file.exists():
            try:
                with open(self.user_wallets_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading user wallets: {e}")
                return {}
        return {}

    def save_user_wallets(self) -> bool:
        """Save user wallet assignments to file"""
        try:
            with open(self.user_wallets_file, 'w') as f:
                json.dump(self.user_wallets, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving user wallets: {e}")
            return False

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Get user wallet data, auto-migrating if needed

        Args:
            user_id: Telegram user ID

        Returns:
            User wallet data dictionary
        """
        user_id_str = str(user_id)

        # Auto-migrate old format if needed
        if self.needs_migration(user_id_str):
            self.migrate_user_data(user_id_str)

        return self.user_wallets.get(user_id_str, {})

    def set_user_data(self, user_id: int, data: Dict[str, Any]) -> bool:
        """
        Set user wallet data

        Args:
            user_id: Telegram user ID
            data: User data dictionary

        Returns:
            Success status
        """
        user_id_str = str(user_id)
        self.user_wallets[user_id_str] = data
        return self.save_user_wallets()

    def update_user_data(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields in user data

        Args:
            user_id: Telegram user ID
            updates: Dictionary of fields to update

        Returns:
            Success status
        """
        user_id_str = str(user_id)
        if user_id_str not in self.user_wallets:
            self.user_wallets[user_id_str] = {}

        self.user_wallets[user_id_str].update(updates)
        return self.save_user_wallets()

    def delete_user_data(self, user_id: int) -> bool:
        """
        Delete all user data

        Args:
            user_id: Telegram user ID

        Returns:
            Success status
        """
        user_id_str = str(user_id)
        if user_id_str in self.user_wallets:
            del self.user_wallets[user_id_str]
            return self.save_user_wallets()
        return False

    def needs_migration(self, user_id_str: str) -> bool:
        """
        Check if user data needs migration to new multi-wallet format

        Args:
            user_id_str: User ID as string

        Returns:
            True if migration needed
        """
        if user_id_str not in self.user_wallets:
            return False

        user_data = self.user_wallets[user_id_str]

        # Old format has 'wallets' but not 'wallet_slots'
        return 'wallets' in user_data and 'wallet_slots' not in user_data

    def migrate_user_data(self, user_id_str: str) -> bool:
        """
        Migrate user from old single-wallet to new multi-wallet structure

        Args:
            user_id_str: User ID as string

        Returns:
            Success status
        """
        if user_id_str not in self.user_wallets:
            return False

        user_data = self.user_wallets[user_id_str]

        if 'wallets' not in user_data:
            return False  # Nothing to migrate

        # Get max slots from config
        max_slots = self.config.get('settings', {}).get('max_wallet_slots_per_user', 3)

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

    def get_primary_wallet(self, user_id: int) -> Optional[str]:
        """
        Get the primary wallet slot name for a user

        Args:
            user_id: Telegram user ID

        Returns:
            Primary wallet slot name or None
        """
        user_data = self.get_user_data(user_id)
        return user_data.get('primary_wallet')

    def set_primary_wallet(self, user_id: int, slot_name: str) -> bool:
        """
        Set the primary wallet slot for a user

        Args:
            user_id: Telegram user ID
            slot_name: Wallet slot name (e.g., 'wallet1')

        Returns:
            Success status
        """
        user_data = self.get_user_data(user_id)

        if not user_data or 'wallet_slots' not in user_data:
            return False

        # Check if slot exists (allow empty slots)
        if slot_name not in user_data['wallet_slots']:
            return False

        # Update primary flags
        old_primary = user_data.get('primary_wallet')
        if old_primary and old_primary in user_data['wallet_slots']:
            user_data['wallet_slots'][old_primary]['is_primary'] = False

        user_data['primary_wallet'] = slot_name
        user_data['wallet_slots'][slot_name]['is_primary'] = True

        return self.set_user_data(user_id, user_data)

    def get_wallet_slot(self, user_id: int, slot_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific wallet slot data

        Args:
            user_id: Telegram user ID
            slot_name: Wallet slot name

        Returns:
            Wallet slot data or None
        """
        user_data = self.get_user_data(user_id)
        if 'wallet_slots' in user_data:
            return user_data['wallet_slots'].get(slot_name)
        return None

    def update_wallet_slot(self, user_id: int, slot_name: str, slot_data: Dict[str, Any]) -> bool:
        """
        Update a wallet slot

        Args:
            user_id: Telegram user ID
            slot_name: Wallet slot name
            slot_data: Slot data to update

        Returns:
            Success status
        """
        user_data = self.get_user_data(user_id)

        if 'wallet_slots' not in user_data:
            user_data['wallet_slots'] = {}

        user_data['wallet_slots'][slot_name] = slot_data
        return self.set_user_data(user_id, user_data)

    def delete_wallet_slot(self, user_id: int, slot_name: str) -> bool:
        """
        Delete a wallet slot

        Args:
            user_id: Telegram user ID
            slot_name: Wallet slot name

        Returns:
            Success status
        """
        user_data = self.get_user_data(user_id)

        if 'wallet_slots' not in user_data or slot_name not in user_data['wallet_slots']:
            return False

        # Reset the slot instead of deleting
        user_data['wallet_slots'][slot_name] = {
            'label': None,
            'created_at': None,
            'is_primary': False,
            'chains': {}
        }

        # If this was the primary wallet, switch to wallet1
        if user_data.get('primary_wallet') == slot_name:
            user_data['primary_wallet'] = 'wallet1'
            user_data['wallet_slots']['wallet1']['is_primary'] = True

        return self.set_user_data(user_id, user_data)

    def get_available_slots(self, user_id: int) -> list:
        """
        Get list of available (empty) wallet slots

        Args:
            user_id: Telegram user ID

        Returns:
            List of available slot names
        """
        user_data = self.get_user_data(user_id)
        available = []

        if 'wallet_slots' in user_data:
            for slot_name, slot_data in user_data['wallet_slots'].items():
                if not slot_data.get('chains'):
                    available.append(slot_name)

        return available
