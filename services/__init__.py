"""
Services Package for Tenex Trading Bot
Modular microservice-style architecture

Each service handles a specific domain:
- DataManager: User data persistence
- WalletManager: Wallet creation/import/management
- BalanceService: Balance queries and price fetching
- TokenService: Token detection and info fetching
- TransferService: Blockchain transfers
- LimitOrderService: Limit sell order management
- NotificationService: Admin notifications to channels/groups
"""

from .data_manager import DataManager
from .wallet_manager import WalletManager
from .balance_service import BalanceService
from .token_service import TokenService
from .transfer_service import TransferService
from .limit_order_service import LimitOrderService
from .notification_service import NotificationService

__all__ = [
    'DataManager',
    'WalletManager',
    'BalanceService',
    'TokenService',
    'TransferService',
    'LimitOrderService',
    'NotificationService',
]
