const ChainBase = require('./ChainBase');
const { generateWallet, generateNewAccount, getStxAddress } = require('@stacks/wallet-sdk');
const { makeSTXTokenTransfer, broadcastTransaction, AnchorMode } = require('@stacks/transactions');
const { STACKS_MAINNET, STACKS_TESTNET } = require('@stacks/network');
const axios = require('axios');

class StacksChain extends ChainBase {
  getMetadata() {
    return {
      name: 'Stacks',
      symbol: 'STX',
      networks: ['mainnet', 'testnet'],
      coinType: 5757,
      defaultNetwork: 'mainnet'
    };
  }

  validateSeedPhrase(seedPhrase) {
    // Stacks wallet SDK handles validation internally
    return seedPhrase && seedPhrase.trim().length > 0;
  }

  async generateAddresses(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} Stacks wallet addresses for ${network}...\n`);
    
    let wallet = await generateWallet({
      secretKey: seedPhrase,
      password: ''
    });

    const addresses = [];
    const transactionVersion = network === 'mainnet' ? 'mainnet' : 'testnet';

    for (let i = 0; i < count; i++) {
      if (i > 0) {
        wallet = generateNewAccount(wallet);
      }

      const account = wallet.accounts[i];
      const address = getStxAddress({
        account: account,
        transactionVersion: transactionVersion
      });

      addresses.push({
        index: i,
        address: address,
        privateKey: account.stxPrivateKey,
        derivationPath: `m/44'/5757'/0'/0/${i}`
      });

      if ((i + 1) % 50 === 0 || i === count - 1) {
        console.log(`Generated ${i + 1}/${count} addresses...`);
      }
    }

    return addresses;
  }

  async getBalance(address, network = 'mainnet') {
    try {
      const apiUrl = network === 'mainnet' 
        ? 'https://api.mainnet.hiro.so'
        : 'https://api.testnet.hiro.so';
      
      const response = await axios.get(`${apiUrl}/extended/v1/address/${address}/balances`);
      
      const stxBalance = parseInt(response.data.stx.balance) / 1000000;
      const stxLocked = parseInt(response.data.stx.locked) / 1000000;
      const totalStx = stxBalance + stxLocked;
      
      const txResponse = await axios.get(`${apiUrl}/extended/v1/address/${address}/transactions?limit=1`);
      const txCount = txResponse.data.total;
      
      return {
        balance: totalStx,
        available: stxBalance,
        locked: stxLocked,
        transactionCount: txCount,
        hasActivity: txCount > 0 || totalStx > 0
      };
    } catch (error) {
      return {
        balance: 0,
        available: 0,
        locked: 0,
        transactionCount: 0,
        hasActivity: false,
        error: error.message
      };
    }
  }

  async generateAccounts(seedPhrase, count, network = 'mainnet') {
    console.log(`\nGenerating ${count} Stacks accounts for ${network}...\n`);
    
    let wallet = await generateWallet({
      secretKey: seedPhrase,
      password: ''
    });

    const accounts = [];
    let accountsWithBalance = 0;
    const transactionVersion = network === 'mainnet' ? 'mainnet' : 'testnet';

    for (let i = 0; i < count; i++) {
      if (i > 0) {
        wallet = generateNewAccount(wallet);
      }

      const account = wallet.accounts[i];
      const address = getStxAddress({
        account: account,
        transactionVersion: transactionVersion
      });

      process.stdout.write(`[${i}] Checking ${address}...`);
      
      await new Promise(resolve => setTimeout(resolve, 3000));
      const balanceInfo = await this.getBalance(address, network);
      
      const accountData = {
        index: i,
        address: address,
        privateKey: account.stxPrivateKey,
        derivationPath: `m/44'/5757'/0'/0/${i}`,
        ...balanceInfo
      };

      accounts.push(accountData);
      
      if (balanceInfo.available > 0) {
        accountsWithBalance++;
      }

      const balanceDisplay = balanceInfo.available > 0 
        ? `✓ ${balanceInfo.available} STX available` 
        : balanceInfo.locked > 0
          ? `○ ${balanceInfo.locked} STX locked`
          : '○ Empty';
      console.log(` ${balanceDisplay}`);
    }

    console.log('\n=== SUMMARY ===');
    console.log(`Total accounts: ${count}`);
    console.log(`Accounts with available balance: ${accountsWithBalance}`);
    console.log(`Total available STX: ${accounts.reduce((sum, a) => sum + a.available, 0).toFixed(6)} STX`);
    console.log(`Total locked STX: ${accounts.reduce((sum, a) => sum + a.locked, 0).toFixed(6)} STX`);

    return accounts;
  }

  async getTransactions(address, network = 'mainnet', limit = 50, offset = 0) {
    try {
      const apiUrl = network === 'mainnet' 
        ? 'https://api.mainnet.hiro.so'
        : 'https://api.testnet.hiro.so';
      
      const response = await axios.get(
        `${apiUrl}/extended/v1/address/${address}/transactions`,
        { params: { limit, offset } }
      );
      
      return {
        total: response.data.total,
        limit: response.data.limit,
        offset: response.data.offset,
        transactions: response.data.results
      };
    } catch (error) {
      throw new Error(`Failed to fetch transactions: ${error.message}`);
    }
  }

  async getAccountNonce(address, network) {
    try {
      const apiUrl = network === 'mainnet' 
        ? 'https://api.mainnet.hiro.so'
        : 'https://api.testnet.hiro.so';
      
      const response = await axios.get(`${apiUrl}/v2/accounts/${address}?proof=0`);
      return parseInt(response.data.nonce);
    } catch (error) {
      return 0;
    }
  }

  async transferMenu(accounts, network, promptFunc) {
    const accountsWithBalance = accounts.filter(a => a.available > 0);
    
    if (accountsWithBalance.length === 0) {
      console.log('\n❌ No accounts with available balance to transfer');
      return;
    }

    console.log('\n=== TRANSFER OPTIONS ===');
    console.log('1. Transfer from ALL accounts with balance');
    console.log('2. Transfer from specific account(s)');
    console.log('3. Cancel');
    
    const choice = await promptFunc('\nSelect option (1-3): ');
    
    if (choice === '3') {
      console.log('Transfer cancelled');
      return;
    }

    let selectedAccounts = [];
    
    if (choice === '1') {
      selectedAccounts = accountsWithBalance;
      console.log(`\n✓ Selected ${selectedAccounts.length} accounts with available balance:`);
      selectedAccounts.forEach(a => {
        console.log(`  [${a.index}] ${a.address} - ${a.available} STX`);
      });
    } else if (choice === '2') {
      console.log('\nAccounts with available balance:');
      accountsWithBalance.forEach(a => {
        console.log(`  [${a.index}] ${a.address} - ${a.available} STX`);
      });
      
      const indices = await promptFunc('\nEnter account indices (comma-separated, e.g., 0,2,5): ');
      const indexArray = indices.split(',').map(i => parseInt(i.trim())).filter(i => !isNaN(i));
      
      selectedAccounts = accounts.filter(a => indexArray.includes(a.index) && a.available > 0);
      
      if (selectedAccounts.length === 0) {
        console.log('❌ No valid accounts selected');
        return;
      }
      
      console.log(`\n✓ Selected ${selectedAccounts.length} account(s):`);
      selectedAccounts.forEach(a => {
        console.log(`  [${a.index}] ${a.address} - ${a.available} STX`);
      });
    } else {
      console.log('Invalid option');
      return;
    }

    const recipient = await promptFunc('\nRecipient address: ');
    if (!recipient || recipient.length < 20) {
      console.log('❌ Invalid recipient address');
      return;
    }

    const amountInput = await promptFunc('Amount per account (in STX, or "all" for entire balance): ');
    const transferAll = amountInput.toLowerCase() === 'all';
    const amount = transferAll ? null : parseFloat(amountInput);
    
    if (!transferAll && (isNaN(amount) || amount <= 0)) {
      console.log('❌ Invalid amount');
      return;
    }

    const memo = await promptFunc('Memo (optional, press enter to skip): ');
    
    const feeInput = await promptFunc('Fee per transaction in microSTX (default: 200): ');
    const fee = feeInput ? parseInt(feeInput) : 200;

    console.log('\n=== TRANSFER SUMMARY ===');
    console.log(`Accounts: ${selectedAccounts.length}`);
    console.log(`Recipient: ${recipient}`);
    console.log(`Amount: ${transferAll ? 'All available balance' : `${amount} STX per account`}`);
    console.log(`Fee: ${fee} microSTX per transaction`);
    console.log(`Memo: ${memo || 'None'}`);
    console.log(`Network: ${network}`);
    
    const totalToSend = transferAll 
      ? selectedAccounts.reduce((sum, a) => sum + a.available - (fee / 1000000), 0)
      : amount * selectedAccounts.length;
    console.log(`Total to send: ~${totalToSend.toFixed(6)} STX`);
    console.log(`Total fees: ${(fee * selectedAccounts.length / 1000000).toFixed(6)} STX`);

    const confirm = await promptFunc('\nProceed with transfer? (yes/no): ');
    
    if (confirm.toLowerCase() !== 'yes') {
      console.log('Transfer cancelled');
      return;
    }

    console.log('\n=== EXECUTING TRANSFERS ===');
    
    const networkObj = network === 'mainnet' ? STACKS_MAINNET : STACKS_TESTNET;
    const results = [];

    for (const account of selectedAccounts) {
      try {
        const nonce = await this.getAccountNonce(account.address, network);
        
        const transferAmount = transferAll 
          ? Math.floor((account.available * 1000000) - fee)
          : Math.floor(amount * 1000000);
        
        if (transferAmount <= 0) {
          console.log(`[${account.index}] ⚠️  Insufficient balance after fees`);
          results.push({ index: account.index, status: 'skipped', reason: 'Insufficient balance' });
          continue;
        }

        const txOptions = {
          recipient: recipient,
          amount: transferAmount,
          senderKey: account.privateKey,
          network: networkObj,
          anchorMode: AnchorMode.Any,
          fee: fee,
          nonce: nonce,
          memo: memo || undefined
        };

        console.log(`[${account.index}] Sending ${(transferAmount / 1000000).toFixed(6)} STX...`);
        
        const transaction = await makeSTXTokenTransfer(txOptions);
        const broadcastResponse = await broadcastTransaction({ transaction, network: networkObj });
        
        if (broadcastResponse.error) {
          console.log(`[${account.index}] ❌ Failed: ${broadcastResponse.error}`);
          results.push({ index: account.index, status: 'failed', error: broadcastResponse.error });
        } else {
          console.log(`[${account.index}] ✓ Success! TxID: ${broadcastResponse.txid}`);
          results.push({ 
            index: account.index, 
            status: 'success', 
            txid: broadcastResponse.txid,
            amount: transferAmount / 1000000
          });
        }
        
        await new Promise(resolve => setTimeout(resolve, 500));
        
      } catch (error) {
        console.log(`[${account.index}] ❌ Error: ${error.message}`);
        results.push({ index: account.index, status: 'error', error: error.message });
      }
    }

    console.log('\n=== TRANSFER RESULTS ===');
    const successful = results.filter(r => r.status === 'success');
    const failed = results.filter(r => r.status === 'failed' || r.status === 'error');
    const skipped = results.filter(r => r.status === 'skipped');
    
    console.log(`Successful: ${successful.length}`);
    console.log(`Failed: ${failed.length}`);
    console.log(`Skipped: ${skipped.length}`);
    
    if (successful.length > 0) {
      const totalSent = successful.reduce((sum, r) => sum + r.amount, 0);
      console.log(`Total sent: ${totalSent.toFixed(6)} STX`);
    }

    return results;
  }

  formatCSV(accounts) {
    let csvContent = 'Index,Address,Derivation Path,Private Key,STX Balance,STX Available,STX Locked,Transaction Count,Has Activity\n';
    
    accounts.forEach(a => {
      csvContent += `${a.index},"${a.address}","${a.derivationPath}","${a.privateKey}",${a.balance},${a.available},${a.locked},${a.transactionCount},${a.hasActivity}\n`;
    });

    return csvContent;
  }
}

module.exports = StacksChain;