const ChainBase = require('./ChainBase');

/**
 * Example Chain Implementation Template
 * 
 * To add a new blockchain:
 * 1. Copy this file and rename it (e.g., BitcoinChain.js, EthereumChain.js)
 * 2. Implement all required methods
 * 3. Register the chain in ChainRegistry.js
 * 4. Install any required dependencies
 * 
 * Example registration in ChainRegistry.js:
 *   const BitcoinChain = require('./BitcoinChain');
 *   this.register('bitcoin', new BitcoinChain());
 */
class ExampleChain extends ChainBase {
  /**
   * Get chain metadata
   * Define the blockchain's basic information
   */
  getMetadata() {
    return {
      name: 'Example Blockchain',     // Full name
      symbol: 'EXM',                   // Token symbol
      networks: ['mainnet', 'testnet'], // Supported networks
      coinType: 0,                     // BIP44 coin type (see: https://github.com/satoshilabs/slips/blob/master/slip-0044.md)
      defaultNetwork: 'mainnet'        // Default network
    };
  }

  /**
   * Validate seed phrase
   * Check if the seed phrase is valid for this blockchain
   * 
   * @param {string} seedPhrase - BIP39 seed phrase
   * @returns {boolean} True if valid
   */
  validateSeedPhrase(seedPhrase) {
    // Example using bip39:
    // const bip39 = require('bip39');
    // return bip39.validateMnemonic(seedPhrase);
    
    return seedPhrase && seedPhrase.trim().length > 0;
  }

  /**
   * Generate addresses from seed phrase (no balance checking)
   * This is the fast generation method
   * 
   * @param {string} seedPhrase - BIP39 seed phrase
   * @param {number} count - Number of addresses to generate
   * @param {string} network - Network name (mainnet, testnet, etc)
   * @returns {Promise<Array>} Array of address objects
   */
  async generateAddresses(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} Example addresses for ${network}...\n`);
    
    const addresses = [];
    
    for (let i = 0; i < count; i++) {
      // Derive address from seed phrase
      // Example derivation path: m/44'/COIN_TYPE'/ACCOUNT'/0/ADDRESS_INDEX
      const path = `m/44'/0'/${i}'/0/0`;
      
      // TODO: Implement actual key derivation
      const address = `example_address_${i}`;
      const privateKey = `example_private_key_${i}`;
      
      addresses.push({
        index: i,
        address: address,
        privateKey: privateKey,
        derivationPath: path
      });

      if ((i + 1) % 50 === 0 || i === count - 1) {
        console.log(`Generated ${i + 1}/${count} addresses...`);
      }
    }

    return addresses;
  }

  /**
   * Generate accounts with balance checking
   * This is slower but includes balance information
   * 
   * @param {string} seedPhrase - BIP39 seed phrase
   * @param {number} count - Number of accounts to generate
   * @param {string} network - Network name
   * @returns {Promise<Array>} Array of account objects with balance info
   */
  async generateAccounts(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} Example accounts for ${network}...\n`);
    
    const accounts = [];
    let accountsWithBalance = 0;

    for (let i = 0; i < count; i++) {
      // Generate address
      const path = `m/44'/0'/${i}'/0/0`;
      const address = `example_address_${i}`;
      const privateKey = `example_private_key_${i}`;

      process.stdout.write(`[${i}] Checking ${address}...`);
      
      // Add delay to avoid rate limiting
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Fetch balance
      const balanceInfo = await this.getBalance(address, network);
      
      const accountData = {
        index: i,
        address: address,
        privateKey: privateKey,
        derivationPath: path,
        ...balanceInfo
      };

      accounts.push(accountData);
      
      if (balanceInfo.balance > 0) {
        accountsWithBalance++;
      }

      const balanceDisplay = balanceInfo.balance > 0 
        ? `✓ ${balanceInfo.balance} EXM` 
        : '○ Empty';
      console.log(` ${balanceDisplay}`);
    }

    console.log('\n=== SUMMARY ===');
    console.log(`Total accounts: ${count}`);
    console.log(`Accounts with balance: ${accountsWithBalance}`);
    console.log(`Total balance: ${accounts.reduce((sum, a) => sum + a.balance, 0)} EXM`);

    return accounts;
  }

  /**
   * Get balance for an address
   * 
   * @param {string} address - Blockchain address
   * @param {string} network - Network name
   * @returns {Promise<Object>} Balance information
   */
  async getBalance(address, network = 'mainnet') {
    try {
      // TODO: Implement API call to get balance
      // Example:
      // const apiUrl = network === 'mainnet' ? 'https://api.example.com' : 'https://testnet-api.example.com';
      // const response = await axios.get(`${apiUrl}/balance/${address}`);
      
      return {
        balance: 0,
        hasActivity: false
      };
    } catch (error) {
      return {
        balance: 0,
        hasActivity: false,
        error: error.message
      };
    }
  }

  /**
   * Get transactions for an address
   * 
   * @param {string} address - Blockchain address
   * @param {string} network - Network name
   * @param {number} limit - Number of transactions
   * @param {number} offset - Offset for pagination
   * @returns {Promise<Object>} Transaction data
   */
  async getTransactions(address, network = 'mainnet', limit = 50, offset = 0) {
    try {
      // TODO: Implement API call to get transactions
      // const apiUrl = network === 'mainnet' ? 'https://api.example.com' : 'https://testnet-api.example.com';
      // const response = await axios.get(`${apiUrl}/transactions/${address}?limit=${limit}&offset=${offset}`);
      
      return {
        total: 0,
        limit: limit,
        offset: offset,
        transactions: []
      };
    } catch (error) {
      throw new Error(`Failed to fetch transactions: ${error.message}`);
    }
  }

  /**
   * View transactions interactively (OPTIONAL)
   * Only implement if you want an interactive transaction viewer
   * 
   * @param {string} address - Blockchain address
   * @param {string} network - Network name
   * @param {number} initialLimit - Initial page size
   * @param {Function} promptFunc - Prompt function for user input
   * @returns {Promise<void>}
   */
  async viewTransactions(address, network, initialLimit, promptFunc) {
    // Optional: Implement interactive transaction viewer
    console.log('Interactive transaction viewer not implemented for Example chain');
  }

  /**
   * Transfer tokens (OPTIONAL)
   * Only implement if you want transfer functionality
   * 
   * @param {Array} accounts - Array of account objects
   * @param {string} network - Network name
   * @param {Function} promptFunc - Prompt function for user input
   * @returns {Promise<Array>} Transfer results
   */
  async transferMenu(accounts, network, promptFunc) {
    // Optional: Implement transfer functionality
    console.log('Transfer functionality not implemented for Example chain');
    return [];
  }

  /**
   * Format account data for CSV export
   * 
   * @param {Array} accounts - Array of account objects
   * @returns {string} CSV content
   */
  formatCSV(accounts) {
    let csvContent = 'Index,Address,Derivation Path,Private Key,Balance,Has Activity\n';
    
    accounts.forEach(a => {
      csvContent += `${a.index},"${a.address}","${a.derivationPath}","${a.privateKey}",${a.balance},${a.hasActivity}\n`;
    });

    return csvContent;
  }
}

// Don't export this template - it's just for reference
// module.exports = ExampleChain;