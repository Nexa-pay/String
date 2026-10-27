import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from pyromod import listen
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeExpired
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError

# --- CONFIGURATION ---
BOT_TOKEN = "8701869062:AAFTGGGkI-pg2ZyWkq9e7mRhvR5Q9jGDwuk"
API_ID = "37133457"
API_HASH = "951a895d6016c9d88880f9591209dbc2"

bot = Client("SessionGeneratorBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
    
    # 1. Ask for Phone Number using a Contact Request Button
    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 Share Phone Number", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await bot.send_message(
        chat_id, 
        f"**Starting {lib_type.capitalize()} Session Generation...**\n\n"
        "Please tap the **📱 Share Phone Number** button below, or type it manually with the country code (e.g., +91...):",
        reply_markup=contact_keyboard
    )
    
    try:
        phone_msg = await bot.listen(chat_id, timeout=300)
        
        # Check if they used the button or typed it manually
        if phone_msg.contact:
            phone_number = phone_msg.contact.phone_number
        else:
            phone_number = phone_msg.text.replace(" ", "")
            
        # Hide the big keyboard
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
    user_client = Client(":memory:", api_id=api_id, api_hash=api_hash)
    await user_client.connect()
    
    try:
        code_info = await user_client.send_code(phone_number)
        await bot.send_message(
            chat_id, 
            "✅ **Code sent!** Check your Telegram messages.\n\n"
            "Send the OTP below. *(You can send it normally like `12345` or with spaces `1 2 3 4 5`)*"
        )
        
        otp_msg = await bot.listen(chat_id, timeout=300)
        # Extracts only the digits so it works with or without spaces/dashes
        otp = re.sub(r'\D', '', otp_msg.text) 
        
        try:
            await user_client.sign_in(phone_number, code_info.phone_code_hash, otp)
        except SessionPasswordNeeded:
            await bot.send_message(chat_id, "🔐 **2FA is enabled!**\n\nPlease send your Two-Step Verification password:")
            pwd_msg = await bot.listen(chat_id, timeout=300)
            await user_client.check_password(pwd_msg.text)
        except PhoneCodeExpired:
            await bot.send_message(chat_id, "❌ **Error:** The OTP code has expired. Please type /start to try again.")
            return
            
        session_string = await user_client.export_session_string()
        await send_session(chat_id, session_string, "Pyrogram", user_client)
        
    except Exception as e:
        await bot.send_message(chat_id, f"**Login Failed:** `{e}`")
    finally:
        await user_client.disconnect()

async def generate_telethon(chat_id, api_id, api_hash, phone_number):
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()
    
    try:
        code_info = await client.send_code_request(phone_number)
        await bot.send_message(
            chat_id, 
            "✅ **Code sent!** Check your Telegram messages.\n\n"
            "Send the OTP below. *(You can send it normally like `12345` or with spaces `1 2 3 4 5`)*"
        )
        
        otp_msg = await bot.listen(chat_id, timeout=300)
        otp = re.sub(r'\D', '', otp_msg.text)
        
        try:
            await client.sign_in(phone_number, code_info.phone_code_hash, otp)
        except SessionPasswordNeededError:
            await bot.send_message(chat_id, "🔐 **2FA is enabled!**\n\nPlease send your Two-Step Verification password:")
            pwd_msg = await bot.listen(chat_id, timeout=300)
            await client.sign_in(password=pwd_msg.text)
        except PhoneCodeExpiredError:
            await bot.send_message(chat_id, "❌ **Error:** The OTP code has expired. Please type /start to try again.")
            return
            
        session_string = client.session.save()
        
        temp_pyro = Client(":memory:", api_id=api_id, api_hash=api_hash, session_string=session_string)
        await temp_pyro.connect()
        await send_session(chat_id, session_string, "Telethon", temp_pyro)
        await temp_pyro.disconnect()
        
    except Exception as e:
        await bot.send_message(chat_id, f"**Login Failed:** `{e}`")
    finally:
        await client.disconnect()

async def send_session(chat_id, session_string, lib_type, user_client):
    text = f"**{lib_type} String Session**\n\n`{session_string}`\n\n**⚠️ Keep this private! Do not share it with anyone!**"
    try:
        await user_client.send_message("me", text)
        await bot.send_message(chat_id, "🎉 **Success!** Your string session has been securely sent to your **Saved Messages**.")
    except Exception:
        await bot.send_message(chat_id, f"**Success!** Here is your session:\n\n`{session_string}`")

if __name__ == "__main__":
    bot.run()
