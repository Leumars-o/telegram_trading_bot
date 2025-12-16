# Multi-Wallet Feature Testing Checklist

## Pre-Testing Setup
- [ ] Bot is running: `source telegram-env/bin/activate && python tenex_trading_bot.py`
- [ ] Test with a fresh user account or existing user with wallets
- [ ] Have small test amounts of SOL/ETH for transfer testing

---

## 1. Migration Testing (Existing Users)

### Test with Existing User
- [ ] Login with user who has existing wallets
- [ ] Send `/start` command
- [ ] Verify existing wallets appear under "Wallet1" (primary)
- [ ] Check `wallets/user_wallets.json` - verify migration structure:
  - [ ] Has `wallet_slots` field
  - [ ] Has `primary_wallet: "wallet1"`
  - [ ] Has `_migrated: true`
  - [ ] Has `_old_wallets` backup
- [ ] Verify wallet2 and wallet3 initialized as empty
- [ ] All existing balances display correctly

---

## 2. Wallet Creation in Slots

### Create in Primary Wallet (Default)
- [ ] Click "Create Wallet" from main menu
- [ ] Select a chain (SOL or ETH)
- [ ] Verify wallet created in primary wallet (wallet1)
- [ ] Check success message shows slot name

### Create in Specific Slot
- [ ] Go to "Manage Wallets" → "Create Wallet in Slot"
- [ ] Select wallet2
- [ ] See available chains for that slot
- [ ] Create SOL wallet in wallet2
- [ ] Verify success message
- [ ] Create ETH wallet in wallet2
- [ ] Verify both chains now in wallet2

### Create in Wallet3
- [ ] Repeat above for wallet3
- [ ] Verify all 3 wallet slots can have chains

### Edge Cases
- [ ] Try to create duplicate chain in same slot (should fail)
- [ ] Verify can create same chain in different slots (should work)
- [ ] Example: SOL in wallet1, wallet2, AND wallet3 all valid

---

## 3. View All Wallets

### Display Verification
- [ ] Click "View Wallets" from main menu
- [ ] Verify shows ALL wallet slots (wallet1, wallet2, wallet3)
- [ ] Primary wallet shows 🟢 indicator
- [ ] Other wallets show ⚪ indicator
- [ ] Each wallet shows its label (if set)
- [ ] Each wallet shows all its chains with balances
- [ ] Subtotal per wallet displayed
- [ ] Grand total across all wallets displayed

---

## 4. Wallet Switching

### Switch from Wallet1 to Wallet2
- [ ] Go to "Manage Wallets" → "Switch Active Wallet"
- [ ] See all 3 wallets with chain counts
- [ ] Current primary shows 🟢
- [ ] Select wallet2
- [ ] Verify success message
- [ ] Return to main menu (/start)
- [ ] Verify wallet2 now shows as primary 🟢
- [ ] Verify only wallet2 balances show on main menu

### Switch to Empty Wallet
- [ ] Switch to wallet3 (if empty)
- [ ] Verify can switch even if empty
- [ ] Main menu shows "Get started by creating..."

### Switch Back
- [ ] Switch back to wallet1
- [ ] Verify indicator updates correctly

---

## 5. Wallet Labeling

### Add Label
- [ ] Go to "Manage Wallets" → "Label/Rename Wallet"
- [ ] Select wallet1
- [ ] Send label text: "Main Wallet"
- [ ] Verify success message
- [ ] Check View Wallets - label appears as "Wallet1 - 'Main Wallet'"

### Update Label
- [ ] Go to Label menu again
- [ ] Select wallet1 (should show current label)
- [ ] Send new label: "Trading"
- [ ] Verify label updated

### Label Other Wallets
- [ ] Label wallet2 as "Savings"
- [ ] Label wallet3 as "Test"
- [ ] Verify all labels display in Switch, View, and Manage menus

### Clear Label
- [ ] Go to Label menu
- [ ] Select a wallet
- [ ] Send "clear"
- [ ] Verify label removed

### Test Limits
- [ ] Send label longer than 20 chars
- [ ] Verify truncated to 20 chars

---

## 6. Wallet Deletion

### Try to Delete Primary (Should Fail)
- [ ] Ensure wallet1 is primary
- [ ] Go to "Manage Wallets" → "Delete Wallet"
- [ ] Verify wallet1 NOT in list or shows "(Switch first)"
- [ ] Verify helpful message displayed

### Delete Empty Wallet
- [ ] Switch to wallet1 (make it primary)
- [ ] Go to Delete Wallet menu
- [ ] Select wallet3 (if empty)
- [ ] See confirmation screen with $0.00 balance
- [ ] Click "Confirm Delete"
- [ ] Verify success message
- [ ] Verify wallet3 slot now empty but reusable

