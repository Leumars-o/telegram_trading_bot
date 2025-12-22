# BSC Wallet Manager Guide

Complete guide for managing BSC (Binance Smart Chain) wallets using the Tenex Wallet Manager.

## Prerequisites

1. Install Node.js dependencies:
```bash
npm install
```

2. Add your seed phrase to `.env`:
```bash
BSC_SEED="your twelve or twenty-four word seed phrase here"
```

## Available Commands

### 1. Generate BSC Wallets

Generate BSC wallet addresses from a seed phrase (no balance check):

```bash
# Generate 100 addresses and save to JSON
node wallet_manager.js generate-bsc BSC_SEED -c 100 -o bsc_wallets.json

# Generate 500 addresses for mainnet (default)
node wallet_manager.js generate-bsc BSC_SEED -c 500

# Generate for testnet
node wallet_manager.js generate-bsc BSC_SEED -c 100 -n testnet
```

**Output:**
- JSON file with addresses, private keys, and derivation paths
- Fast generation (no RPC calls)
- Uses BIP44 derivation path: `m/44'/60'/0'/0/i`

### 2. Scan BSC Wallets

Scan BSC wallets and check balances on-chain:

```bash
# Scan 20 addresses and check balances
node wallet_manager.js scan-bsc BSC_SEED -c 20

# Scan 50 addresses and save results to CSV
node wallet_manager.js scan-bsc BSC_SEED -c 50 -o scan_results.csv

# Scan testnet addresses
node wallet_manager.js scan-bsc BSC_SEED -c 20 -n testnet
```

**Output:**
- Real-time balance checking via BSC RPC
- Shows BNB balance for each address
- Transaction count per address
- Identifies addresses with activity
- Optional CSV export with all details

### 3. View Transactions

View transactions for a specific BSC address:

```bash
node wallet_manager.js tx-bsc 0x742d35Cc6634C0532925a3b844Bc454e4438f44e
```

### 4. Find Address in Wallet

Find a specific address in a generated wallet file:

```bash
node wallet_manager.js find bsc_wallets.json -a 0x742d35Cc6634C0532925a3b844Bc454e4438f44e
```

**Output:**
- Index in wallet
- Full address
- Private key
- Derivation path

## Networks

BSC Chain supports two networks:

- **mainnet** (default) - Binance Smart Chain Mainnet
- **testnet** - BSC Testnet

## Derivation Path

BSC uses the same derivation path as Ethereum (EVM compatible):
```
m/44'/60'/0'/0/{index}
```

Where:
- `44'` - BIP44 standard
- `60'` - Ethereum coin type (BSC is EVM compatible)
- `0'` - Account 0
- `0` - External chain
- `{index}` - Address index (0, 1, 2, ...)

## RPC Endpoints

**Mainnet:**
- Default: `https://bsc-dataseed.binance.org`
- Alternative: `https://bsc-dataseed1.defibit.io`

**Testnet:**
- Default: `https://data-seed-prebsc-1-s1.binance.org:8545`

## Examples

### Example 1: Generate 100 BSC Addresses

```bash
# Add to .env
echo 'MY_BSC_WALLET="word1 word2 ... word12"' >> .env

# Generate addresses
node wallet_manager.js generate-bsc MY_BSC_WALLET -c 100 -o my_bsc_addresses.json
```

### Example 2: Scan for Active Wallets

```bash
# Scan first 50 addresses
node wallet_manager.js scan-bsc MY_BSC_WALLET -c 50

# Look for output like:
# [0] Checking 0x742d...f44e... ✓ 1.2345 BNB
# [1] Checking 0x8f3a...e12c... ○ Empty
```

### Example 3: Export Scan Results

```bash
# Scan and export to CSV
node wallet_manager.js scan-bsc MY_BSC_WALLET -c 100 -o bsc_scan.csv

# CSV will contain:
# Index, Address, Derivation Path, Private Key, BNB Balance, Transaction Count, Has Activity
```

### Example 4: Find Lost Wallet

If you have an address but forgot which index it was:

```bash
node wallet_manager.js find my_bsc_addresses.json -a 0x742d35Cc6634C0532925a3b844Bc454e4438f44e
```

## Security Notes

⚠️ **IMPORTANT SECURITY WARNINGS:**

1. **Private Keys**: Generated JSON and CSV files contain private keys. Store them securely!
2. **Never commit**: Add `*.json` and `*.csv` to `.gitignore`
3. **Environment variables**: Never commit your `.env` file
4. **File permissions**: Restrict access to wallet files:
   ```bash
   chmod 600 bsc_wallets.json
   ```

## Integration with Trading Bot

The generated BSC wallets can be imported into the Tenex Trading Bot:

1. Generate wallet addresses
2. Fund the addresses with BNB
3. Import private keys into the bot
4. Start trading BSC tokens!

## Troubleshooting

### Error: "Invalid seed phrase"
- Ensure your seed phrase is 12 or 24 words
- Check for extra spaces or typos
- Verify it's a valid BIP39 mnemonic

### Error: "Failed to connect to BSC RPC"
- Check your internet connection
- Try alternative RPC endpoint in `chains/BSCChain.js`
- Use a custom RPC via environment variable

### Slow scanning
- Reduce the count: `-c 10` instead of `-c 100`
- Use generate instead of scan if you don't need balances
- Consider using a faster RPC endpoint

## Additional Resources

- BSC Documentation: https://docs.bnbchain.org/
- BSC Scan: https://bscscan.com/
- BIP44 Standard: https://github.com/bitcoin/bips/blob/master/bip-0044.mediawiki
- Binance Academy: https://academy.binance.com/

## Support

For issues or questions:
1. Check the examples above
2. Run `node wallet_manager.js help` for full command list
3. Review the code in `chains/BSCChain.js`
