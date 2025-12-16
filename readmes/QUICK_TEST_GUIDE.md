# Quick Testing Guide - Multi-Wallet Feature

## 🚀 Quick Start (5 Minutes)

### 1. Start the Bot
```bash
cd /Users/leumas/leumas/tenex-telegram-bot
source telegram-env/bin/activate
python tenex_trading_bot.py
```

### 2. Basic Functionality Test (2 Minutes)

Open Telegram and send `/start` to your bot:

**Test 1: View Wallets**
- Click "View Wallets"
- Should see wallet1 with 🟢 indicator
- If you had existing wallets, they're now in wallet1

**Test 2: Create in New Slot**
- Click "Manage Wallets" → "Create Wallet in Slot"
- Select "Wallet2"
- Select any chain (SOL or ETH)
- Success! You now have 2 wallet slots

**Test 3: Switch Primary Wallet**
- Click "Manage Wallets" → "Switch Active Wallet"
- Select "Wallet2"
- Click "Back to Menu"
- Main menu now shows only Wallet2 balances 🟢

---

## 🧪 Essential Tests (10 Minutes)

### Test 4: Label Wallets
```
Manage Wallets → Label/Rename Wallet → Wallet1
Send: "Main"

Manage Wallets → Label/Rename Wallet → Wallet2
Send: "Trading"
```
Now view wallets - see labels displayed!

### Test 5: Create Full Wallet Setup
```
Switch to Wallet1 (make it primary)
Create → SOL in Wallet1 ✅
Create → ETH in Wallet1 ✅

Manage Wallets → Create in Slot → Wallet2
Create → SOL in Wallet2 ✅

Manage Wallets → Create in Slot → Wallet3
Create → ETH in Wallet3 ✅
```
You now have:
- Wallet1: SOL + ETH
- Wallet2: SOL
- Wallet3: ETH

---

## 💸 Critical Test: Inter-Wallet Transfer (5 Minutes)

⚠️ **IMPORTANT: This uses REAL blockchain transactions!**

### Prerequisites
- Have at least 0.02 SOL in one wallet (for transfer + fees)
- Use TESTNET if available, or very small amounts

### Test Transfer
```
1. Fund Wallet1 with 0.02 SOL (if not already)

2. Click "Internal Transfer"

3. Select Source: Wallet1

4. Select Chain: SOL (shows your balance)

5. Select Destination: Wallet2

6. Send amount: 0.01

7. Wait for confirmation... ⏳

8. ✅ Success! Should show transaction signature
```

### Verify Transfer
```
1. View Wallets
   - Wallet1 SOL: Decreased by ~0.01 (+ fees)
   - Wallet2 SOL: Increased by 0.01

2. Copy transaction signature

3. Check on Solana Explorer:
   https://explorer.solana.com/
   Paste signature to verify on-chain
```

---

## 🗑️ Delete & Management Tests (3 Minutes)

### Test Deletion Flow
```
1. Switch to Wallet1 (make it primary)

2. Manage Wallets → Delete Wallet → Select Wallet3

3. Review confirmation screen:
   - Shows all balances
   - Shows warning if funds exist
   - Lists what will be deleted

4. Confirm Delete

5. Success! Wallet3 slot now empty

6. Can recreate wallet in Wallet3 slot if needed
```

### Test Protection
```
Try to delete Wallet1 (the primary wallet)
→ Should NOT appear in delete list
→ Or shows "(Switch first)"

This prevents accidentally deleting active wallet!
```

---

## 📤 Export & Withdraw Tests (2 Minutes)

### Test Export (Shows Different Keys)
```
Export Private Key → Wallet1 → SOL
- Copy the private key

Export Private Key → Wallet2 → SOL
- Copy the private key

Compare: They should be DIFFERENT! ✅
Each slot has unique keys.
```

### Test Withdraw Flow
```
Withdraw → Select Wallet1 → Select SOL
Enter recipient address: [your other wallet]
Enter amount: 0.001
Confirm
```

---

