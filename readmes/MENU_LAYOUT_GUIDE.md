# Menu Layout Guide - Updated UI

## 📱 New Menu Layouts

All menus have been updated with improved button placement and styling!

---

## 🏠 Main Menu (Home)

### When User Has Wallets:
```
┌────────────────────────────────────┐
│  🤖 Welcome to Tenex Trading Bot!  │
│                                    │
│  💼 Wallet1 (Active) 🟢            │
│  Balance info here...              │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│        🔄 Refresh Balance          │
├────────────────────────────────────┤
│        👛 View All Wallets         │
├────────────────────────────────────┤
│        🔧 Manage Wallets           │
├────────────────────────────────────┤
│    💸 Transfer Between Wallets     │
├────────────────────────────────────┤
│            📤 Withdraw             │
├────────────────────────────────────┤
│       🔑 Export Private Key        │
└────────────────────────────────────┘
```

**Features:**
- ✅ Transfer Between Wallets - **IN HOME MENU** ✨
- ✅ All main actions accessible
- ✅ Clean, vertical layout

---

### When User Has NO Wallets:
```
┌────────────────────────────────────┐
│  🤖 Welcome to Tenex Trading Bot!  │
│                                    │
│  Get started by creating or        │
│  importing a wallet.               │
└────────────────────────────────────┘

┌─────────────────┬──────────────────┐
│  ➕ Create      │  📥 Import       │
│     Wallet      │     Wallet       │
└─────────────────┴──────────────────┘
```

**Features:**
- ✅ Create and Import **ON SAME LINE** ✨
- ✅ Clean, horizontal layout
- ✅ Easy choice for new users

---

## 🔧 Manage Wallets Menu

```
┌────────────────────────────────────┐
│        🔧 Manage Wallets           │
│                                    │
│  Current Active: Wallet1 🟢        │
│                                    │
│  What would you like to do?        │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│      🔄 Switch Active Wallet       │
├─────────────────┬──────────────────┤
│  ➕ Create      │  📥 Import       │  ✨ SAME LINE!
│     Wallet      │     Wallet       │
├────────────────────────────────────┤
│      🏷️ Label/Rename Wallet       │
├────────────────────────────────────┤
│    💸 Transfer Between Wallets     │  ✨ ADDED!
├────────────────────────────────────┤
│         🗑️ Delete Wallet           │
├────────────────────────────────────┤
│        ⬅️ Back to Menu             │
└────────────────────────────────────┘
```

**Features:**
- ✅ Create and Import **ON SAME LINE** ✨
- ✅ Transfer Between Wallets **ADDED TO MENU** ✨
- ✅ All management options in one place
- ✅ Logical grouping of actions

---

## 🎯 Menu Comparison

### Before vs After

#### Main Menu - NEW USERS
**Before:**
```
➕ Create Wallet       (separate lines)
📥 Import Wallet
```

**After:**
```
➕ Create Wallet  |  📥 Import Wallet   (same line!) ✨
```

---

#### Manage Wallets Menu
**Before:**
```
🔄 Switch Active Wallet
➕ Create Wallet in Slot    (separate lines)
📥 Import Wallet in Slot
🏷️ Label/Rename Wallet
🗑️ Delete Wallet
⬅️ Back to Menu
```

**After:**
```
🔄 Switch Active Wallet
➕ Create Wallet  |  📥 Import Wallet   (same line!) ✨
🏷️ Label/Rename Wallet
💸 Transfer Between Wallets             (added!) ✨
🗑️ Delete Wallet
⬅️ Back to Menu
```

---

## ✨ What Changed

### 1. Main Menu (Home)
✅ **Transfer Between Wallets added** (was missing!)
- Now accessible directly from home
- No need to go into Manage Wallets

### 2. Main Menu (New Users)
✅ **Create | Import on same line**
- Cleaner horizontal layout
- More intuitive choice presentation
- Saves vertical space

### 3. Manage Wallets Menu
✅ **Create | Import on same line**
- Consistent with main menu
- Better visual organization
- Clear action pairing

✅ **Transfer Between Wallets added**
- Complete wallet management in one place
- Easy access for frequent transfers
- Logical placement after labeling

---

## 🎨 Button Styling

### Single-Line Buttons (Full Width)
```python
[InlineKeyboardButton("🔄 Switch Active Wallet", callback_data='switch_wallet_menu')]
```
Rendered as:
```
┌────────────────────────────────────┐
│      🔄 Switch Active Wallet       │
└────────────────────────────────────┘
```

### Two-Button Row (Half Width Each)
```python
[
    InlineKeyboardButton("➕ Create Wallet", callback_data='create_in_slot_menu'),
    InlineKeyboardButton("📥 Import Wallet", callback_data='import_in_slot_menu')
]
```
Rendered as:
```
┌─────────────────┬──────────────────┐
│  ➕ Create      │  📥 Import       │
│     Wallet      │     Wallet       │
└─────────────────┴──────────────────┘
```

---

## 🔄 Navigation Flow

### Complete User Journey

