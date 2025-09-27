import asyncio
import logging
import json
import os
from datetime import datetime
from typing import Dict, List, Set
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import BOT_TOKEN

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Data storage files
USERS_DATA_FILE = "users_data.json"
LOGS_FILE = "bot_logs.txt"

# In-memory storage
users_data = {}  # user_id: {"channels": {}, "active_channels": set(), "current_target": None}
user_logs = []

def load_data():
    """Load users data from file."""
    global users_data
    try:
        if os.path.exists(USERS_DATA_FILE):
            with open(USERS_DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Convert sets back from lists
                for user_id, user_data in data.items():
                    user_data['active_channels'] = set(user_data.get('active_channels', []))
                users_data = data
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        users_data = {}

def save_data():
    """Save users data to file."""
    try:
        # Convert sets to lists for JSON serialization
        data_to_save = {}
        for user_id, user_data in users_data.items():
            data_copy = user_data.copy()
            data_copy['active_channels'] = list(user_data.get('active_channels', set()))
            data_to_save[user_id] = data_copy
        
        with open(USERS_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def log_action(user: types.User, action: str, details: str = ""):
    """Log user actions to file and memory."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = user.username if user.username else "No username"
    full_name = f"{user.first_name} {user.last_name}" if user.last_name else user.first_name
    
    log_entry = f"[{timestamp}] User: {full_name} (@{username}, ID: {user.id}) | Action: {action} | Details: {details}"
    
    # Add to memory
    user_logs.append(log_entry)
    
    # Write to file
    try:
        with open(LOGS_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")
    except Exception as e:
        logger.error(f"Error writing log: {e}")
    
    # Print to console
    print(log_entry)

def initialize_user(user_id: int):
    """Initialize user data if not exists."""
    if str(user_id) not in users_data:
        users_data[str(user_id)] = {
            "channels": {},  # channel_id: {"name": "...", "added_date": "..."}
            "active_channels": set(),
            "current_target": None
        }

@dp.message(CommandStart())
async def start_command(message: Message):
    """Send a welcome message when the command /start is issued."""
    user_id = str(message.from_user.id)
    initialize_user(user_id)
    
    log_action(message.from_user, "START_COMMAND", "Bot started")
    
    welcome_text = (
        "✅ Assalomu alaykum\n\n"
        "🤖 Xabarlarni yo'naltiruvchi botga xush kelibsiz!\n\n"
        "Qanday foydalanish:\n"
        "1. Menga kanal yoki guruh ID sini yuboring (masalan: -1001234567890)\n"
        "2. Men barcha ID larni eslab qolaman\n"
        "3. /status buyrug'i orqali barcha ID larni ko'ring\n"
        "4. Har qanday xabar/fayl yuboring va men uni tanlangan kanalingizga jo'nataman\n\n"
        "⚠️ Muhim: Botni kanallaringizga admin qilib qo'shishni unutmang!\n\n"
        "Buyruqlar:\n"
        "/start - Ushbu xabarni ko'rsatish\n"
        "/help - Yordam\n"
        "/status - Barcha kanal/guruh ID larni ko'rish\n"
        "/clear - Tanlangan kanal/guruh ID larni o'chirish\n"
        "/logs - Oxirgi 10 ta log yozuvini ko'rish (faqat admin uchun)"
    )
    await message.answer(welcome_text)

@dp.message(Command("help"))
async def help_command(message: Message):
    """Send help information."""
    log_action(message.from_user, "HELP_COMMAND")
    
    help_text = (
        "📋 Kanal/Guruh ID sini qanday olish:\n\n"
        "Guruhlar uchun:\n"
        "1. @userinfobot ni guruingizga qo'shing\n"
        "2. /id buyrug'ini yuboring\n"
        "3. Guruh ID sini nusxalang (-100 bilan boshlanadi)\n\n"
        "Kanallar uchun:\n"
        "1. Kanalingizdan biror xabarni @userinfobot ga yo'naltiring\n"
        "2. U sizga kanal ID sini ko'rsatadi\n\n"
        "Keyin menga ID ni yuboring va xabarlarni yo'naltirishni boshlang!\n\n"
        "💡 Bot bir nechta kanal/guruh ID sini saqlashi mumkin!"
    )
    await message.answer(help_text)

@dp.message(Command("status"))
async def status_command(message: Message):
    """Show all channel/group IDs for the user and let them select target."""
    user_id = str(message.from_user.id)
    initialize_user(user_id)
    
    log_action(message.from_user, "STATUS_COMMAND")
    
    user_data = users_data[user_id]
    active_channels = user_data.get('active_channels', set())
    all_channels = user_data.get('channels', {})
    
    if not active_channels:
        await message.answer("❌ Hech qanday faol kanal/guruh ID si yo'q. Avval ID yuboring!")
        return
    
    # Create status message
    status_text = "📋 Sizning faol kanal/guruh ID lari:\n\n"
    keyboard_buttons = []
    
    for i, channel_id in enumerate(active_channels, 1):
        channel_info = all_channels.get(channel_id, {})
        channel_name = channel_info.get('name', 'Noma\'lum kanal')
        added_date = channel_info.get('added_date', 'Noma\'lum sana')
        
        current_marker = "🎯 " if user_data.get('current_target') == channel_id else ""
        status_text += f"{i}. {current_marker}{channel_name}\n   ID: {channel_id}\n   Qo'shilgan: {added_date}\n\n"
        
        # Create inline button
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=f"{current_marker}{i}. {channel_name}", 
                callback_data=f"select_{channel_id}"
            )
        ])
    
    keyboard_buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    status_text += "Qaysi kanal/guruhga xabar jo'natmoqchisiz? Pastdan tanlang:"
    
    await message.answer(status_text, reply_markup=keyboard)

@dp.callback_query(F.data.startswith("select_"))
async def select_channel(callback: CallbackQuery):
    """Handle channel selection."""
    channel_id = callback.data.replace("select_", "")
    user_id = str(callback.from_user.id)
    
    users_data[user_id]['current_target'] = channel_id
    save_data()
    
    channel_info = users_data[user_id]['channels'].get(channel_id, {})
    channel_name = channel_info.get('name', channel_id)
    
    log_action(callback.from_user, "CHANNEL_SELECTED", f"Selected: {channel_name} ({channel_id})")
    
    await callback.message.edit_text(f"✅ Tanlandi: {channel_name}\n\nEndi xabarlaringiz shu kanalga jo'natiladi!")
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_selection(callback: CallbackQuery):
    """Cancel channel selection."""
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()

@dp.message(Command("clear"))
async def clear_command(message: Message):
    """Clear active channel/group IDs but keep them in logs."""
    user_id = str(message.from_user.id)
    initialize_user(user_id)
    
    user_data = users_data[user_id]
    active_channels = user_data.get('active_channels', set())
    
    if not active_channels:
        await message.answer("❌ O'chiriladigan kanal/guruh ID si yo'q.")
        return
    
    # Log cleared channels
    cleared_channels = list(active_channels)
    log_action(message.from_user, "CHANNELS_CLEARED", f"Cleared {len(cleared_channels)} channels: {cleared_channels}")
    
    # Clear active channels but keep in history
    user_data['active_channels'] = set()
    user_data['current_target'] = None
    save_data()
    
    await message.answer(f"✅ {len(cleared_channels)} ta kanal/guruh ID si o'chirildi!\n\n📝 Barcha ma'lumotlar log faylida saqlanib qoldi.")

@dp.message(Command("logs"))
async def logs_command(message: Message):
    """Show recent logs (admin only for now)."""
    log_action(message.from_user, "LOGS_REQUESTED")
    
    if not user_logs:
        await message.answer("📝 Hozircha loglar yo'q.")
        return
    
    # Get last 10 logs
    recent_logs = user_logs[-10:]
    logs_text = "📝 Oxirgi 10 ta log yozuvi:\n\n"
    
    for log in recent_logs:
        logs_text += f"{log}\n\n"
    
    if len(logs_text) > 4000:  # Telegram message limit
        logs_text = logs_text[:4000] + "...\n\n📄 To'liq loglar bot_logs.txt faylida."
    
    await message.answer(logs_text)

@dp.message(F.text)
async def handle_text_message(message: Message):
    """Handle text messages (including channel IDs) or send them."""
    user_id = str(message.from_user.id)
    initialize_user(user_id)
    message_text = message.text
    
    # Check if message looks like a channel/group ID
    if message_text and (message_text.startswith('-100') or message_text.startswith('@')):
        # Add new channel/group ID
        user_data = users_data[user_id]
        
        # Get channel name (try to fetch info)
        channel_name = message_text
        try:
            chat_info = await bot.get_chat(message_text)
            channel_name = chat_info.title if chat_info.title else message_text
        except:
            pass
        
        # Add to channels dict and active set
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data['channels'][message_text] = {
            "name": channel_name,
            "added_date": current_time
        }
        user_data['active_channels'].add(message_text)
        
        # Set as current target if first channel or no current target
        if not user_data.get('current_target'):
            user_data['current_target'] = message_text
        
        save_data()
        log_action(message.from_user, "CHANNEL_ADDED", f"Added: {channel_name} ({message_text})")
        
        await message.answer(
            f"✅ Kanal/Guruh qo'shildi: {channel_name}\n"
            f"ID: {message_text}\n\n"
            f"Jami kanallar: {len(user_data['active_channels'])}\n"
            f"Joriy maqsad: {channel_name}\n\n"
            "📋 Barcha kanallarni ko'rish uchun /status buyrug'ini ishlating."
        )
        return
    
    # Send message to selected channel
    await send_to_channel(message)

async def send_to_channel(message: Message):
    """Send message content to the selected channel/group."""
    user_id = str(message.from_user.id)
    user_data = users_data[user_id]
    target_chat = user_data.get('current_target')
    
    if not target_chat:
        await message.answer(
            "❌ Maqsad kanal/guruh tanlanmagan!\n"
            "Avval kanal ID yuboring yoki /status orqali tanlang."
        )
        return
    
    try:
        # Send different types of content based on message type
        if message.text:
            await bot.send_message(chat_id=target_chat, text=message.text)
            log_action(message.from_user, "TEXT_SENT", f"To: {target_chat}, Length: {len(message.text)}")
        elif message.photo:
            await bot.send_photo(
                chat_id=target_chat, 
                photo=message.photo[-1].file_id,
                caption=message.caption
            )
            log_action(message.from_user, "PHOTO_SENT", f"To: {target_chat}")
        elif message.video:
            await bot.send_video(
                chat_id=target_chat,
                video=message.video.file_id,
                caption=message.caption
            )
            log_action(message.from_user, "VIDEO_SENT", f"To: {target_chat}")
        elif message.document:
            await bot.send_document(
                chat_id=target_chat,
                document=message.document.file_id,
                caption=message.caption
            )
            log_action(message.from_user, "DOCUMENT_SENT", f"To: {target_chat}, Name: {message.document.file_name}")
        elif message.audio:
            await bot.send_audio(
                chat_id=target_chat,
                audio=message.audio.file_id,
                caption=message.caption
            )
            log_action(message.from_user, "AUDIO_SENT", f"To: {target_chat}")
        elif message.voice:
            await bot.send_voice(
                chat_id=target_chat,
                voice=message.voice.file_id,
                caption=message.caption
            )
            log_action(message.from_user, "VOICE_SENT", f"To: {target_chat}")
        elif message.sticker:
            await bot.send_sticker(
                chat_id=target_chat,
                sticker=message.sticker.file_id
            )
            log_action(message.from_user, "STICKER_SENT", f"To: {target_chat}")
        elif message.animation:
            await bot.send_animation(
                chat_id=target_chat,
                animation=message.animation.file_id,
                caption=message.caption
            )
            log_action(message.from_user, "ANIMATION_SENT", f"To: {target_chat}")
        elif message.video_note:
            await bot.send_video_note(
                chat_id=target_chat,
                video_note=message.video_note.file_id
            )
            log_action(message.from_user, "VIDEO_NOTE_SENT", f"To: {target_chat}")
        elif message.location:
            await bot.send_location(
                chat_id=target_chat,
                latitude=message.location.latitude,
                longitude=message.location.longitude
            )
            log_action(message.from_user, "LOCATION_SENT", f"To: {target_chat}")
        elif message.contact:
            await bot.send_contact(
                chat_id=target_chat,
                phone_number=message.contact.phone_number,
                first_name=message.contact.first_name,
                last_name=message.contact.last_name
            )
            log_action(message.from_user, "CONTACT_SENT", f"To: {target_chat}")
        
        # Get channel name for success message
        channel_info = user_data['channels'].get(target_chat, {})
        channel_name = channel_info.get('name', target_chat)
        
        # Send success message and delete it after 3 seconds
        success_msg = await message.answer(f"✅ Xabar muvaffaqiyatli jo'natildi!\n📤 Maqsad: {channel_name}")
        await asyncio.sleep(3)
        await success_msg.delete()
        
    except Exception as e:
        channel_info = user_data['channels'].get(target_chat, {})
        channel_name = channel_info.get('name', target_chat)
        
        log_action(message.from_user, "SEND_ERROR", f"To: {target_chat}, Error: {str(e)}")
        
        error_msg = (
            f"❌ Xabarni jo'natishda xatolik!\n"
            f"📤 Maqsad: {channel_name}\n"
            f"🔧 Xatolik: {str(e)}\n\n"
            "Mumkin bo'lgan sabablar:\n"
            "• Bot maqsad kanal/guruhda admin emas\n"
            "• Noto'g'ri kanal/guruh ID si\n"
            "• Kanal/guruh mavjud emas\n"
            "• Bot kanal/guruhdan o'chirilgan"
        )
        # Send error message and delete it after 10 seconds
        error_message = await message.answer(error_msg)
        await asyncio.sleep(10)
        try:
            await error_message.delete()
        except:
            pass

# Handle all media types with the same function
@dp.message(F.photo | F.video | F.document | F.audio | F.voice | F.sticker | F.animation | F.video_note | F.location | F.contact)
async def handle_media_message(message: Message):
    """Handle all media types."""
    user_id = str(message.from_user.id)
    initialize_user(user_id)
    await send_to_channel(message)

async def main():
    """Start the bot."""
    # Load existing data
    load_data()
    
    print("Bot ishga tushmoqda...")
    log_action(types.User(id=0, is_bot=True, first_name="System"), "BOT_STARTED", "Bot initialized")
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())