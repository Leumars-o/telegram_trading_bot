"""
Telegram Wallet Manager Bot - FIXED VERSION
Executes Node.js wallet manager operations through Python Telegram bot

Installation:
pip install python-telegram-bot python-dotenv

Setup:
1. Create bot with @BotFather on Telegram
2. Get bot token
3. Add TELEGRAM_BOT_TOKEN to .env file
4. Add TELEGRAM_ADMIN_ID to .env (your Telegram user ID)
"""

import os
import subprocess
import asyncio
import json
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.error import TimedOut, BadRequest, NetworkError
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.getenv('TELEGRAM_ADMIN_ID', '0'))
WALLET_MANAGER_PATH = os.getenv('WALLET_MANAGER_PATH', '../stx-multi-wallet/wallet_manager.js')

class WalletBot:
    def __init__(self):
        self.waiting_for_input = {}
        
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == ADMIN_ID
    
    async def run_wallet_command(self, command: list) -> dict:
        """Execute wallet manager command and return result"""
        try:
            logger.info(f"Executing command: {' '.join(command[:2])}...")
            
            result = subprocess.run(
                ['node'] + command,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=os.path.dirname(os.path.abspath(WALLET_MANAGER_PATH))
            )
            
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            logger.error("Command timed out")
            return {
                'success': False,
                'stdout': '',
                'stderr': 'Command timed out after 5 minutes',
                'returncode': -1
            }
        except Exception as e:
            logger.error(f"Command error: {e}")
            return {
                'success': False,
                'stdout': '',
                'stderr': str(e),
                'returncode': -1
            }
    
    def escape_markdown(self, text: str) -> str:
        """Escape markdown special characters"""
        # For MarkdownV2
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    async def safe_edit_message(self, message_or_query, text, reply_markup=None, parse_mode=None):
        """Safely edit message with retry logic - works with Message or CallbackQuery"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Handle both Message and CallbackQuery objects
                if hasattr(message_or_query, 'edit_text'):
                    # It's a Message object
                    if reply_markup:
                        await message_or_query.edit_text(
                            text,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode
                        )
                    else:
                        await message_or_query.edit_text(text, parse_mode=parse_mode)
                else:
                    # It's a CallbackQuery object
                    if reply_markup:
                        await message_or_query.edit_message_text(
                            text,
                            reply_markup=reply_markup,
                            parse_mode=parse_mode
                        )
                    else:
                        await message_or_query.edit_message_text(text, parse_mode=parse_mode)
                return True
            except TimedOut:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                logger.error("Edit message timed out after retries")
                return False
            except BadRequest as e:
                error_msg = str(e).lower()
                # Ignore "message is not modified" errors
                if "not modified" in error_msg or "exactly the same" in error_msg:
                    logger.debug(f"Message already has same content, skipping edit")
                    return True
                logger.error(f"Bad request: {e}")
                # Try without parse_mode
                try:
                    if hasattr(message_or_query, 'edit_text'):
                        if reply_markup:
                            await message_or_query.edit_text(text, reply_markup=reply_markup)
                        else:
                            await message_or_query.edit_text(text)
                    else:
                        if reply_markup:
                            await message_or_query.edit_message_text(text, reply_markup=reply_markup)
                        else:
                            await message_or_query.edit_message_text(text)
                    return True
                except:
                    return False
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                return False
        return False
    
    async def safe_send_message(self, context, chat_id, text, parse_mode=None):
        """Safely send message with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await context.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=parse_mode
                )
            except TimedOut:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                    continue
                logger.error("Send message timed out after retries")
                return None
            except BadRequest:
                # Try without parse_mode
                try:
                    return await context.bot.send_message(chat_id=chat_id, text=text)
                except:
                    return None
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                return None
        return None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command - show main menu"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Unauthorized. This bot is private.")
            return
        
        keyboard = [
            [InlineKeyboardButton("📋 List Chains", callback_data='chains')],
            [InlineKeyboardButton("🔍 Scan Wallet", callback_data='scan')],
            [InlineKeyboardButton("⚡ Generate Addresses", callback_data='generate')],
            [InlineKeyboardButton("📊 View Transactions", callback_data='tx')],
            [InlineKeyboardButton("🔎 Find Address", callback_data='find')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🤖 Wallet Manager Bot\n\nSelect an operation:",
            reply_markup=reply_markup
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks"""
        query = update.callback_query
        
        # Answer callback query to remove loading state
        try:
            await asyncio.wait_for(query.answer(), timeout=5.0)
        except (asyncio.TimeoutError, TimedOut):
            logger.warning("Callback query answer timed out")
        except Exception as e:
            logger.warning(f"Error answering callback: {e}")
        
        if not self.is_admin(query.from_user.id):
            await self.safe_edit_message(query, "❌ Unauthorized")
            return
        
        action = query.data
        
        try:
            if action == 'chains':
                await self.list_chains(query, context)
            elif action == 'scan':
                await self.start_scan(query)
            elif action == 'generate':
                await self.start_generate(query)
            elif action == 'tx':
                await self.start_tx(query, context)
            elif action == 'find':
                await self.start_find(query, context)
            elif action.startswith('scan_'):
                chain = action.split('_')[1]
                await self.execute_scan(query, context, chain)
            elif action.startswith('generate_'):
                chain = action.split('_')[1]
                await self.execute_generate(query, context, chain)
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await self.safe_edit_message(query, f"❌ Error: {str(e)}")
    
    async def list_chains(self, query, context):
        """List all supported blockchains"""
        result = await self.run_wallet_command([WALLET_MANAGER_PATH, 'chains'])
        
        if result['success']:
            # Send as plain text to avoid markdown issues
            output = result['stdout'][:4000]  # Telegram limit
            await self.safe_edit_message(query, f"📋 Supported Blockchains\n\n{output}")
        else:
            await self.safe_edit_message(query, f"❌ Error: {result['stderr']}")
    
    async def start_scan(self, query):
        """Start scan operation - ask for chain"""
        keyboard = [
            [InlineKeyboardButton("Stacks", callback_data='scan_stacks')],
            [InlineKeyboardButton("Solana", callback_data='scan_solana')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.safe_edit_message(
            query,
            "🔍 Scan Wallet\n\nSelect blockchain:",
            reply_markup=reply_markup
        )
    
    async def execute_scan(self, query, context, chain):
        """Execute scan operation"""
        user_id = query.from_user.id
        self.waiting_for_input[user_id] = {
            'action': 'scan',
            'chain': chain,
            'step': 'seed'
        }
        
        await self.safe_edit_message(
            query,
            f"🔍 Scan {chain.capitalize()}\n\n"
            f"Please send the environment variable name for your seed phrase\n"
            f"(e.g., PHANTOM_SEED)\n\n"
            f"⚠️ Message will be deleted for security"
        )
    
    async def start_generate(self, query):
        """Start generate operation - ask for chain"""
        keyboard = [
            [InlineKeyboardButton("Stacks", callback_data='generate_stacks')],
            [InlineKeyboardButton("Solana", callback_data='generate_solana')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await self.safe_edit_message(
            query,
            "⚡ Generate Addresses\n\nSelect blockchain:",
            reply_markup=reply_markup
        )
    
    async def execute_generate(self, query, context, chain):
        """Execute generate operation"""
        user_id = query.from_user.id
        self.waiting_for_input[user_id] = {
            'action': 'generate',
            'chain': chain,
            'step': 'seed'
        }
        
        await self.safe_edit_message(
            query,
            f"⚡ Generate {chain.capitalize()} Addresses\n\n"
            f"Please send the environment variable name for your seed phrase\n"
            f"(e.g., PHANTOM_SEED)\n\n"
            f"⚠️ Message will be deleted for security"
        )
    
    async def start_tx(self, query, context):
        """Start transaction viewer"""
        user_id = query.from_user.id
        self.waiting_for_input[user_id] = {
            'action': 'tx',
            'step': 'address'
        }
        
        await self.safe_edit_message(
            query,
            "📊 View Transactions\n\nPlease send the address to view transactions for:"
        )
    
    async def start_find(self, query, context):
        """Start find address operation"""
        user_id = query.from_user.id
        self.waiting_for_input[user_id] = {
            'action': 'find',
            'step': 'file'
        }
        
        await self.safe_edit_message(
            query,
            "🔎 Find Address\n\nPlease send the wallet JSON filename\n(e.g., wallet.json):"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (user input)"""
        if not self.is_admin(update.effective_user.id):
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.waiting_for_input:
            return
        
        state = self.waiting_for_input[user_id]
        message_text = update.message.text
        
        # Delete user message for security
        try:
            await update.message.delete()
        except:
            pass
        
        try:
            if state['action'] == 'scan':
                await self.handle_scan_input(update, context, state, message_text)
            elif state['action'] == 'generate':
                await self.handle_generate_input(update, context, state, message_text)
            elif state['action'] == 'tx':
                await self.handle_tx_input(update, context, state, message_text)
            elif state['action'] == 'find':
                await self.handle_find_input(update, context, state, message_text)
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                f"❌ Error: {str(e)}"
            )
    
    async def handle_scan_input(self, update, context, state, text):
        """Handle scan operation inputs"""
        user_id = update.effective_user.id
        
        if state['step'] == 'seed':
            state['seed'] = text
            state['step'] = 'count'
            self.waiting_for_input[user_id] = state
            
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                "How many addresses to scan? (e.g., 10, 20, 50)"
            )
        
        elif state['step'] == 'count':
            count = text
            chain = state['chain']
            seed = state['seed']
            
            del self.waiting_for_input[user_id]
            
            msg = await self.safe_send_message(
                context,
                update.effective_chat.id,
                f"⏳ Scanning {count} {chain} addresses...\n\nThis may take a few minutes."
            )
            
            if not msg:
                return
            
            command = [WALLET_MANAGER_PATH, f'scan-{chain}', seed, '-c', count]
            result = await self.run_wallet_command(command)
            
            if result['success']:
                output = result['stdout']
                if len(output) > 4000:
                    output = output[:4000] + "\n\n... (truncated)"
                
                await self.safe_edit_message(msg, f"✅ Scan Complete\n\n{output}")
            else:
                error_msg = result['stderr'][:1000]
                await self.safe_edit_message(msg, f"❌ Error:\n{error_msg}")
    
    async def handle_generate_input(self, update, context, state, text):
        """Handle generate operation inputs"""
        user_id = update.effective_user.id
        
        if state['step'] == 'seed':
            state['seed'] = text
            state['step'] = 'count'
            self.waiting_for_input[user_id] = state
            
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                "How many addresses to generate? (e.g., 100, 500, 1000)"
            )
        
        elif state['step'] == 'count':
            count = text
            chain = state['chain']
            seed = state['seed']
            
            del self.waiting_for_input[user_id]
            
            msg = await self.safe_send_message(
                context,
                update.effective_chat.id,
                f"⏳ Generating {count} {chain} addresses..."
            )
            
            if not msg:
                return
            
            output_file = f"{chain}_{count}_addresses.json"
            command = [WALLET_MANAGER_PATH, f'generate-{chain}', seed, '-c', count, '-o', output_file]
            
            result = await self.run_wallet_command(command)
            
            if result['success']:
                await self.safe_edit_message(
                    msg,
                    f"✅ Generation Complete\n\n"
                    f"Generated {count} addresses\n"
                    f"Saved to: {output_file}\n\n"
                    f"⚠️ File contains private keys!"
                )
            else:
                error_msg = result['stderr'][:1000]
                await self.safe_edit_message(msg, f"❌ Error:\n{error_msg}")
    
    async def handle_tx_input(self, update, context, state, text):
        """Handle transaction viewer inputs"""
        user_id = update.effective_user.id
        address = text
        
        del self.waiting_for_input[user_id]
        
        msg = await self.safe_send_message(
            context,
            update.effective_chat.id,
            f"⏳ Fetching transactions for {address[:8]}..."
        )
        
        if not msg:
            return
        
        command = [WALLET_MANAGER_PATH, 'tx', address, '-l', '10']
        result = await self.run_wallet_command(command)
        
        if result['success']:
            output = result['stdout'][:4000]
            await self.safe_edit_message(msg, f"📊 Transactions\n\n{output}")
        else:
            error_msg = result['stderr'][:1000]
            await self.safe_edit_message(msg, f"❌ Error:\n{error_msg}")
    
    async def handle_find_input(self, update, context, state, text):
        """Handle find address inputs"""
        user_id = update.effective_user.id
        
        if state['step'] == 'file':
            state['file'] = text
            state['step'] = 'address'
            self.waiting_for_input[user_id] = state
            
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                "Now send the address to find:"
            )
        
        elif state['step'] == 'address':
            file = state['file']
            address = text
            
            del self.waiting_for_input[user_id]
            
            command = [WALLET_MANAGER_PATH, 'find', file, '-a', address]
            result = await self.run_wallet_command(command)
            
            output = result['stdout'][:4000] if result['success'] else result['stderr'][:1000]
            status = "✅" if result['success'] else "❌"
            
            await self.safe_send_message(
                context,
                update.effective_chat.id,
                f"{status} Find Result\n\n{output}"
            )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message"""
        if not self.is_admin(update.effective_user.id):
            return
        
        help_text = """🤖 Wallet Manager Bot Help

