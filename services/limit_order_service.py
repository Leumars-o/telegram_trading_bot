"""
Limit Order Service
Manages limit sell orders based on price and market cap targets
"""

import json
import logging
import asyncio
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class LimitOrderService:
    """Service to manage and monitor limit sell orders"""

    def __init__(self, data_dir: Path):
        """
        Initialize Limit Order Service

        Args:
            data_dir: Directory path for limit order storage
        """
        self.data_dir = data_dir
        self.orders_file = data_dir / 'limit_orders.json'
        self.orders = self.load_orders()

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_orders(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load limit orders from file"""
        if self.orders_file.exists():
            try:
                with open(self.orders_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading limit orders: {e}")
                return {}
        return {}

    def save_orders(self) -> bool:
        """Save limit orders to file"""
        try:
            with open(self.orders_file, 'w') as f:
                json.dump(self.orders, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving limit orders: {e}")
            return False

    def create_limit_order(
        self,
        user_id: int,
        token_address: str,
        token_symbol: str,
        order_type: str,  # 'price' or 'market_cap'
        trigger_value: float,
        sell_percentage: float,
        chain: str = 'solana'
    ) -> Dict[str, Any]:
        """
        Create a new limit sell order

        Args:
            user_id: Telegram user ID
            token_address: Token contract address
            token_symbol: Token symbol
            order_type: Type of order ('price' or 'market_cap')
            trigger_value: Target price or market cap to trigger at
            sell_percentage: Percentage to sell (1-100)
            chain: Blockchain chain

        Returns:
            Created order dictionary
        """
        user_id_str = str(user_id)

        # Generate order ID
        order_id = f"limit_{user_id}_{token_address[:8]}_{int(datetime.datetime.now().timestamp())}"

        order = {
            'order_id': order_id,
            'user_id': user_id,
            'token_address': token_address,
            'token_symbol': token_symbol,
            'chain': chain,
            'order_type': order_type,
            'trigger_value': trigger_value,
            'sell_percentage': sell_percentage,
            'status': 'active',
            'created_at': datetime.datetime.now().isoformat(),
            'executed_at': None,
            'execution_price': None,
            'execution_market_cap': None,
            'error': None
        }

        # Add to user's orders
        if user_id_str not in self.orders:
            self.orders[user_id_str] = []

        self.orders[user_id_str].append(order)
        self.save_orders()

        logger.info(f"Created limit order {order_id} for user {user_id}")
        return order

    def get_user_orders(self, user_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all orders for a user

        Args:
            user_id: Telegram user ID
            status: Optional status filter ('active', 'executed', 'cancelled', 'failed')

        Returns:
            List of orders
        """
        user_id_str = str(user_id)
        orders = self.orders.get(user_id_str, [])

        if status:
            orders = [o for o in orders if o.get('status') == status]

        return orders

    def get_active_orders_by_token(self, user_id: int, token_address: str) -> List[Dict[str, Any]]:
        """
        Get active orders for a specific token

        Args:
            user_id: Telegram user ID
            token_address: Token contract address

        Returns:
            List of active orders for the token
        """
        user_id_str = str(user_id)
        orders = self.orders.get(user_id_str, [])

        return [
            o for o in orders
            if o.get('token_address') == token_address and o.get('status') == 'active'
        ]

    def get_all_active_orders(self) -> List[Dict[str, Any]]:
        """
        Get all active orders across all users

        Returns:
            List of all active orders
        """
        all_active = []

        for user_orders in self.orders.values():
            for order in user_orders:
                if order.get('status') == 'active':
                    all_active.append(order)

        return all_active

    def cancel_order(self, user_id: int, order_id: str) -> bool:
        """
        Cancel a limit order

        Args:
            user_id: Telegram user ID
            order_id: Order ID to cancel

        Returns:
            Success status
        """
        user_id_str = str(user_id)

        if user_id_str not in self.orders:
            return False

        for order in self.orders[user_id_str]:
            if order['order_id'] == order_id and order['status'] == 'active':
                order['status'] = 'cancelled'
                order['cancelled_at'] = datetime.datetime.now().isoformat()
                self.save_orders()
                logger.info(f"Cancelled order {order_id} for user {user_id}")
                return True

        return False

    def mark_order_executed(
        self,
        order_id: str,
        execution_price: float,
        execution_market_cap: float
    ) -> bool:
        """
        Mark an order as executed

        Args:
            order_id: Order ID
            execution_price: Price at execution
            execution_market_cap: Market cap at execution

        Returns:
            Success status
        """
        for user_orders in self.orders.values():
            for order in user_orders:
                if order['order_id'] == order_id and order['status'] == 'active':
                    order['status'] = 'executed'
                    order['executed_at'] = datetime.datetime.now().isoformat()
                    order['execution_price'] = execution_price
                    order['execution_market_cap'] = execution_market_cap
                    self.save_orders()
                    logger.info(f"Marked order {order_id} as executed")
                    return True

        return False

    def mark_order_failed(self, order_id: str, error: str) -> bool:
        """
        Mark an order as failed

        Args:
            order_id: Order ID
            error: Error message

        Returns:
            Success status
        """
        for user_orders in self.orders.values():
            for order in user_orders:
                if order['order_id'] == order_id and order['status'] == 'active':
                    order['status'] = 'failed'
                    order['failed_at'] = datetime.datetime.now().isoformat()
                    order['error'] = error
                    self.save_orders()
                    logger.error(f"Marked order {order_id} as failed: {error}")
                    return True

        return False

    def should_execute_order(
        self,
        order: Dict[str, Any],
        current_price: float,
        current_market_cap: float
    ) -> bool:
        """
        Check if an order should be executed based on current conditions

        Args:
            order: Order dictionary
            current_price: Current token price in USD
            current_market_cap: Current token market cap in USD

        Returns:
            True if order should execute
        """
        if order.get('status') != 'active':
            return False

        order_type = order.get('order_type')
        trigger_value = order.get('trigger_value', 0)

        if order_type == 'price':
            # Execute if current price >= target price
            return current_price >= trigger_value
        elif order_type == 'market_cap':
            # Execute if current market cap >= target market cap
            return current_market_cap >= trigger_value

        return False

    def get_order_summary(self, order: Dict[str, Any]) -> str:
        """
        Get a formatted summary of an order

        Args:
            order: Order dictionary

        Returns:
            Formatted string summary
        """
        order_type = order.get('order_type')
        trigger_value = order.get('trigger_value', 0)
        sell_pct = order.get('sell_percentage', 0)
        symbol = order.get('token_symbol', 'TOKEN')
        status = order.get('status', 'unknown')

        if order_type == 'price':
            trigger_str = f"${trigger_value:.10f}"
            condition = f"Price ≥ {trigger_str}"
        else:  # market_cap
            if trigger_value >= 1_000_000:
                trigger_str = f"${trigger_value/1_000_000:.2f}M"
            elif trigger_value >= 1_000:
                trigger_str = f"${trigger_value/1_000:.2f}K"
            else:
                trigger_str = f"${trigger_value:.2f}"
            condition = f"MCap ≥ {trigger_str}"

        status_emoji = {
            'active': '🟢',
            'executed': '✅',
            'cancelled': '❌',
            'failed': '⚠️'
        }.get(status, '⚪')

        return f"{status_emoji} {symbol}: Sell {sell_pct}% when {condition}"

    def delete_order(self, user_id: int, order_id: str) -> bool:
        """
        Permanently delete an order

        Args:
            user_id: Telegram user ID
            order_id: Order ID to delete

        Returns:
            Success status
        """
        user_id_str = str(user_id)

        if user_id_str not in self.orders:
            return False

        original_count = len(self.orders[user_id_str])
        self.orders[user_id_str] = [
            o for o in self.orders[user_id_str]
            if o['order_id'] != order_id
        ]

        if len(self.orders[user_id_str]) < original_count:
            self.save_orders()
            logger.info(f"Deleted order {order_id} for user {user_id}")
            return True

        return False
