const ChainBase = require('./ChainBase');
const bip39 = require('bip39');
const { ethers } = require('ethers');

/**
 * Binance Smart Chain (BSC) Implementation
 *
 * BSC is EVM-compatible, so it works very similar to Ethereum
 * Uses the same derivation path as Ethereum (BIP44 coin type 60)
 */
class BSCChain extends ChainBase {
  getMetadata() {
    return {
      name: 'Binance Smart Chain',
      symbol: 'BNB',
      networks: ['mainnet', 'testnet'],
      coinType: 60, // Same as Ethereum (EVM compatible)
      defaultNetwork: 'mainnet'
    };
  }

  validateSeedPhrase(seedPhrase) {
    return bip39.validateMnemonic(seedPhrase);
  }

  async generateAddresses(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} BSC addresses for ${network}...\n`);

    if (!this.validateSeedPhrase(seedPhrase)) {
      throw new Error('Invalid seed phrase');
    }

    const addresses = [];
    // Create HD node from seed buffer (at root level m/, depth 0)
    const seed = bip39.mnemonicToSeedSync(seedPhrase);
    const hdNode = ethers.HDNodeWallet.fromSeed(seed);

    for (let i = 0; i < count; i++) {
      // BSC uses the same derivation path as Ethereum: m/44'/60'/0'/0/i
      const path = `m/44'/60'/0'/0/${i}`;
      const wallet = hdNode.derivePath(path);

      addresses.push({
        index: i,
        address: wallet.address,
        privateKey: wallet.privateKey,
        derivationPath: path
      });

      if ((i + 1) % 50 === 0 || i === count - 1) {
        console.log(`Generated ${i + 1}/${count} addresses...`);
      }
    }

    return addresses;
  }

  async getBalance(address, network = 'mainnet') {
    try {
      const rpcUrls = {
        mainnet: 'https://bsc-dataseed.binance.org',
        testnet: 'https://data-seed-prebsc-1-s1.binance.org:8545'
      };

      const provider = new ethers.JsonRpcProvider(rpcUrls[network]);
      const balance = await provider.getBalance(address);
      const bnbBalance = parseFloat(ethers.formatEther(balance));

      // Get transaction count to check activity
      const txCount = await provider.getTransactionCount(address);

      return {
        balance: bnbBalance,
        wei: balance.toString(),
        transactionCount: txCount,
        hasActivity: txCount > 0 || bnbBalance > 0
      };
    } catch (error) {
      return {
        balance: 0,
        wei: '0',
        transactionCount: 0,
        hasActivity: false,
        error: error.message
      };
    }
  }

  async generateAccounts(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} BSC accounts for ${network}...\n`);

    if (!this.validateSeedPhrase(seedPhrase)) {
      throw new Error('Invalid seed phrase');
    }

    const accounts = [];
    let accountsWithBalance = 0;
    // Create HD node from seed buffer (at root level m/, depth 0)
    const seed = bip39.mnemonicToSeedSync(seedPhrase);
    const hdNode = ethers.HDNodeWallet.fromSeed(seed);

    for (let i = 0; i < count; i++) {
      const path = `m/44'/60'/0'/0/${i}`;
      const wallet = hdNode.derivePath(path);

      process.stdout.write(`[${i}] Checking ${wallet.address}...`);

      await new Promise(resolve => setTimeout(resolve, 1000));
      const balanceInfo = await this.getBalance(wallet.address, network);

      const accountData = {
        index: i,
        address: wallet.address,
        privateKey: wallet.privateKey,
        derivationPath: path,
        ...balanceInfo
      };

      accounts.push(accountData);

      if (balanceInfo.balance > 0) {
        accountsWithBalance++;
      }

      const balanceDisplay = balanceInfo.balance > 0
        ? `✓ ${balanceInfo.balance} BNB`
        : '○ Empty';
      console.log(` ${balanceDisplay}`);
    }

    console.log('\n=== SUMMARY ===');
    console.log(`Total accounts: ${count}`);
    console.log(`Accounts with balance: ${accountsWithBalance}`);
    console.log(`Total BNB: ${accounts.reduce((sum, a) => sum + a.balance, 0).toFixed(18)} BNB`);

    return accounts;
  }

  async getTransactions(address, network = 'mainnet', limit = 50, offset = 0) {
    // Note: For full transaction history, you'd typically use BscScan API
    // This is a simplified example using RPC

    try {
      const rpcUrls = {
        mainnet: 'https://bsc-dataseed.binance.org',
        testnet: 'https://data-seed-prebsc-1-s1.binance.org:8545'
      };

      const provider = new ethers.JsonRpcProvider(rpcUrls[network]);
      const currentBlock = await provider.getBlockNumber();

      // Note: This is a simplified approach
      // For production, use BscScan API for complete history
      const txCount = await provider.getTransactionCount(address);

      return {
        total: txCount,
        limit: limit,
        offset: offset,
        transactions: [],
        note: 'Use BscScan API for full transaction history'
      };
    } catch (error) {
      throw new Error(`Failed to fetch transactions: ${error.message}`);
    }
  }

  formatCSV(accounts) {
    let csvContent = 'Index,Address,Derivation Path,Private Key,BNB Balance,Transaction Count,Has Activity\n';

    accounts.forEach(a => {
      csvContent += `${a.index},"${a.address}","${a.derivationPath}","${a.privateKey}",${a.balance},${a.transactionCount || 0},${a.hasActivity}\n`;
    });

    return csvContent;
  }
}

module.exports = BSCChain;
