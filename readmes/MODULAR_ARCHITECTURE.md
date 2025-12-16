# Tenex Trading Bot - Modular Architecture

## Overview

The bot has been refactored from a monolithic 3,170-line file into a clean microservice-style architecture with separate service modules for each domain.

## Architecture

```
tenex-telegram-bot/
├── services/                    # Service modules (NEW)
│   ├── __init__.py             # Package exports
│   ├── data_manager.py         # User data persistence
│   ├── wallet_manager.py       # Wallet operations
│   ├── balance_service.py      # Balance & price fetching
│   ├── token_service.py        # Token detection & info
│   ├── transfer_service.py     # Blockchain transfers
│   └── menu_service.py         # UI/menu generation (placeholder)
│
├── tenex_trading_bot.py        # Main bot (REFACTOR IN PROGRESS)
├── trading_integration.py      # Trading features (existing)
└── jupiter_swap.py             # Jupiter swap handler (existing)
```

## Service Modules

### 1. DataManager (`services/data_manager.py`)
**Responsibility**: All data persistence operations

**Key Methods**:
- `get_user_data(user_id)` - Get user wallet data
- `set_user_data(user_id, data)` - Save user data
- `update_user_data(user_id, updates)` - Update specific fields
- `get_wallet_slot(user_id, slot_name)` - Get specific wallet slot
- `set_primary_wallet(user_id, slot_name)` - Set primary wallet
- `needs_migration(user_id)` - Check if migration needed
- `migrate_user_data(user_id)` - Migrate old format to new

**Example Usage**:
```python
from services import DataManager

# Initialize
data_mgr = DataManager(wallets_dir=Path('wallets'), config=CONFIG)

# Get user data
user_data = data_mgr.get_user_data(user_id=12345)

# Update primary wallet
data_mgr.set_primary_wallet(user_id=12345, slot_name='wallet2')
```

### 2. WalletManager (`services/wallet_manager.py`)
**Responsibility**: Wallet creation, import, and key derivation

**Key Methods**:
- `generate_seed_phrase(word_count=12)` - Generate BIP39 seed
- `derive_address_from_seed(seed, network, index)` - Derive wallet
- `create_wallet(user_id, network, slot_name)` - Create new wallet
- `import_wallet(user_id, network, seed, slot_name)` - Import wallet
- `get_wallet_private_key(user_id, network, slot_name)` - Get private key
- `set_wallet_label(user_id, slot_name, label)` - Set custom label

**Example Usage**:
```python
from services import WalletManager

# Initialize
wallet_mgr = WalletManager(data_manager=data_mgr, config=CONFIG)

# Create new Solana wallet
wallet_info = wallet_mgr.create_wallet(
    user_id=12345,
    network='SOL',
    slot_name='wallet1'
)
# Returns: {'slot_name': 'wallet1', 'network': 'SOL', 'address': '...', 'seed_phrase': '...'}

# Import existing wallet
imported = wallet_mgr.import_wallet(
    user_id=12345,
    network='ETH',
    seed_phrase='word1 word2 ...',
    slot_name='wallet2'
)
```

### 3. BalanceService (`services/balance_service.py`)
**Responsibility**: Balance checking and price fetching

**Key Methods**:
- `get_token_prices()` - Get USD prices from CoinGecko
- `get_balance(network, address)` - Get balance for any network
- `get_solana_balance(address)` - Get SOL balance
- `get_ethereum_balance(address)` - Get ETH balance
- `get_stacks_balance(address)` - Get STX balance
- `get_wallet_total_balance_usd(user_id, slot_name, data_mgr)` - Total USD value

**Example Usage**:
```python
from services import BalanceService

# Initialize
balance_svc = BalanceService(config=CONFIG)

# Get prices
prices = await balance_svc.get_token_prices()
# Returns: {'SOL': 120.5, 'ETH': 3200.0, ...}

# Get balance
balance = await balance_svc.get_balance('SOL', 'DYw8...')
# Returns: {'balance': 2.5, 'formatted': '2.500000 SOL'}

# Get total USD value
total_usd = await balance_svc.get_wallet_total_balance_usd(
    user_id=12345,
    slot_name='wallet1',
    data_manager=data_mgr
)
```

### 4. TokenService (`services/token_service.py`)
**Responsibility**: Token detection and information from DexScreener

**Key Methods**:
- `is_contract_address(text)` - Check if text is a contract address
- `detect_and_fetch_token(token_address)` - Fetch token data
- `parse_token_data(token_info)` - Parse DexScreener response
- `format_large_number(num)` - Format numbers (K/M/B)
- `get_chain_emoji(chain)` - Get emoji for blockchain

**Example Usage**:
```python
from services import TokenService

# Initialize
token_svc = TokenService(config=CONFIG)

# Check if contract address
is_contract = token_svc.is_contract_address('DYw8jCTf...')

# Fetch token data
token_info = await token_svc.detect_and_fetch_token('DYw8jCTf...')
# Returns: {'chain': 'solana', 'data': {...}}

# Parse data
parsed = token_svc.parse_token_data(token_info)
# Returns: {'chain': 'SOL', 'token_name': '...', 'price_usd': 0.05, ...}
```