Available Operations:
• /start - Show main menu
• /chains - List supported blockchains
• /help - Show this help message

Operations:
• Scan - Check wallet balances
• Generate - Create new addresses
• Transactions - View tx history
• Find - Search for address

Security:
⚠️ Your messages are auto-deleted
⚠️ Files contain private keys
⚠️ Only admin can use this bot"""
        
        await update.message.reply_text(help_text)
    
    async def chains_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Quick chains command"""
        if not self.is_admin(update.effective_user.id):
            return
        
        result = await self.run_wallet_command([WALLET_MANAGER_PATH, 'chains'])
        
        if result['success']:
            output = result['stdout'][:4000]
            await update.message.reply_text(f"📋 Supported Blockchains\n\n{output}")
        else:
            await update.message.reply_text(f"❌ Error: {result['stderr']}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Notify user if possible
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again."
            )
        except:
            pass

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env file")
        return
    
    if not ADMIN_ID or ADMIN_ID == 0:
        print("Error: TELEGRAM_ADMIN_ID not found in .env file")
        print("Get your user ID by messaging @userinfobot on Telegram")
        return
    
    bot = WalletBot()
    
    # Create application with increased timeouts
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CommandHandler("help", bot.help_command))
    application.add_handler(CommandHandler("chains", bot.chains_command))
    application.add_handler(CallbackQueryHandler(bot.button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start bot
    logger.info("🤖 Bot started!")
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Wallet Manager Path: {WALLET_MANAGER_PATH}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()