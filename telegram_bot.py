"""
Telegram Bot for TTS - Render.com Optimized
"""

import os
import logging
import asyncio
from typing import Dict, Any
import aiohttp
import io

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CallbackQueryHandler
)
from telegram.constants import ParseMode

from app.database import Database
from app.minimax_api import MinimaxAPI

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram Bot Handler"""
    
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN")
        self.application = None
        self.db = Database()
        self.minimax = MinimaxAPI()
        
        if not self.bot_token:
            logger.error("❌ BOT_TOKEN environment variable not set!")
            raise ValueError("BOT_TOKEN is required")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        welcome_text = f"""
🎤 *Welcome to TTS Bot*, {user.first_name}!

I can convert text to high-quality speech with multiple voices.

*Commands:*
/start - Show this message
/help - Help guide
/tts [text] - Convert text to speech
/mycode [code] - Set access code
/myquota - Check quota
/voices - Browse voices
/settings - Configure settings

*Example:* `/tts Hello world`

*Admin Panel:* {os.getenv("RENDER_EXTERNAL_URL", "https://your-app.onrender.com")}/admin
        """
        
        # Add user to database
        await self.db.add_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        keyboard = [
            [InlineKeyboardButton("🎵 Browse Voices", callback_data="browse_voices")],
            [InlineKeyboardButton("🔑 Set Access Code", callback_data="set_code")],
            [InlineKeyboardButton("📊 Check Quota", callback_data="check_quota")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
*🤖 TTS Bot Help*

*Basic Commands:*
• `/tts [text]` - Convert text to speech
  Example: `/tts Hello world!`
• `/tts_long` - For longer texts

*Access Management:*
• `/mycode [code]` - Set access code
  Example: `/mycode TTS-ABC123XYZ`
• `/myquota` - Check remaining quota
• `/reset_code` - Reset current code

*Voice Management:*
• `/voices` - Browse available voices
• `/setvoice [id]` - Set default voice
• `/voiceinfo [id]` - Voice details

*Settings:*
• `/settings` - Configure parameters
• `/setspeed [0.5-2.0]` - Set speed
• `/setpitch [-5-5]` - Set pitch
• `/setemotion [auto/happy/sad/angry/calm]` - Set emotion

*Usage:*
• Max text: 5000 characters
• Format: OGG/Opus 48kHz Mono
• Languages: English, Bengali, etc.

*Support:* Contact admin for help.
        """
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def tts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /tts command"""
        user_id = update.effective_user.id
        text = ' '.join(context.args) if context.args else None
        
        if not text:
            await update.message.reply_text(
                "❌ Please provide text:\n`/tts Your text here`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check text length
        if len(text) > 5000:
            await update.message.reply_text("❌ Text too long. Max 5000 characters.")
            return
        
        # Check user quota
        user_quota = await self.db.get_user_quota(user_id)
        
        if not user_quota or user_quota.get('remaining', 0) < len(text):
            await update.message.reply_text(
                f"❌ Insufficient quota!\n"
                f"Required: {len(text):,}\n"
                f"Available: {user_quota.get('remaining', 0) if user_quota else 0:,}\n\n"
                f"Set access code: /mycode"
            )
            return
        
        # Processing message
        processing_msg = await update.message.reply_text("🔄 Generating audio...")
        
        try:
            # Get user settings
            settings = await self.db.get_user_settings(user_id)
            
            # Generate TTS
            result = await self.minimax.generate_tts(
                text=text,
                voice_id=settings.get('voice_id', 'moss_audio_4d4208c8-b67d-11f0-afaf-868268514f62'),
                speed=settings.get('speed', 0.9),
                pitch=settings.get('pitch', 0),
                volume=settings.get('volume', 1.6),
                emotion=settings.get('emotion', 'auto')
            )
            
            if not result['success']:
                await processing_msg.edit_text(f"❌ Error: {result.get('error')}")
                return
            
            # Update quota
            await self.db.use_quota(user_id, len(text))
            
            # Save to history
            await self.db.add_history(
                user_id=user_id,
                text=text[:200],  # Store only first 200 chars
                char_count=len(text),
                voice_id=settings.get('voice_id')
            )
            
            # Send audio
            audio_file = io.BytesIO(result['audio_data'])
            audio_file.name = f"tts_{user_id}.ogg"
            
            caption = (
                f"✅ *Audio Generated!*\n"
                f"Characters: {len(text):,}\n"
                f"Remaining: {user_quota['remaining'] - len(text):,}"
            )
            
            await context.bot.send_voice(
                chat_id=update.effective_chat.id,
                voice=audio_file,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN
            )
            
            await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            await processing_msg.edit_text("❌ Failed to generate audio. Please try again.")
    
    async def set_access_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /mycode command"""
        user_id = update.effective_user.id
        code = context.args[0] if context.args else None
        
        if not code:
            await update.message.reply_text(
                "❌ Please provide access code:\n`/mycode TTS-ABC123XYZ`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Validate code format
        if not code.startswith('TTS-') or len(code) < 10:
            await update.message.reply_text(
                "❌ Invalid code format. Must start with 'TTS-'"
            )
            return
        
        # Activate code
        result = await self.db.activate_access_code(user_id, code)
        
        if result['success']:
            await update.message.reply_text(
                f"✅ *Access Code Activated!*\n\n"
                f"Code: `{code}`\n"
                f"Quota: {result['quota']:,} characters\n"
                f"Expiry: {result.get('expiry', 'Never')}\n\n"
                f"You can now use /tts command!",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(f"❌ {result['message']}")
    
    async def check_quota(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myquota command"""
        user_id = update.effective_user.id
        
        quota = await self.db.get_user_quota(user_id)
        
        if not quota:
            await update.message.reply_text(
                "❌ No access code set.\n"
                "Use `/mycode TTS-YOUR-CODE`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        quota_text = f"""
📊 *Your Quota*

*Access Code:* `{quota['code']}`
*Total:* {quota['total']:,} characters
*Used:* {quota['used']:,} characters
*Remaining:* {quota['remaining']:,} characters
*Usage:* {(quota['used']/quota['total']*100):.1f}%

*Estimated Usage:*
• Short messages (100 chars): ~{quota['remaining']//100:,} times
• Medium messages (500 chars): ~{quota['remaining']//500:,} times
        """
        
        await update.message.reply_text(quota_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "browse_voices":
            await self.show_voices(update, context)
        elif data == "set_code":
            await query.edit_message_text(
                "Enter your access code:\n`TTS-XXXXXXXXXXXXXXX`\n\n"
                "Type /cancel to go back.",
                parse_mode=ParseMode.MARKDOWN
            )
        elif data == "check_quota":
            await self.check_quota(update, context)
    
    async def show_voices(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show available voices"""
        query = update.callback_query
        
        voices = await self.db.get_all_voices()
        
        if not voices:
            await query.edit_message_text("❌ No voices available")
            return
        
        # Create voice buttons (max 8 per page)
        keyboard = []
        row = []
        
        for i, voice in enumerate(voices[:8], 1):
            emoji = "👨" if voice.get('gender') == 'male' else "👩" if voice.get('gender') == 'female' else "👤"
            button_text = f"{emoji} {voice['name'][:12]}"
            
            row.append(
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"voice_{voice['voice_id']}"
                )
            )
            
            if i % 2 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_start")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎵 *Select a Voice*\n\n"
            "Click a voice to set as default",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def setup_commands(self):
        """Setup bot commands"""
        commands = [
            ("start", "Start the bot"),
            ("help", "Show help"),
            ("tts", "Convert text to speech"),
            ("mycode", "Set access code"),
            ("myquota", "Check quota"),
            ("voices", "Browse voices"),
            ("settings", "Configure settings"),
        ]
        
        await self.application.bot.set_my_commands(commands)
    
    def run(self):
        """Run the bot"""
        # Create application
        self.application = Application.builder().token(self.bot_token).build()
        
        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("tts", self.tts_command))
        self.application.add_handler(CommandHandler("mycode", self.set_access_code))
        self.application.add_handler(CommandHandler("myquota", self.check_quota))
        
        # Callback handler
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Message handler
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_message
        ))
        
        # Setup commands
        self.application.post_init = self.setup_commands
        
        # Start polling
        logger.info("🤖 Starting Telegram bot...")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages"""
        # If user is setting access code
        message = update.message.text
        
        if message.startswith('TTS-'):
            # User is entering access code
            await self.set_access_code(update, context)
        else:
            await update.message.reply_text(
                "Send me text with /tts command.\n"
                "Example: `/tts Hello world`",
                parse_mode=ParseMode.MARKDOWN
            )


# Create bot instance
bot = TelegramBot()