### 5. TransferService (`services/transfer_service.py`)
**Responsibility**: Cryptocurrency transfers between wallets

**Key Methods**:
- `execute_solana_transfer(from_pk, to_address, amount)` - SOL transfer
- `execute_ethereum_transfer(from_pk, to_address, amount)` - ETH transfer

**Example Usage**:
```python
from services import TransferService

# Initialize
transfer_svc = TransferService(config=CONFIG)

# Execute Solana transfer
signature = await transfer_svc.execute_solana_transfer(
    from_private_key='a1b2c3...',
    to_address='DYw8...',
    amount_lamports=1_000_000_000  # 1 SOL
)
```

## How to Update Your Main Bot

Here's how to refactor your `tenex_trading_bot.py` to use these services:

### Before (Monolithic):
```python
class TradingBot(TradingMixin):
    def __init__(self):
        self.user_wallets = self.load_user_wallets()
        # ...

    def load_user_wallets(self):
        # ...100 lines of code

    def create_wallet(self, ...):
        # ...100 lines of code

    async def get_balance(self, ...):
        # ...50 lines of code
```

### After (Modular):
```python
from services import (
    DataManager,
    WalletManager,
    BalanceService,
    TokenService,
    TransferService
)

class TradingBot(TradingMixin):
    def __init__(self):
        # Initialize services
        self.data_manager = DataManager(WALLETS_DIR, CONFIG)
        self.wallet_manager = WalletManager(self.data_manager, CONFIG)
        self.balance_service = BalanceService(CONFIG)
        self.token_service = TokenService(CONFIG)
        self.transfer_service = TransferService(CONFIG)

        # State management
        self.waiting_for_input = {}
        self.trading_context = {}
        self.user_orders = {}

    def get_user_wallet_data(self, user_id):
        # Delegate to service
        return self.data_manager.get_user_data(user_id)

    async def create_wallet(self, query, context, network, slot_name):
        # Delegate to service
        wallet_info = self.wallet_manager.create_wallet(
            user_id=query.from_user.id,
            network=network,
            slot_name=slot_name
        )
        # ... handle UI response

    async def get_balance(self, network, address):
        # Delegate to service
        return await self.balance_service.get_balance(network, address)
```

## Migration Strategy

**Phase 1: Service Creation** ✅ COMPLETE
- Created all service modules
- Organized into `services/` package

**Phase 2: Update Main Bot** 🔄 IN PROGRESS
1. Add service imports to `tenex_trading_bot.py`
2. Initialize services in `__init__`
3. Replace direct method calls with service calls
4. Keep UI/menu logic in main bot for now

**Phase 3: Further Modularization** 📋 TODO
- Extract menu/UI generation to `MenuService`
- Extract export functionality to separate module
- Add more comprehensive error handling

## Benefits

### 1. Separation of Concerns
Each service has a single, well-defined responsibility

### 2. Testability
Services can be tested independently:
```python
def test_wallet_creation():
    data_mgr = DataManager(test_dir, test_config)
    wallet_mgr = WalletManager(data_mgr, test_config)

    wallet = wallet_mgr.create_wallet(12345, 'SOL')
    assert wallet is not None
    assert 'address' in wallet
```

### 3. Reusability
Services can be used by other components:
```python
# Use in CLI tool
from services import BalanceService

balance_svc = BalanceService(CONFIG)
balance = await balance_svc.get_balance('SOL', address)
```

### 4. Maintainability
- Easier to find and fix bugs
- Changes are localized to specific services
- Reduced file size (from 3,170 lines to ~300 lines each)

### 5. Scalability
- Easy to add new services
- Can split into microservices later if needed
- Clear interfaces between components

## Quick Start

```python
# In your main bot file:
from pathlib import Path
from services import (
    DataManager,
    WalletManager,
    BalanceService,
    TokenService,
    TransferService
)

# Load config
with open('config.json') as f:
    CONFIG = json.load(f)

# Initialize services
data_mgr = DataManager(Path('wallets'), CONFIG)
wallet_mgr = WalletManager(data_mgr, CONFIG)
balance_svc = BalanceService(CONFIG)
token_svc = TokenService(CONFIG)
transfer_svc = TransferService(CONFIG)

# Use services
user_data = data_mgr.get_user_data(user_id)
wallet = wallet_mgr.create_wallet(user_id, 'SOL')
balance = await balance_svc.get_balance('SOL', wallet['address'])
```

## Next Steps

1. **Update Main Bot**: Refactor `tenex_trading_bot.py` to use services
2. **Test Integration**: Ensure all features work with new architecture
3. **Add Unit Tests**: Create tests for each service
4. **Extract More Logic**: Move menu generation to `MenuService`
5. **Documentation**: Add docstrings and API documentation

## Support

For questions or issues with the modular architecture:
1. Check service docstrings for method documentation
2. Review this README for architecture overview
3. See individual service files for implementation details