#### New User (No Wallets):
```
/start
├─ ➕ Create Wallet → Select chain → ✅ Created
├─ 📥 Import Wallet → Select chain → Send seed → ✅ Imported
```

#### Existing User (Has Wallets):
```
/start
├─ 🔧 Manage Wallets
│  ├─ 🔄 Switch Active Wallet
│  ├─ ➕ Create Wallet (in slot)
│  ├─ 📥 Import Wallet (in slot)
│  ├─ 🏷️ Label/Rename Wallet
│  ├─ 💸 Transfer Between Wallets  ← NEW! ✨
│  └─ 🗑️ Delete Wallet
│
├─ 💸 Transfer Between Wallets  ← Also in main menu! ✨
├─ 👛 View All Wallets
├─ 📤 Withdraw
└─ 🔑 Export Private Key
```

---

## 📊 Access Matrix

| Feature | Main Menu | Manage Wallets Menu |
|---------|-----------|---------------------|
| Create Wallet | ✅ (new users) | ✅ |
| Import Wallet | ✅ (new users) | ✅ |
| Transfer Between Wallets | ✅ | ✅ |
| Switch Active Wallet | ❌ | ✅ |
| Label/Rename | ❌ | ✅ |
| Delete Wallet | ❌ | ✅ |
| View All Wallets | ✅ | ❌ |
| Withdraw | ✅ | ❌ |
| Export Key | ✅ | ❌ |

**Logic:**
- **Main Menu** = Quick actions + viewing
- **Manage Wallets** = Wallet organization + transfers
- **Transfer** = Available in BOTH (frequently used!)

---

## 💡 Design Rationale

### Why Create | Import on Same Line?
✅ Related actions (both add wallets)
✅ Similar frequency of use
✅ Saves vertical space
✅ Cleaner visual hierarchy
✅ Better mobile UX

### Why Transfer in Both Menus?
✅ **High frequency action** (users transfer often)
✅ **Main menu** = Quick access without navigation
✅ **Manage menu** = Logical grouping with wallet management
✅ **User choice** = Access from wherever convenient

### Why This Button Order?
1. **Switch** - Change which wallet is active (primary action)
2. **Create/Import** - Add new wallets (paired action)
3. **Label** - Organize wallets (secondary action)
4. **Transfer** - Move funds between wallets (common action)
5. **Delete** - Remove wallets (destructive action, at bottom)

---

## 🧪 Testing the New Layout

### Test Main Menu
```
1. Start bot (new user)
2. See Create | Import on SAME LINE ✅
3. Create a wallet
4. Return to /start
5. See "💸 Transfer Between Wallets" button ✅
```

### Test Manage Wallets
```
1. /start
2. Click "🔧 Manage Wallets"
3. See Create | Import on SAME LINE ✅
4. See "💸 Transfer Between Wallets" ✅
5. All options accessible from one menu ✅
```

---

## 📝 Code Changes

### Main Menu Keyboard
```python
# New users - Create and Import on same line
keyboard.append([
    InlineKeyboardButton("➕ Create Wallet", callback_data='create_start'),
    InlineKeyboardButton("📥 Import Wallet", callback_data='import_start')
])

# Existing users - Transfer added
if CONFIG.get('settings', {}).get('inter_wallet_transfers_enabled', True):
    keyboard.append([InlineKeyboardButton("💸 Transfer Between Wallets", callback_data='internal_transfer_start')])
```

### Manage Wallets Keyboard
```python
keyboard = [
    [InlineKeyboardButton("🔄 Switch Active Wallet", callback_data='switch_wallet_menu')],
    [
        InlineKeyboardButton("➕ Create Wallet", callback_data='create_in_slot_menu'),
        InlineKeyboardButton("📥 Import Wallet", callback_data='import_in_slot_menu')
    ],
    [InlineKeyboardButton("🏷️ Label/Rename Wallet", callback_data='label_wallet_menu')],
]

# Transfer added
if CONFIG.get('settings', {}).get('inter_wallet_transfers_enabled', True):
    keyboard.append([InlineKeyboardButton("💸 Transfer Between Wallets", callback_data='internal_transfer_start')])
```

---

## ✅ Summary of Changes

### ✨ New Features:
1. **Transfer in Main Menu** - Quick access from home
2. **Transfer in Manage Wallets** - Complete management hub
3. **Create | Import on same line** - Better layout

### 🎨 UI Improvements:
- Cleaner horizontal layout for paired actions
- More intuitive menu organization
- Consistent button styling
- Better use of screen space

### 🚀 User Experience:
- Fewer clicks to common actions
- Logical grouping of features
- Multiple paths to frequent actions
- Clear visual hierarchy

---

## 🎉 Result

**Before:** Transfer only accessible through main menu
**After:** Transfer in BOTH main and manage menus! ✅

**Before:** Create and Import on separate lines
**After:** Create | Import on same line for cleaner UI! ✅

**Before:** Manage menu lacked transfer option
**After:** Complete wallet management in one place! ✅

---

*Menu layouts updated: December 9, 2024*
*All features: Fully functional ✅*
*Testing: Ready to go! 🚀*
