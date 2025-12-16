// Multi-Chain Wallet Manager - Stacks & Solana
// Install dependencies: 
// npm install @stacks/wallet-sdk @stacks/transactions @stacks/network axios
// npm install @solana/web3.js bip39 ed25519-hd-key
// Usage: node wallet_manager.js <command> <env_var_name> [options]

const { generateWallet, generateNewAccount, getStxAddress } = require('@stacks/wallet-sdk');
const { makeSTXTokenTransfer, broadcastTransaction, AnchorMode } = require('@stacks/transactions');
const { STACKS_MAINNET, STACKS_TESTNET } = require('@stacks/network');
const { Keypair, Connection, PublicKey, LAMPORTS_PER_SOL } = require('@solana/web3.js');
const bip39 = require('bip39');
const { derivePath } = require('ed25519-hd-key');
const axios = require('axios');
const fs = require('fs').promises;
const readline = require('readline');
require('dotenv').config();

/**
 * Fetch balance for a Stacks address
 */
async function getBalance(address, network = 'mainnet') {
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
      stx: totalStx,
      stxAvailable: stxBalance,
      stxLocked: stxLocked,
      transactionCount: txCount,
      hasActivity: txCount > 0 || totalStx > 0
    };
  } catch (error) {
    return {
      stx: 0,
      stxAvailable: 0,
      stxLocked: 0,
      transactionCount: 0,
      hasActivity: false,
      error: error.message
    };
  }
}

/**
 * Fetch balance for a Solana address
 */
async function getSolanaBalance(address, network = 'mainnet') {
  try {
    const endpoint = network === 'mainnet' 
      ? 'https://api.mainnet-beta.solana.com'
      : 'https://api.devnet.solana.com';
    
    const connection = new Connection(endpoint, 'confirmed');
    const publicKey = new PublicKey(address);
    
    const balance = await connection.getBalance(publicKey);
    const solBalance = balance / LAMPORTS_PER_SOL;
    
    // Get transaction count
    const signatures = await connection.getSignaturesForAddress(publicKey, { limit: 1 });
    const hasActivity = signatures.length > 0 || solBalance > 0;
    
    return {
      sol: solBalance,
      lamports: balance,
      hasActivity: hasActivity
    };
  } catch (error) {
    return {
      sol: 0,
      lamports: 0,
      hasActivity: false,
      error: error.message
    };
  }
}

/**
 * Generate Solana wallet addresses from seed phrase
 */
