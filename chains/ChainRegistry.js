const StacksChain = require('./StacksChain');
const SolanaChain = require('./SolanaChain');
const EthereumChain = require('./EthereumChain');
const BSCChain = require('./BSCChain');

/**
 * Chain Registry - Central registry for all supported blockchains
 */
class ChainRegistry {
  constructor() {
    this.chains = new Map();
    this.registerDefaultChains();
  }

  /**
   * Register default chains
   */
  registerDefaultChains() {
    this.register('stacks', new StacksChain());
    this.register('solana', new SolanaChain());
    this.register('ethereum', new EthereumChain());
    this.register('bsc', new BSCChain());
  }

  /**
   * Register a new blockchain
   * @param {string} key - Chain identifier (e.g., 'ethereum', 'bitcoin')
   * @param {ChainBase} chainInstance - Instance of chain implementation
   */
  register(key, chainInstance) {
    if (this.chains.has(key)) {
      console.warn(`Warning: Chain '${key}' is already registered. Overwriting...`);
    }
    this.chains.set(key.toLowerCase(), chainInstance);
  }

  /**
   * Get a chain by key
   * @param {string} key - Chain identifier
   * @returns {ChainBase} Chain instance
   */
  get(key) {
    const chain = this.chains.get(key.toLowerCase());
    if (!chain) {
      throw new Error(`Chain '${key}' is not registered. Available chains: ${this.listChains().join(', ')}`);
    }
    return chain;
  }

  /**
   * Check if a chain is registered
   * @param {string} key - Chain identifier
   * @returns {boolean}
   */
  has(key) {
    return this.chains.has(key.toLowerCase());
  }

  /**
   * List all registered chains
   * @returns {Array<string>} Array of chain keys
   */
  listChains() {
    return Array.from(this.chains.keys());
  }

  /**
   * Get all chain metadata
   * @returns {Array<Object>} Array of chain metadata
   */
  getAllMetadata() {
    const metadata = [];
    for (const [key, chain] of this.chains) {
      metadata.push({
        key: key,
        ...chain.getMetadata()
      });
    }
    return metadata;
  }

  /**
   * Auto-detect chain from command
   * @param {string} command - Command string (e.g., 'scan-sol', 'generate-btc')
   * @returns {string|null} Chain key or null if not found
   */
  detectChainFromCommand(command) {
    const parts = command.split('-');
    
    // Check if last part is a registered chain
    if (parts.length > 1) {
      const potentialChain = parts[parts.length - 1];
      if (this.has(potentialChain)) {
        return potentialChain;
      }
    }
    
    // Default to stacks for commands without chain suffix
    if (['scan', 'generate', 'transfer', 'tx'].includes(command)) {
      return 'stacks';
    }
    
    return null;
  }

  /**
   * Get base command from full command
   * @param {string} command - Full command (e.g., 'scan-sol')
   * @returns {string} Base command (e.g., 'scan')
   */
  getBaseCommand(command) {
    const parts = command.split('-');
    
    // If last part is a chain, remove it
    if (parts.length > 1 && this.has(parts[parts.length - 1])) {
      return parts.slice(0, -1).join('-');
    }
    
    return command;
  }
}

// Export singleton instance
module.exports = new ChainRegistry();