## 🎯 Migration Test (Existing Users)

If you had wallets BEFORE this update:

### Test Auto-Migration
```
1. /start command

2. Your old wallets should be in Wallet1 ✅

3. Wallet2 and Wallet3 are empty and ready ✅

4. Check balances - all correct? ✅

5. Open wallets/user_wallets.json
   - Look for "_migrated": true
   - Look for "_old_wallets" backup
   - Verify structure has "wallet_slots"
```

---

## 📊 Quick Verification Commands

### Check Data Structure
```bash
# View user data
cat wallets/user_wallets.json | python -m json.tool

# Should show:
{
  "USER_ID": {
    "primary_wallet": "wallet1",
    "wallet_slots": {
      "wallet1": { ... },
      "wallet2": { ... },
      "wallet3": { ... }
    },
    "_migrated": true
  }
}
```

### Check Environment Variables (Imported Wallets)
```bash
# View .env (be careful - contains secrets!)
grep "_wallet._._SEED" .env

# Should show format:
# 123456789_wallet1_SOL_SEED_PHRASE="word1 word2 ..."
# 123456789_wallet2_ETH_SEED_PHRASE="word1 word2 ..."
```

---

## ⚠️ Common Issues & Fixes

### Issue: "No wallets available"
**Fix:** Create a wallet first using "Create Wallet" button

### Issue: Can't delete wallet
**Check:**
- Is it the primary wallet? (Switch first)
- Is it your only wallet? (Can't delete last one)

### Issue: Transfer failed
**Check:**
- Sufficient balance?
- Network connection OK?
- Not transferring to same wallet?

### Issue: Balance not updating
**Fix:** Click "View Wallets" to refresh

---

## 🎉 Success Indicators

After testing, you should see:

✅ Can create wallets in all 3 slots
✅ Can switch between wallets smoothly
✅ Labels save and display correctly
✅ Can transfer funds between your own wallets
✅ **Transfers complete on blockchain with signatures**
✅ Export shows different keys per slot
✅ Delete works with proper warnings
✅ Migration preserved existing data

---

## 📝 Quick Issue Reporting

Found a bug? Note:
1. **What you did:** (exact steps)
2. **What happened:** (actual result)
3. **What should happen:** (expected result)
4. **Error message:** (if any)
5. **Bot logs:** (check terminal output)

---

## 🚨 Emergency: Rollback

If critical issues occur:

```bash
# Stop the bot
Ctrl+C

# Restore backup (if you made one)
cp wallets/user_wallets.json.backup wallets/user_wallets.json

# Or check migration backup in the file itself
# Look for "_old_wallets" field in user_wallets.json
```

---

## 💡 Testing Tips

1. **Start Small:** Test with tiny amounts (0.001 SOL)
2. **One Feature at a Time:** Don't rush through tests
3. **Verify Each Step:** Check balances after each operation
4. **Use Testnet:** If available for your chains
5. **Keep Notes:** Document any weird behavior
6. **Check Logs:** Terminal shows detailed error info
7. **Test Edge Cases:** Empty wallets, max amounts, etc.

---

## 📞 Need Help?

- Check full `TESTING_CHECKLIST.md` for detailed tests
- Review bot logs in terminal for errors
- Check JSON structure in `wallets/user_wallets.json`
- Verify config in `config.json`

---

## ⏱️ Time Estimates

- **Quick Start:** 5 minutes
- **Essential Tests:** 10 minutes
- **Critical Transfer Test:** 5 minutes
- **Full Checklist:** 1-2 hours

**Recommended:** Do Quick Start + Essential Tests first, then come back for full checklist later.

---

## 🎯 Priority Tests

If short on time, test these FIRST:

1. ✅ Migration works (existing users)
2. ✅ Create wallets in different slots
3. ✅ Switch primary wallet
4. ✅ **Inter-wallet transfer (CRITICAL - real blockchain tx)**
5. ✅ Delete wallet with warnings

These cover the core functionality.

Happy Testing! 🚀