async function generateSolanaAddresses(seedPhrase, count, network = 'mainnet') {
  console.log(`\nGenerating ${count} Solana wallet addresses for ${network}...\n`);
  
  // Validate seed phrase
  if (!bip39.validateMnemonic(seedPhrase)) {
    throw new Error('Invalid seed phrase');
  }
  
  // Convert seed phrase to seed
  const seed = await bip39.mnemonicToSeed(seedPhrase);
  
  const addresses = [];
  
  for (let i = 0; i < count; i++) {
    // Solana uses derivation path: m/44'/501'/[account]'/0'
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

/**
 * Generate Solana accounts with balance checking
 */
async function generateSolanaAccounts(seedPhrase, count, network = 'mainnet') {
  console.log(`\nGenerating ${count} Solana accounts for ${network}...\n`);
  
  if (!bip39.validateMnemonic(seedPhrase)) {
    throw new Error('Invalid seed phrase');
  }
  
  const seed = await bip39.mnemonicToSeed(seedPhrase);
  const accounts = [];
  let totalBalance = 0;
  let accountsWithBalance = 0;

  for (let i = 0; i < count; i++) {
    const path = `m/44'/501'/${i}'/0'`;
    const derivedSeed = derivePath(path, seed.toString('hex')).key;
    const keypair = Keypair.fromSeed(derivedSeed);
    const address = keypair.publicKey.toString();

    process.stdout.write(`[${i}] Checking ${address}...`);
    
    await new Promise(resolve => setTimeout(resolve, 5000));
    const balanceInfo = await getSolanaBalance(address, network);
    
    const accountData = {
      index: i,
      address: address,
      privateKey: Buffer.from(keypair.secretKey).toString('hex'),
      derivationPath: path,
      ...balanceInfo
    };

    accounts.push(accountData);
    
    totalBalance += balanceInfo.sol;
    if (balanceInfo.sol > 0) {
      accountsWithBalance++;
    }

    const balanceDisplay = balanceInfo.sol > 0 
      ? `✓ ${balanceInfo.sol} SOL` 
      : '○ Empty';
    console.log(` ${balanceDisplay}`);
  }

  console.log('\n=== SUMMARY ===');
  console.log(`Total accounts: ${count}`);
  console.log(`Accounts with balance: ${accountsWithBalance}`);
  console.log(`Total SOL: ${totalBalance.toFixed(9)} SOL`);

  return accounts;
}

/**
 * Get nonce for an address
 */
async function getAccountNonce(address, network) {
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

/**
 * Generate wallet addresses only (no balance checking)
 */
async function generateWalletAddresses(secretKey, count, network = 'mainnet') {
  console.log(`\nGenerating ${count} Stacks wallet addresses for ${network}...\n`);
  
  let wallet = await generateWallet({
    secretKey: secretKey,
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

/**
 * Save wallet addresses to JSON file
 */
async function saveWalletToJSON(addresses, filename, walletName, network, blockchain = 'stacks') {
  const data = {
    blockchain: blockchain,
    walletName: walletName,
    network: network,
    totalAddresses: addresses.length,
    generatedAt: new Date().toISOString(),
    addresses: addresses
  };

  await fs.writeFile(filename, JSON.stringify(data, null, 2), 'utf8');
  console.log(`\n✓ Wallet data saved to ${filename}`);
  console.log(`⚠️  WARNING: File contains private keys - keep it secure!`);
  return data;
}

/**
 * Load wallet addresses from JSON file
 */
async function loadWalletFromJSON(filename) {
  try {
    const fileContent = await fs.readFile(filename, 'utf8');
    return JSON.parse(fileContent);
  } catch (error) {
    throw new Error(`Failed to load wallet file: ${error.message}`);
  }
}

/**
 * Find address in wallet data
 */
function findAddressInWallet(walletData, targetAddress) {
  const normalizedTarget = targetAddress.toLowerCase().trim();
  const found = walletData.addresses.find(
    addr => addr.address.toLowerCase() === normalizedTarget
  );
  
  if (found) {
    console.log('\n✓ ADDRESS FOUND!');
    console.log(`Blockchain: ${walletData.blockchain || 'stacks'}`);
    console.log(`Wallet: ${walletData.walletName}`);
    console.log(`Network: ${walletData.network}`);
    console.log(`Index: ${found.index}`);
    console.log(`Address: ${found.address}`);
    console.log(`Derivation Path: ${found.derivationPath}`);
    console.log(`Private Key: ${found.privateKey}`);
    return found;
  } else {
    console.log(`\n✗ Address not found in wallet "${walletData.walletName}"`);
    return null;
  }
}

/**
 * Generate wallet accounts with balance checking
 */
async function generateAccounts(secretKey, count, network = 'mainnet') {
  console.log(`\nGenerating ${count} Stacks accounts for ${network}...\n`);
  
  let wallet = await generateWallet({
    secretKey: secretKey,
    password: ''
  });

  const accounts = [];
  let totalBalance = 0;
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
    const balanceInfo = await getBalance(address, network);
    
    const accountData = {
      index: i,
      address: address,
      privateKey: account.stxPrivateKey,
      derivationPath: `m/44'/5757'/0'/0/${i}`,
      ...balanceInfo
    };

    accounts.push(accountData);
    
    totalBalance += balanceInfo.stx;
    if (balanceInfo.stxAvailable > 0) {
      accountsWithBalance++;
    }

    const balanceDisplay = balanceInfo.stxAvailable > 0 
      ? `✓ ${balanceInfo.stxAvailable} STX available` 
      : balanceInfo.stxLocked > 0
        ? `○ ${balanceInfo.stxLocked} STX locked`
        : '○ Empty';
    console.log(` ${balanceDisplay}`);
  }

  console.log('\n=== SUMMARY ===');
  console.log(`Total accounts: ${count}`);
  console.log(`Accounts with available balance: ${accountsWithBalance}`);
  console.log(`Total available STX: ${accounts.reduce((sum, a) => sum + a.stxAvailable, 0).toFixed(6)} STX`);
  console.log(`Total locked STX: ${accounts.reduce((sum, a) => sum + a.stxLocked, 0).toFixed(6)} STX`);

  return accounts;
}

/**
 * Fetch transactions for an address
 */
async function getTransactions(address, network = 'mainnet', limit = 50, offset = 0) {
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

/**
 * Get detailed transaction info
 */
async function getTransactionDetails(txId, network = 'mainnet') {
  try {
    const apiUrl = network === 'mainnet' 
      ? 'https://api.mainnet.hiro.so'
      : 'https://api.testnet.hiro.so';
    
    const response = await axios.get(`${apiUrl}/extended/v1/tx/${txId}`);
    return response.data;
  } catch (error) {
    throw new Error(`Failed to fetch transaction details: ${error.message}`);
  }
}

/**
 * Format transaction type for display
 */
function formatTxType(tx) {
  if (tx.tx_type === 'token_transfer') {
    return 'STX Transfer';
  } else if (tx.tx_type === 'contract_call') {
    return `Contract Call: ${tx.contract_call?.function_name || 'unknown'}`;
  } else if (tx.tx_type === 'smart_contract') {
    return 'Deploy Contract';
  } else if (tx.tx_type === 'coinbase') {
    return 'Coinbase';
  } else if (tx.tx_type === 'poison_microblock') {
    return 'Poison Microblock';
  }
  return tx.tx_type;
}

/**
 * Format transaction status
 */
function formatTxStatus(status) {
  const statusMap = {
    'success': '✓ Success',
    'abort_by_response': '✗ Aborted',
    'abort_by_post_condition': '✗ Post-condition failed',
    'pending': '⧗ Pending'
  };
  return statusMap[status] || status;
}

/**
 * Display transaction list
 */
function displayTransactionList(transactions, address) {
  console.log('\n' + '='.repeat(120));
  console.log(`IDX | TX ID${' '.repeat(59)} | TYPE${' '.repeat(16)} | AMOUNT | STATUS`);
  console.log('='.repeat(120));
  
  transactions.forEach((tx, idx) => {
    const txId = tx.tx_id;
    const shortTxId = txId.substring(0, 8) + '...' + txId.substring(txId.length - 8);
    
    let amount = '';
    let direction = '';
    
    if (tx.tx_type === 'token_transfer') {
      const amountSTX = (parseInt(tx.token_transfer?.amount || 0) / 1000000).toFixed(6);
      const sender = tx.sender_address;
      const recipient = tx.token_transfer?.recipient_address;
      
      if (sender.toLowerCase() === address.toLowerCase()) {
        direction = '→';
        amount = `${direction} ${amountSTX} STX`;
      } else if (recipient.toLowerCase() === address.toLowerCase()) {
        direction = '←';
        amount = `${direction} ${amountSTX} STX`;
      }
    } else if (tx.tx_type === 'contract_call') {
      amount = 'N/A';
    }
    
    const type = formatTxType(tx);
    const status = formatTxStatus(tx.tx_status);
    
    console.log(
      `${String(idx).padStart(3)} | ${shortTxId.padEnd(64)} | ${type.padEnd(20)} | ${amount.padEnd(6)} | ${status}`
    );
  });
  
  console.log('='.repeat(120));
}

/**
 * Parse recipients from send-many contract call
 */
function parseSendManyRecipients(tx) {
  if (tx.tx_type !== 'contract_call' || !tx.contract_call) {
    return null;
  }

  const functionName = tx.contract_call.function_name.toLowerCase();
  if (!functionName.includes('send-many') && !functionName.includes('send')) {
    return null;
  }

  const recipients = [];
  
  const recipientsArg = tx.contract_call.function_args?.find(
    arg => arg.name === 'recipients' || arg.type === 'list'
  );

  if (!recipientsArg) {
    return null;
  }

  const repr = recipientsArg.repr;
  const tupleRegex = /\(tuple[^)]*\(to '([A-Z0-9]+)\)[^)]*\((?:ustx|amount) u(\d+)\)/g;
  
  let match;
  while ((match = tupleRegex.exec(repr)) !== null) {
    recipients.push({
      address: match[1],
      microSTX: parseInt(match[2]),
      stx: parseInt(match[2]) / 1000000
    });
  }

  return recipients.length > 0 ? recipients : null;
}

/**
 * Export recipients to CSV
 */
async function exportRecipientsToCSV(recipients, filename, txId) {
  let csvContent = 'Address,Amount (microSTX),Amount (STX)\n';
  
  recipients.forEach(r => {
    csvContent += `${r.address},${r.microSTX},${r.stx}\n`;
  });

  await fs.writeFile(filename, csvContent, 'utf8');
  console.log(`\n✓ Exported ${recipients.length} recipients to ${filename}`);
  return filename;
}

/**
 * Check if wallet addresses are in recipient list
 */
async function checkWalletsInRecipients(recipients, walletJsonFile) {
  try {
    const walletData = await loadWalletFromJSON(walletJsonFile);
    const walletAddresses = new Set(
      walletData.addresses.map(a => a.address.toLowerCase())
    );

    const matches = recipients.filter(r => 
      walletAddresses.has(r.address.toLowerCase())
    );

    if (matches.length > 0) {
      console.log(`\n✓ Found ${matches.length} of your wallet addresses in recipients!`);
      console.log('\n' + '='.repeat(80));
      matches.forEach(match => {
        const walletInfo = walletData.addresses.find(
          a => a.address.toLowerCase() === match.address.toLowerCase()
        );
        console.log(`Address: ${match.address}`);
        console.log(`  Index: ${walletInfo.index}`);
        console.log(`  Amount: ${match.stx} STX (${match.microSTX} microSTX)`);
        console.log(`  Derivation: ${walletInfo.derivationPath}`);
        console.log('-'.repeat(80));
      });
      
      const totalReceived = matches.reduce((sum, m) => sum + m.stx, 0);
      console.log(`Total received by your wallets: ${totalReceived.toFixed(6)} STX`);
    } else {
      console.log('\n✗ None of your wallet addresses found in recipients');
    }

    return matches;
  } catch (error) {
    console.error(`Error loading wallet file: ${error.message}`);
    return [];
  }
}

/**
 * Display detailed transaction information with enhanced send-many handling
 */
function displayTransactionDetails(tx) {
  console.log('\n' + '='.repeat(80));
  console.log('TRANSACTION DETAILS');
  console.log('='.repeat(80));
  
  console.log(`\nTransaction ID: ${tx.tx_id}`);
  console.log(`Status: ${formatTxStatus(tx.tx_status)}`);
  console.log(`Type: ${formatTxType(tx)}`);
  console.log(`Block Height: ${tx.block_height || 'Pending'}`);
  console.log(`Block Hash: ${tx.block_hash || 'Pending'}`);
  console.log(`Burn Block Time: ${tx.burn_block_time ? new Date(tx.burn_block_time * 1000).toLocaleString() : 'Pending'}`);
  console.log(`Fee: ${(parseInt(tx.fee_rate) / 1000000).toFixed(6)} STX`);
  console.log(`Nonce: ${tx.nonce}`);
  console.log(`Sender: ${tx.sender_address}`);
  console.log(`View on Explorer: https://explorer.hiro.so/txid/${tx.tx_id}`);
  
  if (tx.tx_type === 'token_transfer') {
    console.log(`\n--- TOKEN TRANSFER ---`);
    console.log(`Recipient: ${tx.token_transfer.recipient_address}`);
    console.log(`Amount: ${(parseInt(tx.token_transfer.amount) / 1000000).toFixed(6)} STX`);
    if (tx.token_transfer.memo) {
      console.log(`Memo: ${tx.token_transfer.memo}`);
    }
  } else if (tx.tx_type === 'contract_call') {
    console.log(`\n--- CONTRACT CALL ---`);
    console.log(`Contract: ${tx.contract_call.contract_id}`);
    console.log(`Function: ${tx.contract_call.function_name}`);
    
    const recipients = parseSendManyRecipients(tx);
    
    if (recipients) {
      console.log(`\nRecipients: ${recipients.length} addresses`);
      console.log(`Total Amount: ${recipients.reduce((sum, r) => sum + r.stx, 0).toFixed(6)} STX`);
      
      console.log(`\nFirst 5 recipients:`);
      recipients.slice(0, 5).forEach((r, idx) => {
        console.log(`  ${idx + 1}. ${r.address} - ${r.stx} STX`);
      });
      if (recipients.length > 5) {
        console.log(`  ... and ${recipients.length - 5} more`);
      }
    } else {
      console.log(`Function Args:`);
      tx.contract_call.function_args?.forEach(arg => {
        const repr = arg.repr.length > 200 
          ? arg.repr.substring(0, 200) + '...' 
          : arg.repr;
        console.log(`  - ${arg.name}: ${repr}`);
      });
    }
  } else if (tx.tx_type === 'smart_contract') {
    console.log(`\n--- SMART CONTRACT DEPLOYMENT ---`);
    console.log(`Contract ID: ${tx.smart_contract.contract_id}`);
    console.log(`Source Code Length: ${tx.smart_contract.source_code.length} bytes`);
  }
  
  if (tx.tx_result) {
    console.log(`\nResult: ${tx.tx_result.repr}`);
  }
  
  if (tx.post_conditions && tx.post_conditions.length > 0) {
    console.log(`\n--- POST CONDITIONS ---`);
    tx.post_conditions.forEach((pc, idx) => {
      console.log(`${idx + 1}. Type: ${pc.type}`);
    });
  }
  
  if (tx.events && tx.events.length > 0) {
    console.log(`\n--- EVENTS (${tx.events.length}) ---`);
    tx.events.slice(0, 5).forEach((event, idx) => {
      console.log(`${idx + 1}. ${event.event_type}`);
      if (event.event_type === 'stx_transfer_event') {
        console.log(`   From: ${event.stx_transfer_event.sender}`);
        console.log(`   To: ${event.stx_transfer_event.recipient}`);
        console.log(`   Amount: ${(parseInt(event.stx_transfer_event.amount) / 1000000).toFixed(6)} STX`);
      }
    });
    if (tx.events.length > 5) {
      console.log(`... and ${tx.events.length - 5} more events`);
    }
  }
  
  console.log('\n' + '='.repeat(80));
  
  return parseSendManyRecipients(tx);
}

/**
 * Interactive transaction viewer with enhanced features
 */
async function viewTransactions(address, network = 'mainnet', initialLimit = 10) {
  console.log(`\nFetching transactions for: ${address}`);
  console.log(`Network: ${network}\n`);
  
  let offset = 0;
  let limit = initialLimit;
  let txData = await getTransactions(address, network, limit, offset);
  
  console.log(`Total transactions: ${txData.total}`);
  
  while (true) {
    displayTransactionList(txData.transactions, address);
    
    console.log(`\nShowing ${offset + 1}-${Math.min(offset + limit, txData.total)} of ${txData.total} transactions`);
    console.log('\nOptions:');
    console.log('  [0-9]  - View transaction details by index');
    console.log('  n      - Next page');
    console.log('  p      - Previous page');
    console.log('  l      - Change limit');
    console.log('  q      - Quit');
    
    const choice = await prompt('\nEnter choice: ');
    
    if (choice.toLowerCase() === 'q') {
      console.log('Exiting transaction viewer');
      break;
    } else if (choice.toLowerCase() === 'n') {
      if (offset + limit < txData.total) {
        offset += limit;
        txData = await getTransactions(address, network, limit, offset);
      } else {
        console.log('Already at last page');
        await prompt('Press enter to continue...');
      }
    } else if (choice.toLowerCase() === 'p') {
      if (offset > 0) {
        offset = Math.max(0, offset - limit);
        txData = await getTransactions(address, network, limit, offset);
      } else {
        console.log('Already at first page');
        await prompt('Press enter to continue...');
      }
    } else if (choice.toLowerCase() === 'l') {
      const newLimit = await prompt('Enter new limit (1-50): ');
      const parsedLimit = parseInt(newLimit);
      if (!isNaN(parsedLimit) && parsedLimit > 0 && parsedLimit <= 50) {
        limit = parsedLimit;
        txData = await getTransactions(address, network, limit, offset);
      } else {
        console.log('Invalid limit');
        await prompt('Press enter to continue...');
      }
    } else {
      const idx = parseInt(choice);
      if (!isNaN(idx) && idx >= 0 && idx < txData.transactions.length) {
        const tx = txData.transactions[idx];
        const details = await getTransactionDetails(tx.tx_id, network);
        const recipients = displayTransactionDetails(details);
        
        if (recipients && recipients.length > 0) {
          console.log('\n--- SEND-MANY OPTIONS ---');
          console.log('e - Export recipients to CSV');
          console.log('c - Check if your wallet addresses are in recipients');
          console.log('b - Both (export and check)');
          console.log('Enter - Continue without action');
          
          const action = await prompt('\nEnter choice: ');
          
          if (action.toLowerCase() === 'e' || action.toLowerCase() === 'b') {
            const filename = `recipients_${tx.tx_id.substring(0, 8)}.csv`;
            await exportRecipientsToCSV(recipients, filename, tx.tx_id);
          }
          
          if (action.toLowerCase() === 'c' || action.toLowerCase() === 'b') {
            console.log('\nAvailable wallet JSON files in current directory:');
            try {
              const files = await fs.readdir('.');
              const jsonFiles = files.filter(f => f.endsWith('.json'));
              jsonFiles.forEach((f, idx) => {
                console.log(`  ${idx + 1}. ${f}`);
              });
              
              const fileChoice = await prompt('\nEnter wallet JSON filename (or number): ');
              let walletFile;
              
              const fileIdx = parseInt(fileChoice);
              if (!isNaN(fileIdx) && fileIdx > 0 && fileIdx <= jsonFiles.length) {
                walletFile = jsonFiles[fileIdx - 1];
              } else {
                walletFile = fileChoice;
              }
              
              if (walletFile) {
                await checkWalletsInRecipients(recipients, walletFile);
              }
            } catch (error) {
              console.log('Could not list files. Please enter wallet JSON filename:');
              const walletFile = await prompt('Filename: ');
              if (walletFile) {
                await checkWalletsInRecipients(recipients, walletFile);
              }
            }
          }
        }
        
        await prompt('\nPress enter to continue...');
      } else {
        console.log('Invalid index');
        await prompt('Press enter to continue...');
      }
    }
  }
}

/**
 * Create readline interface for user input
 */
function createInterface() {
  return readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });
}

/**
 * Prompt user for input
 */
function prompt(question) {
  const rl = createInterface();
  return new Promise(resolve => {
    rl.question(question, answer => {
      rl.close();
      resolve(answer);
    });
  });
}

/**
 * Transfer menu
 */
async function transferMenu(accounts, network) {
  const accountsWithBalance = accounts.filter(a => a.stxAvailable > 0);
  
  if (accountsWithBalance.length === 0) {
    console.log('\n❌ No accounts with available balance to transfer');
    return;
  }

  console.log('\n=== TRANSFER OPTIONS ===');
  console.log('1. Transfer from ALL accounts with balance');
  console.log('2. Transfer from specific account(s)');
  console.log('3. Cancel');
  
  const choice = await prompt('\nSelect option (1-3): ');
  
  if (choice === '3') {
    console.log('Transfer cancelled');
    return;
  }

  let selectedAccounts = [];
  
  if (choice === '1') {
    selectedAccounts = accountsWithBalance;
    console.log(`\n✓ Selected ${selectedAccounts.length} accounts with available balance:`);
    selectedAccounts.forEach(a => {
      console.log(`  [${a.index}] ${a.address} - ${a.stxAvailable} STX`);
    });
  } else if (choice === '2') {
    console.log('\nAccounts with available balance:');
    accountsWithBalance.forEach(a => {
      console.log(`  [${a.index}] ${a.address} - ${a.stxAvailable} STX`);
    });
    
    const indices = await prompt('\nEnter account indices (comma-separated, e.g., 0,2,5): ');
    const indexArray = indices.split(',').map(i => parseInt(i.trim())).filter(i => !isNaN(i));
    
    selectedAccounts = accounts.filter(a => indexArray.includes(a.index) && a.stxAvailable > 0);
    
    if (selectedAccounts.length === 0) {
      console.log('❌ No valid accounts selected');
      return;
    }
    
    console.log(`\n✓ Selected ${selectedAccounts.length} account(s):`);
    selectedAccounts.forEach(a => {
      console.log(`  [${a.index}] ${a.address} - ${a.stxAvailable} STX`);
    });
  } else {
    console.log('Invalid option');
    return;
  }

  const recipient = await prompt('\nRecipient address: ');
  if (!recipient || recipient.length < 20) {
    console.log('❌ Invalid recipient address');
    return;
  }

  const amountInput = await prompt('Amount per account (in STX, or "all" for entire balance): ');
  const transferAll = amountInput.toLowerCase() === 'all';
  const amount = transferAll ? null : parseFloat(amountInput);
  
  if (!transferAll && (isNaN(amount) || amount <= 0)) {
    console.log('❌ Invalid amount');
    return;
  }

  const memo = await prompt('Memo (optional, press enter to skip): ');
  
  const feeInput = await prompt('Fee per transaction in microSTX (default: 200): ');
  const fee = feeInput ? parseInt(feeInput) : 200;

  console.log('\n=== TRANSFER SUMMARY ===');
  console.log(`Accounts: ${selectedAccounts.length}`);
  console.log(`Recipient: ${recipient}`);
  console.log(`Amount: ${transferAll ? 'All available balance' : `${amount} STX per account`}`);
  console.log(`Fee: ${fee} microSTX per transaction`);
  console.log(`Memo: ${memo || 'None'}`);
  console.log(`Network: ${network}`);
  
  const totalToSend = transferAll 
    ? selectedAccounts.reduce((sum, a) => sum + a.stxAvailable - (fee / 1000000), 0)
    : amount * selectedAccounts.length;
  console.log(`Total to send: ~${totalToSend.toFixed(6)} STX`);
  console.log(`Total fees: ${(fee * selectedAccounts.length / 1000000).toFixed(6)} STX`);

  const confirm = await prompt('\nProceed with transfer? (yes/no): ');
  
  if (confirm.toLowerCase() !== 'yes') {
    console.log('Transfer cancelled');
    return;
  }

  console.log('\n=== EXECUTING TRANSFERS ===');
  
  const networkObj = network === 'mainnet' ? STACKS_MAINNET : STACKS_TESTNET;
  const results = [];

  for (const account of selectedAccounts) {
    try {
      const nonce = await getAccountNonce(account.address, network);
      
      const transferAmount = transferAll 
        ? Math.floor((account.stxAvailable * 1000000) - fee)
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

/**
 * Save accounts to CSV
 */
async function saveToCSV(accounts, filename, blockchain = 'stacks') {
  let csvContent = '';
  
  if (blockchain === 'solana') {
    csvContent = 'Index,Address,Derivation Path,Private Key,SOL Balance,Has Activity\n';
    accounts.forEach(a => {
      csvContent += `${a.index},"${a.address}","${a.derivationPath}","${a.privateKey}",${a.sol},${a.hasActivity}\n`;
    });
  } else {
    csvContent = 'Index,Address,Derivation Path,Private Key,STX Balance,STX Available,STX Locked,Transaction Count,Has Activity\n';
    accounts.forEach(a => {
      csvContent += `${a.index},"${a.address}","${a.derivationPath}","${a.privateKey}",${a.stx},${a.stxAvailable},${a.stxLocked},${a.transactionCount},${a.hasActivity}\n`;
    });
  }

  await fs.writeFile(filename, csvContent, 'utf8');
  console.log(`\n✓ Results saved to ${filename}`);
  console.log(`⚠️  WARNING: File contains private keys - keep it secure!`);
}

/**
 * Parse command line arguments
 */
function parseArgs() {
  const args = process.argv.slice(2);
  
  if (args.length < 1) {
    console.log('Multi-Chain Wallet Manager - Stacks & Solana');
    console.log('');
    console.log('Usage: node wallet_manager.js <command> [options]');
    console.log('');
    console.log('Commands:');
    console.log('  scan <env_var>           - Scan Stacks wallet addresses and check balances');
    console.log('  scan-sol <env_var>       - Scan Solana wallet addresses and check balances');
    console.log('  transfer <env_var>       - Scan Stacks wallet and open transfer menu');
    console.log('  generate <env_var>       - Generate Stacks wallet addresses and save to JSON');
    console.log('  generate-sol <env_var>   - Generate Solana wallet addresses and save to JSON');
    console.log('  find <json_file>         - Find an address in a wallet JSON file');
    console.log('  tx <address>             - View Stacks transactions for an address');
    console.log('');
    console.log('Options:');
    console.log('  -c, --count <number>     Number of addresses (default: 20, for generate: 500)');
    console.log('  -n, --network <network>  Network: mainnet/testnet (Stacks) or mainnet/devnet (Solana)');
    console.log('  -o, --output <file>      Save results to CSV/JSON file');
    console.log('  -a, --address <address>  Target address to find (for find command)');
    console.log('  -l, --limit <number>     Transaction limit per page (default: 10)');
    console.log('');
    console.log('Examples:');
    console.log('  node wallet_manager.js scan LEATHER_SEED_PHRASE');
    console.log('  node wallet_manager.js scan-sol PHANTOM_SEED_PHRASE -n devnet');
    console.log('  node wallet_manager.js generate WALLET_1 -c 500 -o wallet1.json');
    console.log('  node wallet_manager.js generate-sol WALLET_2 -c 100 -o sol_wallet.json');
    console.log('  node wallet_manager.js find wallet1.json -a SP2X0TZ59D5SZ8ACQ6YMCHHNR2ZN51Z32E2CJ173');
    console.log('  node wallet_manager.js transfer WALLET_1 -c 20');
    console.log('  node wallet_manager.js tx SP1P72Z3704VMT3DMHPP2CB8TGQWGDBHD3RPR9GZS -l 20');
    console.log('');
    console.log('Available seed phrases in .env:');
    Object.keys(process.env)
      .filter(key => key.includes('SEED') || key.includes('WALLET') || key.includes('PHRASE'))
      .forEach(key => console.log(`  - ${key}`));
    process.exit(1);
  }

  const command = args[0];
  
  let envVarName = null;
  let targetAddress = null;
  let jsonFile = null;
  let startIdx = 2;
  
  if (command === 'tx') {
    targetAddress = args[1];
    if (!targetAddress) {
      console.error('Error: tx command requires an address');
      process.exit(1);
    }
  } else if (command === 'find') {
    jsonFile = args[1];
    if (!jsonFile) {
      console.error('Error: find command requires a JSON file path');
      process.exit(1);
    }
  } else {
    envVarName = args[1];
    if (!envVarName) {
      console.error(`Error: ${command} command requires an environment variable name`);
      process.exit(1);
    }
  }
  
  const isGenerate = command.includes('generate');
  let count = isGenerate ? 500 : 20;
  let network = 'mainnet';
  let outputFile = null;
  let txLimit = 10;

  for (let i = startIdx; i < args.length; i++) {
    if (args[i] === '-c' || args[i] === '--count') {
      count = parseInt(args[++i]);
    } else if (args[i] === '-n' || args[i] === '--network') {
      network = args[++i];
    } else if (args[i] === '-o' || args[i] === '--output') {
      outputFile = args[++i];
    } else if (args[i] === '-a' || args[i] === '--address') {
      targetAddress = args[++i];
    } else if (args[i] === '-l' || args[i] === '--limit') {
      txLimit = parseInt(args[++i]);
    }
  }

  if (!['scan', 'scan-sol', 'transfer', 'generate', 'generate-sol', 'find', 'tx'].includes(command)) {
    console.error('Error: Invalid command');
    process.exit(1);
  }

  if (command === 'find' && !targetAddress) {
    console.error('Error: find command requires -a or --address option');
    process.exit(1);
  }

  if (isNaN(count) || count < 1) {
    console.error('Error: Count must be a positive number');
    process.exit(1);
  }

  const isSolana = command.includes('sol');
  if (isSolana && network !== 'mainnet' && network !== 'devnet') {
    console.error('Error: Solana network must be "mainnet" or "devnet"');
    process.exit(1);
  } else if (!isSolana && command !== 'find' && command !== 'tx' && network !== 'mainnet' && network !== 'testnet') {
    console.error('Error: Stacks network must be "mainnet" or "testnet"');
    process.exit(1);
  }

  let seedPhrase = null;
  if (command !== 'tx' && command !== 'find') {
    seedPhrase = process.env[envVarName];
    if (!seedPhrase) {
      console.error(`Error: Environment variable "${envVarName}" not found in .env file`);
      process.exit(1);
    }
  }

  return {
    command,
    seedPhrase,
    count,
    network,
    outputFile,
    envVarName,
    targetAddress,
    txLimit,
    jsonFile
  };
}

/**
 * Main execution
 */
async function main() {
  const { command, seedPhrase, count, network, outputFile, envVarName, targetAddress, txLimit, jsonFile } = parseArgs();
  
  if (command === 'tx') {
    await new Promise(resolve => setTimeout(resolve, 300));
    const balanceInfo = await getBalance(targetAddress, network);

    console.log('=== Stacks Transaction Viewer ===');
    console.log(`Address: ${targetAddress}`);
    console.log(`Network: ${network}`);
    console.log(`Balance: ${balanceInfo.stx} STX`);
    console.log('=================================');
    
    await viewTransactions(targetAddress, network, txLimit);
    return;
  }

  if (command === 'find') {
    console.log('=== Find Address in Wallet ===');
    console.log(`JSON File: ${jsonFile}`);
    console.log(`Target Address: ${targetAddress}`);
    console.log('==============================');
    
    try {
      const walletData = await loadWalletFromJSON(jsonFile);
      findAddressInWallet(walletData, targetAddress);
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
    return;
  }

  if (command === 'generate-sol') {
    console.log('=== Solana Wallet Generator ===');
    console.log(`Wallet: ${envVarName}`);
    console.log(`Count: ${count}`);
    console.log(`Network: ${network}`);
    console.log('===============================');
    
    try {
      const addresses = await generateSolanaAddresses(seedPhrase, count, network);
      
      const filename = outputFile || `${envVarName.toLowerCase()}_solana_${network}_${count}.json`;
      await saveWalletToJSON(addresses, filename, envVarName, network, 'solana');
      
      console.log(`\n✓ Generated ${addresses.length} Solana addresses`);
      console.log(`✓ First address: ${addresses[0].address}`);
      console.log(`✓ Last address: ${addresses[addresses.length - 1].address}`);
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
    return;
  }

  if (command === 'generate') {
    console.log('=== Stacks Wallet Generator ===');
    console.log(`Wallet: ${envVarName}`);
    console.log(`Count: ${count}`);
    console.log(`Network: ${network}`);
    console.log('===============================');
    
    try {
      const addresses = await generateWalletAddresses(seedPhrase, count, network);
      
      const filename = outputFile || `${envVarName.toLowerCase()}_stacks_${network}_${count}.json`;
      await saveWalletToJSON(addresses, filename, envVarName, network, 'stacks');
      
      console.log(`\n✓ Generated ${addresses.length} addresses`);
      console.log(`✓ First address: ${addresses[0].address}`);
      console.log(`✓ Last address: ${addresses[addresses.length - 1].address}`);
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
    return;
  }

  if (command === 'scan-sol') {
    console.log('=== Solana Wallet Scanner ===');
    console.log(`Wallet: ${envVarName}`);
    console.log(`Count: ${count}`);
    console.log(`Network: ${network}`);
    console.log('=============================');

    try {
      const accounts = await generateSolanaAccounts(seedPhrase, count, network);
      
      if (outputFile) {
        await saveToCSV(accounts, outputFile, 'solana');
      }
    } catch (error) {
      console.error('Error:', error.message);
      process.exit(1);
    }
    return;
  }
  
  console.log('=== Stacks Wallet Manager ===');
  console.log(`Command: ${command}`);
  console.log(`Wallet: ${envVarName}`);
  console.log(`Count: ${count}`);
  console.log(`Network: ${network}`);
  console.log('=============================');

  try {
    const accounts = await generateAccounts(seedPhrase, count, network);
    
    if (outputFile) {
      await saveToCSV(accounts, outputFile, 'stacks');
    }
    
    if (command === 'transfer') {
      await transferMenu(accounts, network);
    }
    
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = {
  generateAccounts,
  generateSolanaAccounts,
  generateWalletAddresses,
  generateSolanaAddresses,
  getBalance,
  getSolanaBalance,
  transferMenu,
  viewTransactions,
  getTransactions,
  getTransactionDetails,
  saveWalletToJSON,
  loadWalletFromJSON,
  findAddressInWallet,
  parseSendManyRecipients,
  exportRecipientsToCSV,
  checkWalletsInRecipients
};