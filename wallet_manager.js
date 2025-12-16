#!/usr/bin/env node
/**
 * Multi-Chain Wallet Manager
 * Modular architecture supporting multiple blockchains
 * 
 * Usage: node wallet_manager.js <command> [options]
 */

const fs = require('fs').promises;
const readline = require('readline');
const chainRegistry = require('./chains/ChainRegistry');
require('dotenv').config();

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
 * Save wallet addresses to JSON file
 */
async function saveWalletToJSON(addresses, filename, walletName, network, blockchain) {
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
 * Save accounts to CSV
 */
async function saveToCSV(accounts, filename, chain) {
  const csvContent = chain.formatCSV(accounts);
  await fs.writeFile(filename, csvContent, 'utf8');
  console.log(`\n✓ Results saved to ${filename}`);
  console.log(`⚠️  WARNING: File contains private keys - keep it secure!`);
}

/**
 * Display help information
 */
function displayHelp() {
  const metadata = chainRegistry.getAllMetadata();
  
  console.log('Multi-Chain Wallet Manager - Modular Architecture');
  console.log('');
  console.log('Usage: node wallet_manager.js <command> [options]');
  console.log('');
  console.log('Commands:');
  console.log('  scan[-chain] <env_var>       - Scan wallet addresses and check balances');
  console.log('  generate[-chain] <env_var>   - Generate wallet addresses and save to JSON');
  console.log('  transfer[-chain] <env_var>   - Scan wallet and open transfer menu');
  console.log('  find <json_file>             - Find an address in a wallet JSON file');
  console.log('  tx[-chain] <address>         - View transactions for an address');
  console.log('  chains                       - List all supported blockchains');
  console.log('');
  console.log('Supported Chains:');
  metadata.forEach(meta => {
    console.log(`  ${meta.key.padEnd(10)} - ${meta.name} (${meta.symbol})`);
    console.log(`             Networks: ${meta.networks.join(', ')}`);
  });
  console.log('');
  console.log('Options:');
  console.log('  -c, --count <number>     Number of addresses (default: 20, for generate: 500)');
  console.log('  -n, --network <network>  Network name (depends on chain)');
  console.log('  -o, --output <file>      Save results to CSV/JSON file');
  console.log('  -a, --address <address>  Target address to find (for find command)');
  console.log('  -l, --limit <number>     Transaction limit per page (default: 10)');
  console.log('');
  console.log('Examples:');
  console.log('  node wallet_manager.js scan WALLET_SEED');
  console.log('  node wallet_manager.js scan-solana PHANTOM_SEED -c 20');
  console.log('  node wallet_manager.js generate-stacks WALLET_1 -c 500 -o wallet1.json');
  console.log('  node wallet_manager.js generate-sol SOL_WALLET -c 100 -n devnet');
  console.log('  node wallet_manager.js find wallet1.json -a SP2X0TZ59D5SZ8ACQ6YMCHHNR2ZN51Z32E2CJ173');
  console.log('  node wallet_manager.js transfer-stacks WALLET_1 -c 20');
  console.log('  node wallet_manager.js tx 7EqQdEULxWcraVx3mXKFqRMTL9MHztaQ');
  console.log('  node wallet_manager.js chains');
  console.log('');
  console.log('Available seed phrases in .env:');
  Object.keys(process.env)
    .filter(key => key.includes('SEED') || key.includes('WALLET') || key.includes('PHRASE'))
    .forEach(key => console.log(`  - ${key}`));
}

/**
 * Parse command line arguments
 */
function parseArgs() {
  const args = process.argv.slice(2);
  
  if (args.length < 1) {
    displayHelp();
    process.exit(1);
  }

  const command = args[0];
  
  // Special commands
  if (command === 'chains') {
    return { command: 'chains' };
  }

  if (command === 'help' || command === '--help' || command === '-h') {
    displayHelp();
    process.exit(0);
  }

  // Detect chain from command
  const chainKey = chainRegistry.detectChainFromCommand(command);
  if (!chainKey) {
    console.error(`Error: Could not determine blockchain for command '${command}'`);
    console.log(`\nSupported chains: ${chainRegistry.listChains().join(', ')}`);
    process.exit(1);
  }

  const baseCommand = chainRegistry.getBaseCommand(command);
  const chain = chainRegistry.get(chainKey);
  const metadata = chain.getMetadata();

  let envVarName = null;
  let targetAddress = null;
  let jsonFile = null;
  let startIdx = 2;
  
  // Parse arguments based on command type
  if (baseCommand === 'tx') {
    targetAddress = args[1];
    if (!targetAddress) {
      console.error('Error: tx command requires an address');
      process.exit(1);
    }
  } else if (baseCommand === 'find') {
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
  
  const isGenerate = baseCommand === 'generate';
  let count = isGenerate ? 500 : 20;
  let network = metadata.defaultNetwork;
  let outputFile = null;
  let txLimit = 10;

  // Parse options
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

  // Validate command
  if (!['scan', 'transfer', 'generate', 'find', 'tx'].includes(baseCommand)) {
    console.error(`Error: Invalid base command '${baseCommand}'`);
    process.exit(1);
  }

  // Validate find command
  if (baseCommand === 'find' && !targetAddress) {
    console.error('Error: find command requires -a or --address option');
    process.exit(1);
  }

  // Validate count
  if (isNaN(count) || count < 1) {
    console.error('Error: Count must be a positive number');
    process.exit(1);
  }

  // Validate network
  if (!metadata.networks.includes(network)) {
    console.error(`Error: Invalid network '${network}' for ${metadata.name}`);
    console.error(`Valid networks: ${metadata.networks.join(', ')}`);
    process.exit(1);
  }

  // Get seed phrase from environment (not needed for tx or find commands)
  let seedPhrase = null;
  if (baseCommand !== 'tx' && baseCommand !== 'find') {
    seedPhrase = process.env[envVarName];
    if (!seedPhrase) {
      console.error(`Error: Environment variable "${envVarName}" not found in .env file`);
      process.exit(1);
    }

    // Validate seed phrase
    if (!chain.validateSeedPhrase(seedPhrase)) {
      console.error(`Error: Invalid seed phrase for ${metadata.name}`);
      process.exit(1);
    }
  }

  return {
    command: baseCommand,
    chainKey,
    chain,
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
  try {
    const args = parseArgs();

    // Handle special commands
    if (args.command === 'chains') {
      console.log('\n=== Supported Blockchains ===\n');
      const metadata = chainRegistry.getAllMetadata();
      metadata.forEach(meta => {
        console.log(`${meta.name} (${meta.symbol})`);
        console.log(`  Key: ${meta.key}`);
        console.log(`  Networks: ${meta.networks.join(', ')}`);
        console.log(`  Coin Type: ${meta.coinType}`);
        console.log('');
      });
      return;
    }

    const { command, chainKey, chain, seedPhrase, count, network, outputFile, envVarName, targetAddress, txLimit, jsonFile } = args;
    const metadata = chain.getMetadata();

    // Handle find command (chain-agnostic)
    if (command === 'find') {
      console.log('=== Find Address in Wallet ===');
      console.log(`JSON File: ${jsonFile}`);
      console.log(`Target Address: ${targetAddress}`);
      console.log('==============================');
      
      const walletData = await loadWalletFromJSON(jsonFile);
      findAddressInWallet(walletData, targetAddress);
      return;
    }

    // Handle tx command
    if (command === 'tx') {
      console.log(`=== ${metadata.name} Transaction Viewer ===`);
      console.log(`Address: ${targetAddress}`);
      console.log(`Network: ${network}`);
      
      const balanceInfo = await chain.getBalance(targetAddress, network);
      console.log(`Balance: ${JSON.stringify(balanceInfo)}`);
      console.log('='.repeat(40));
      
      if (chain.viewTransactions) {
        await chain.viewTransactions(targetAddress, network, txLimit, prompt);
      } else {
        const txData = await chain.getTransactions(targetAddress, network, txLimit, 0);
        console.log(`\nTotal transactions: ${txData.total}`);
        console.log('Transaction viewer not implemented for this chain');
      }
      return;
    }

    // Handle generate command
    if (command === 'generate') {
      console.log(`=== ${metadata.name} Wallet Generator ===`);
      console.log(`Wallet: ${envVarName}`);
      console.log(`Count: ${count}`);
      console.log(`Network: ${network}`);
      console.log('='.repeat(40));
      
      const addresses = await chain.generateAddresses(seedPhrase, count, network);
      
      const filename = outputFile || `${envVarName.toLowerCase()}_${chainKey}_${network}_${count}.json`;
      await saveWalletToJSON(addresses, filename, envVarName, network, chainKey);
      
      console.log(`\n✓ Generated ${addresses.length} addresses`);
      console.log(`✓ First address: ${addresses[0].address}`);
      console.log(`✓ Last address: ${addresses[addresses.length - 1].address}`);
      return;
    }

    // Handle scan command
    if (command === 'scan') {
      console.log(`=== ${metadata.name} Wallet Scanner ===`);
      console.log(`Wallet: ${envVarName}`);
      console.log(`Count: ${count}`);
      console.log(`Network: ${network}`);
      console.log('='.repeat(40));

      const accounts = await chain.generateAccounts(seedPhrase, count, network);
      
      if (outputFile) {
        await saveToCSV(accounts, outputFile, chain);
      }
      return;
    }

    // Handle transfer command
    if (command === 'transfer') {
      console.log(`=== ${metadata.name} Wallet Manager ===`);
      console.log(`Wallet: ${envVarName}`);
      console.log(`Count: ${count}`);
      console.log(`Network: ${network}`);
      console.log('='.repeat(40));

      const accounts = await chain.generateAccounts(seedPhrase, count, network);
      
      if (outputFile) {
        await saveToCSV(accounts, outputFile, chain);
      }
      
      if (chain.transferMenu) {
        await chain.transferMenu(accounts, network, prompt);
      } else {
        console.log('\nTransfer functionality not implemented for this chain');
      }
      return;
    }

  } catch (error) {
    console.error('Error:', error.message);
    if (process.env.DEBUG) {
      console.error(error.stack);
    }
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  main();
}

module.exports = {
  chainRegistry,
  saveWalletToJSON,
  loadWalletFromJSON,
  findAddressInWallet,
  saveToCSV
};