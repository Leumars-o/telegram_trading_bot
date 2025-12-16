const ChainBase = require('./ChainBase');
const { Keypair, Connection, PublicKey, LAMPORTS_PER_SOL } = require('@solana/web3.js');
const bip39 = require('bip39');
const { derivePath } = require('ed25519-hd-key');

class SolanaChain extends ChainBase {
  getMetadata() {
    return {
      name: 'Solana',
      symbol: 'SOL',
      networks: ['mainnet', 'devnet'],
      coinType: 501,
      defaultNetwork: 'mainnet'
    };
  }

  validateSeedPhrase(seedPhrase) {
    return bip39.validateMnemonic(seedPhrase);
  }

  async generateAddresses(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} Solana wallet addresses for ${network}...\n`);
    
    if (!this.validateSeedPhrase(seedPhrase)) {
      throw new Error('Invalid seed phrase');
    }
    
    const seed = await bip39.mnemonicToSeed(seedPhrase);
    const addresses = [];
    
    for (let i = 0; i < count; i++) {
      const path = `m/44'/501'/${i}'/0'`;
      const derivedSeed = derivePath(path, seed.toString('hex')).key;
      const keypair = Keypair.fromSeed(derivedSeed);
      
      addresses.push({
        index: i,
        address: keypair.publicKey.toString(),
        privateKey: Buffer.from(keypair.secretKey).toString('hex'),
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
      const endpoint = network === 'mainnet' 
        ? 'https://api.mainnet-beta.solana.com'
        : 'https://api.devnet.solana.com';
      
      const connection = new Connection(endpoint, 'confirmed');
      const publicKey = new PublicKey(address);
      
      const balance = await connection.getBalance(publicKey);
      const solBalance = balance / LAMPORTS_PER_SOL;
      
      const signatures = await connection.getSignaturesForAddress(publicKey, { limit: 1 });
      const hasActivity = signatures.length > 0 || solBalance > 0;
      
      return {
        balance: solBalance,
        lamports: balance,
        hasActivity: hasActivity
      };
    } catch (error) {
      return {
        balance: 0,
        lamports: 0,
        hasActivity: false,
        error: error.message
      };
    }
  }

  async generateAccounts(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} Solana accounts for ${network}...\n`);
    
    if (!this.validateSeedPhrase(seedPhrase)) {
      throw new Error('Invalid seed phrase');
    }
    
    const seed = await bip39.mnemonicToSeed(seedPhrase);
    const accounts = [];
    let accountsWithBalance = 0;

    for (let i = 0; i < count; i++) {
      const path = `m/44'/501'/${i}'/0'`;
      const derivedSeed = derivePath(path, seed.toString('hex')).key;
      const keypair = Keypair.fromSeed(derivedSeed);
      const address = keypair.publicKey.toString();

      process.stdout.write(`[${i}] Checking ${address}...`);
      
      await new Promise(resolve => setTimeout(resolve, 5000));
      const balanceInfo = await this.getBalance(address, network);
      
      const accountData = {
        index: i,
        address: address,
        privateKey: Buffer.from(keypair.secretKey).toString('hex'),
        derivationPath: path,
        ...balanceInfo
      };

      accounts.push(accountData);
      
      if (balanceInfo.balance > 0) {
        accountsWithBalance++;
      }

      const balanceDisplay = balanceInfo.balance > 0 
        ? `✓ ${balanceInfo.balance} SOL` 
        : '○ Empty';
      console.log(` ${balanceDisplay}`);
    }

    console.log('\n=== SUMMARY ===');
    console.log(`Total accounts: ${count}`);
    console.log(`Accounts with balance: ${accountsWithBalance}`);
    console.log(`Total SOL: ${accounts.reduce((sum, a) => sum + a.balance, 0).toFixed(9)} SOL`);

    return accounts;
  }

  async getTransactions(address, network = 'mainnet', limit = 50, offset = 0) {
    try {
      const endpoint = network === 'mainnet' 
        ? 'https://api.mainnet-beta.solana.com'
        : 'https://api.devnet.solana.com';
      
      const connection = new Connection(endpoint, 'confirmed');
      const publicKey = new PublicKey(address);
      
      // Get signatures with pagination
      const signatures = await connection.getSignaturesForAddress(publicKey, { 
        limit: limit 
      });
      
      return {
        total: signatures.length,
        limit: limit,
        offset: offset,
        transactions: signatures
      };
    } catch (error) {
      throw new Error(`Failed to fetch transactions: ${error.message}`);
    }
  }

  formatCSV(accounts) {
    let csvContent = 'Index,Address,Derivation Path,Private Key,SOL Balance,Has Activity\n';
    
    accounts.forEach(a => {
      csvContent += `${a.index},"${a.address}","${a.derivationPath}","${a.privateKey}",${a.balance},${a.hasActivity}\n`;
    });

    return csvContent;
  }
}

module.exports = SolanaChain;