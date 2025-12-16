/**
 * Base Chain Interface
 * All blockchain implementations must extend this class
 */
class ChainBase {
  constructor() {
    if (this.constructor === ChainBase) {
      throw new Error("ChainBase is an abstract class and cannot be instantiated directly");
    }
  }

  /**
   * Get chain metadata
   * @returns {Object} { name, symbol, networks, coinType }
   */
  getMetadata() {
    throw new Error("getMetadata() must be implemented");
  }

  /**
   * Generate addresses from seed phrase (no balance check)
   * @param {string} seedPhrase - BIP39 seed phrase
   * @param {number} count - Number of addresses to generate
   * @param {string} network - Network name (mainnet, testnet, etc)
   * @returns {Promise<Array>} Array of address objects
   */
  async generateAddresses(seedPhrase, count, network) {
    throw new Error("generateAddresses() must be implemented");
  }

  /**
   * Generate accounts with balance checking
   * @param {string} seedPhrase - BIP39 seed phrase
   * @param {number} count - Number of accounts to generate
   * @param {string} network - Network name
   * @returns {Promise<Array>} Array of account objects with balance info
   */
  async generateAccounts(seedPhrase, count, network) {
    throw new Error("generateAccounts() must be implemented");
  }

  /**
   * Get balance for an address
   * @param {string} address - Blockchain address
   * @param {string} network - Network name
   * @returns {Promise<Object>} Balance information
   */
  async getBalance(address, network) {
    throw new Error("getBalance() must be implemented");
  }

  /**
   * Get transactions for an address
   * @param {string} address - Blockchain address
   * @param {string} network - Network name
   * @param {number} limit - Number of transactions
   * @param {number} offset - Offset for pagination
   * @returns {Promise<Object>} Transaction data
   */
  async getTransactions(address, network, limit, offset) {
    throw new Error("getTransactions() must be implemented");
  }

  /**
   * View transactions interactively (optional)
   * @param {string} address - Blockchain address
   * @param {string} network - Network name
   * @param {number} initialLimit - Initial page size
   * @returns {Promise<void>}
   */
  async viewTransactions(address, network, initialLimit) {
    throw new Error("viewTransactions() is not implemented for this chain");
  }

  /**
   * Transfer tokens (optional)
   * @param {Array} accounts - Array of account objects
   * @param {string} network - Network name
   * @returns {Promise<Array>} Transfer results
   */
  async transferMenu(accounts, network) {
    throw new Error("transferMenu() is not implemented for this chain");
  }

  /**
   * Validate seed phrase
   * @param {string} seedPhrase - Seed phrase to validate
   * @returns {boolean} True if valid
   */
  validateSeedPhrase(seedPhrase) {
    throw new Error("validateSeedPhrase() must be implemented");
  }

  /**
   * Format account data for CSV export
   * @param {Array} accounts - Array of account objects
   * @returns {string} CSV content
   */
  formatCSV(accounts) {
    throw new Error("formatCSV() must be implemented");
  }
}

module.exports = ChainBase;