### Delete Wallet with Funds (Warning)
- [ ] Fund wallet2 with small amount (0.01 SOL)
- [ ] Make sure wallet2 is NOT primary
- [ ] Go to Delete Wallet
- [ ] Select wallet2
- [ ] **VERIFY WARNING APPEARS:**
  - [ ] Shows all chain balances
  - [ ] Shows total USD value
  - [ ] Shows ⚠️ warning about funds
  - [ ] Lists what will be deleted
- [ ] Click Cancel first (verify returns safely)
- [ ] Try again, click "Confirm Delete"
- [ ] Verify wallet2 deleted

### Try to Delete Only Wallet (Should Fail)
- [ ] Delete all wallets except one
- [ ] Try to delete last wallet
- [ ] Verify error: "Cannot delete your only wallet"

### Recreate After Deletion
- [ ] After deleting wallet2, create new wallet in wallet2 slot
- [ ] Verify slot is fully reusable

---

## 7. Inter-Wallet Transfers (CRITICAL - Real Transactions!)

### Setup
- [ ] Ensure you have 3 wallets with at least one funded
- [ ] Example: wallet1 has 0.1 SOL, wallet2 is empty

### Transfer SOL: Wallet1 → Wallet2
- [ ] Go to "Internal Transfer" from main menu
- [ ] Select source: wallet1
- [ ] Select chain: SOL (should show current balance)
- [ ] Select destination: wallet2
- [ ] See prompt for amount
- [ ] Send amount: "0.01"
- [ ] **WAIT for transaction to process** ⏳
- [ ] **VERIFY SUCCESS:**
  - [ ] Transaction signature/hash shown
  - [ ] Can copy signature for verification
- [ ] **Check balances:**
  - [ ] Wallet1 SOL decreased by 0.01 (plus fees)
  - [ ] Wallet2 SOL increased by 0.01

### Transfer with 'max'
- [ ] Start new transfer
- [ ] Source: wallet2, Chain: SOL, Dest: wallet1
- [ ] Send amount: "max"
- [ ] Verify transfers maximum minus fees
- [ ] Check transaction successful

### Transfer to Wallet Without That Chain (Auto-Create)
- [ ] Create fresh wallet3 with no SOL
- [ ] Transfer SOL from wallet1 → wallet3
- [ ] **VERIFY:** Bot auto-creates SOL address in wallet3
- [ ] Transfer succeeds
- [ ] Check wallet3 now has SOL chain

### Transfer ETH (If Available)
- [ ] Repeat above tests with ETH
- [ ] Verify Ethereum transaction signing works
- [ ] Check transaction on Etherscan

### Edge Cases
- [ ] Try to transfer to same wallet (should fail)
- [ ] Try to transfer 0 amount (should fail)
- [ ] Try to transfer more than balance (should fail)
- [ ] Try to transfer from wallet with 0 balance (no chains shown)
- [ ] Send invalid amount like "abc" (should show error)

### Transaction Verification
- [ ] Copy SOL transaction signature
- [ ] Check on Solana Explorer: https://explorer.solana.com/
- [ ] Verify transaction shows correct amount and addresses
- [ ] Copy ETH transaction hash
- [ ] Check on Etherscan: https://etherscan.io/
- [ ] Verify correct amount and addresses

---

## 8. Export Private Key (Slot-Aware)

### Export from Wallet1
- [ ] Go to "Export Private Key"
- [ ] Select wallet1
- [ ] Select SOL
- [ ] Verify shows:
  - [ ] Wallet name: "Wallet1"
  - [ ] Address (correct)
  - [ ] Private key (correct)
  - [ ] Security warning

### Export from Other Slots
- [ ] Export from wallet2 SOL
- [ ] Export from wallet3 ETH
- [ ] Verify each shows correct wallet slot name

### Verify Different Keys
- [ ] Export SOL from wallet1
- [ ] Export SOL from wallet2
- [ ] Verify private keys are DIFFERENT (each slot has unique keys)

---

## 9. Withdraw (Slot-Aware)

### Withdraw from Wallet1
- [ ] Go to "Withdraw"
- [ ] Select wallet1
- [ ] Select SOL
- [ ] Verify shows "Withdraw SOL from Wallet1"
- [ ] Enter recipient address (use another test wallet)
- [ ] Enter amount
- [ ] See confirmation (note: actual signing placeholder for now)

### Withdraw from Other Slots
- [ ] Repeat for wallet2
- [ ] Repeat for wallet3
- [ ] Verify slot name shown in prompts

---

## 10. Import Wallet into Slot

### Import into Wallet2
- [ ] Go to "Import Wallet"
- [ ] Select SOL
- [ ] Enter valid 12/24 word seed phrase
- [ ] Verify imports into current primary wallet
- [ ] Check .env file has key: `{userId}_wallet2_SOL_SEED_PHRASE`

