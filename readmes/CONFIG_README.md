# Configuration Guide

## config.json

The `config.json` file allows you to control which blockchain networks are available in your Telegram trading bot.

### File Structure

```json
{
  "chains": {
    "CHAIN_KEY": {
      "enabled": true/false,
      "name": "Chain Name",
      "symbol": "TOKEN",
      "rpc": "https://rpc-url.com",
      "decimals": 18,
      "emoji": "🔹",
      "wallet_file": "wallets/chain_wallets.json",
      "coingecko_id": "coingecko-id",
      "dexscreener_chain": "chain-name",
      "import_supported": true/false
    }
  },
  "settings": {
    "max_wallets_per_user": 3,
    "price_update_interval": 60,
    "balance_cache_timeout": 30
  }
}
```

### Chain Configuration

#### Required Fields

- **enabled** (boolean): Controls if the chain is visible to users
  - `true`: Chain appears in menus and balances
  - `false`: Chain is hidden from users (existing wallets still accessible but not displayed)

- **name** (string): Full name of the blockchain (e.g., "Solana", "Ethereum")

- **symbol** (string): Token symbol (e.g., "SOL", "ETH", "STX")

- **rpc** (string): RPC endpoint URL for the blockchain

- **decimals** (integer): Number of decimal places for the token

- **wallet_file** (string): Path to the wallet CSV file

#### Optional Fields

- **emoji** (string): Emoji displayed next to the chain name (default: "🔹")

- **coingecko_id** (string): CoinGecko API ID for price fetching

- **dexscreener_chain** (string): DexScreener chain identifier (null if not supported)

- **import_supported** (boolean): Whether seed phrase import is supported (default: true)

### Settings Configuration

- **max_wallets_per_user**: Maximum number of wallets a user can create (default: 3)

- **price_update_interval**: Price update frequency in seconds (future use)

- **balance_cache_timeout**: Balance cache timeout in seconds (future use)

## Usage Examples

### Example 1: Enable only Solana and Ethereum

```json
{
  "chains": {
    "SOL": {
      "enabled": true,
      ...
    },
    "ETH": {
      "enabled": true,
      ...
    },
    "STACKS": {
      "enabled": false,
      ...
    }
  }
}
```

Users will only see Solana and Ethereum options. Stacks will be hidden.

### Example 2: Enable all chains

```json
{
  "chains": {
    "SOL": {
      "enabled": true,
      ...
    },
    "ETH": {
      "enabled": true,
      ...
    },
    "STACKS": {
      "enabled": true,
      ...
    }
  }
}
```

### Example 3: Disable Stacks import

```json
{
  "chains": {
    "STACKS": {
      "enabled": true,
      "import_supported": false,
      ...
    }
  }
}
```

Stacks will be available for wallet creation but not for import.

## Adding New Chains

To add a new chain:

1. Add a new entry in the `chains` object
2. Set all required fields
3. Create a corresponding wallet CSV file in the `wallets/` directory
4. Update the bot code to handle the new chain's balance fetching logic

## Notes

- Changes to `config.json` require restarting the bot
- Existing user wallets for disabled chains are not deleted, just hidden from display
- The bot will fall back to default configuration if `config.json` is missing or corrupted
