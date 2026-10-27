import os
import re
import asyncio
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from pyromod import listen
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeExpired
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError

# Load environment variables securely from .env file
load_dotenv()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not all([BOT_TOKEN, API_ID, API_HASH]):
    raise ValueError("Missing configuration! Ensure your .env file has BOT_TOKEN, API_ID, and API_HASH.")

bot = Client("SessionGeneratorBot", api_id=int(API_ID), api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pyrogram", callback_data="gen_pyrogram")],
        [InlineKeyboardButton("Telethon", callback_data="gen_telethon")]
    ])
    await message.reply_text(
        "**Advanced String Session Generator 🚀**\n\n"
        "Choose the library you want to generate a session for:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("gen_"))
async def generate_session(client, callback_query):
    lib_type = callback_query.data.split("_")[1]
    chat_id = callback_query.message.chat.id
    
    await callback_query.answer()
    
    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Phone Number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await bot.send_message(
        chat_id, 
        f"**Starting {lib_type.capitalize()} Session...**\n\n"
        "Please tap the **📱 Share Phone Number** button below, or type it manually with the country code (e.g., +91...):",
        reply_markup=contact_keyboard
    )
    
    try:
        phone_msg = await bot.listen(chat_id, timeout=300)
        
        if phone_msg.contact:
            phone_number = phone_msg.contact.phone_number
        else:
            phone_number = phone_msg.text.replace(" ", "")
            
        await bot.send_message(chat_id, f"📲 Phone number received: `{phone_number}`\nProcessing...", reply_markup=ReplyKeyboardRemove())

        if lib_type == "pyrogram":
            await generate_pyrogram(chat_id, API_ID, API_HASH, phone_number)
        else:
            await generate_telethon(chat_id, API_ID, API_HASH, phone_number)
            
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏳ Time limit exceeded. Send /start again.", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        await bot.send_message(chat_id, f"**Error:** `{e}`", reply_markup=ReplyKeyboardRemove())

async def generate_pyrogram(chat_id, api_id, api_hash, phone_number):
    user_client = Client(":memory:", api_id=int(api_id), api_hash=api_hash)
    await user_client.connect()
    
    try:
        code_info = await user_client.send_code(phone_number)
        await bot.send_message(
            chat_id, 
            "✅ **Code sent!** Check your Telegram messages.\n\n"
            "⚠️ **SECURITY RULE:** Do NOT send the code directly!\n"
            "👉 **Add a word before the code.**\n"
            "Example: If your code is `12345`, send it as `code 1 2 3 4 5`."
        )
        
        otp_msg = await bot.listen(chat_id, timeout=300)
        otp = re.sub(r'\D', '', otp_msg.text) 
        
        try:
            await user_client.sign_in(phone_number, code_info.phone_code_hash, otp)
        except SessionPasswordNeeded:
            await bot.send_message(chat_id, "🔐 **2FA is enabled!**\n\nPlease send your password:")
            pwd_msg = await bot.listen(chat_id, timeout=300)
            await user_client.check_password(pwd_msg.text)
        except PhoneCodeExpired:
            await bot.send_message(chat_id, "❌ **Error:** Code expired! You probably didn't add a word before the numbers. Type /start to try again.")
            return
            
        session_string = await user_client.export_session_string()
        await send_session(chat_id, session_string, "Pyrogram", user_client)
        
    except Exception as e:
        await bot.send_message(chat_id, f"**Login Failed:** `{e}`")
    finally:
        await user_client.disconnect()

async def generate_telethon(chat_id, api_id, api_hash, phone_number):
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.connect()
    
    try:
        code_info = await client.send_code_request(phone_number)
        await bot.send_message(
            chat_id, 
            "✅ **Code sent!** Check your Telegram messages.\n\n"
            "⚠️ **SECURITY RULE:** Do NOT send the code directly!\n"
            "👉 **Add a word before the code.**\n"
            "Example: If your code is `12345`, send it as `code 1 2 3 4 5`."
        )
        
        otp_msg = await bot.listen(chat_id, timeout=300)
        otp = re.sub(r'\D', '', otp_msg.text)
        
        try:
            await client.sign_in(phone_number, code_info.phone_code_hash, otp)
        except SessionPasswordNeededError:
            await bot.send_message(chat_id, "🔐 **2FA is enabled!**\n\nPlease send your password:")
            pwd_msg = await bot.listen(chat_id, timeout=300)
            await client.sign_in(password=pwd_msg.text)
        except PhoneCodeExpiredError:
            await bot.send_message(chat_id, "❌ **Error:** Code expired! You probably didn't add a word before the numbers. Type /start to try again.")
            return
            
        session_string = client.session.save()
        
        temp_pyro = Client(":memory:", api_id=int(api_id), api_hash=api_hash, session_string=session_string)
        await temp_pyro.connect()
        await send_session(chat_id, session_string, "Telethon", temp_pyro)
        await temp_pyro.disconnect()
        
    except Exception as e:
        await bot.send_message(chat_id, f"**Login Failed:** `{e}`")
    finally:
        await client.disconnect()

async def send_session(chat_id, session_string, lib_type, user_client):
    text = f"**{lib_type} String Session**\n\n`{session_string}`\n\n**⚠️ Keep this private!**"
    try:
        await user_client.send_message("me", text)
        await bot.send_message(chat_id, "🎉 **Success!** Your string session has been sent to your **Saved Messages**.")
    except Exception:
        await bot.send_message(chat_id, f"**Success!** Here is your session:\n\n`{session_string}`")

if __name__ == "__main__":
    bot.run()