### Import Same Seed into Different Slot
- [ ] Switch to wallet3
- [ ] Import same seed phrase into wallet3 SOL
- [ ] Verify stored separately: `{userId}_wallet3_SOL_SEED_PHRASE`
- [ ] Verify wallet2 and wallet3 have same SOL address (from same seed)

---

## 11. Main Menu Display

### Primary Wallet Display
- [ ] Set wallet1 as primary
- [ ] Go to main menu (/start)
- [ ] **Verify shows ONLY wallet1:**
  - [ ] Shows "Wallet1 (Active) 🟢"
  - [ ] Shows label if set
  - [ ] Shows all chains in wallet1
  - [ ] Shows "Total Balance (Primary): $X.XX"
  - [ ] Does NOT show wallet2/wallet3 balances

### After Switching
- [ ] Switch to wallet2
- [ ] Return to main menu
- [ ] Verify shows ONLY wallet2 balances

---

## 12. UI/UX Checks

### Button Labels
- [ ] All buttons have clear, descriptive text
- [ ] Active wallet shows 🟢 indicator
- [ ] Non-active shows ⚪ indicator
- [ ] Labels display in quotes where appropriate
- [ ] Chain counts show (e.g., "2/3 chains")

### Error Messages
- [ ] All error messages are clear and helpful
- [ ] Include "Back" button on errors
- [ ] No cryptic error codes

### Navigation
- [ ] Can navigate back at every step
- [ ] "Back to Menu" always returns to main menu
- [ ] No dead-end screens

### Message Formatting
- [ ] Amounts display with correct decimals
- [ ] USD values show with $ prefix
- [ ] Addresses display in monospace/code format
- [ ] Emojis render correctly

---

## 13. Data Persistence

### After Bot Restart
- [ ] Stop the bot (Ctrl+C)
- [ ] Start bot again
- [ ] Send /start
- [ ] **Verify all data persists:**
  - [ ] All 3 wallet slots intact
  - [ ] Primary wallet setting preserved
  - [ ] All labels preserved
  - [ ] All chain data correct
  - [ ] Balances load correctly

### Check JSON Files
- [ ] Open `wallets/user_wallets.json`
- [ ] Verify structure matches expected format
- [ ] Verify all wallet_slots present
- [ ] Verify primary_wallet field correct

---

## 14. Edge Cases & Stress Tests

### Multiple Users
- [ ] Test with 2+ different Telegram accounts
- [ ] Verify each user has independent wallet_slots
- [ ] No cross-contamination of data

### Rapid Operations
- [ ] Create → Switch → Label → Delete quickly
- [ ] Verify no race conditions or errors

### Empty States
- [ ] New user with no wallets
- [ ] All wallets deleted except one
- [ ] Wallet with no chains
- [ ] All slots full (all chains in all slots)

### Boundary Conditions
- [ ] Label with exactly 20 characters
- [ ] Transfer with very small amounts (0.000001)
- [ ] Balance of exactly 0
- [ ] Very large balances

---

## 15. Security Checks

### Private Key Handling
- [ ] Private keys only shown in export function
- [ ] Not logged in console/files
- [ ] Message with private key can be deleted

### Seed Phrase Security
- [ ] User's seed phrase messages deleted immediately
- [ ] Not stored in logs
- [ ] .env file has restricted permissions

### Transaction Signing
- [ ] Only signs with correct private key
- [ ] Cannot transfer from wallet you don't own
- [ ] Amount validation prevents overspending

---

## Bug Tracking

### Issues Found
```
Issue #: [Number]
Description: [What went wrong]
Steps to Reproduce:
1.
2.
3.

Expected: [What should happen]
Actual: [What actually happened]
Severity: [Critical/High/Medium/Low]
```

---

## Success Criteria

✅ All 3 wallet slots functional
✅ Primary wallet switching works smoothly
✅ Labels persist and display correctly
✅ Deletion with proper warnings
✅ **Inter-wallet transfers execute successfully on blockchain**
✅ Export shows correct keys per slot
✅ Withdraw flow works per slot
✅ Migration preserves existing user data
✅ No crashes or unhandled errors
✅ UI is clear and intuitive

---

## Notes

- **IMPORTANT:** Inter-wallet transfers use REAL blockchain transactions
- Test with SMALL amounts first (0.01 SOL, 0.0001 ETH)
- Keep transaction signatures for verification
- Report any issues with transaction signing immediately
- Check gas/fees are reasonable
- Verify balances update correctly after transfers

---

## Test Results Summary

Date: ___________
Tester: ___________
Bot Version: Multi-Wallet v1.0

Total Tests: ___ / ___
Passed: ___
Failed: ___
Blocked: ___

Critical Issues: ___
Notes:
```

```
