import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyromod import listen
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

# --- CONFIGURATION ---
BOT_TOKEN = "8701869062:AAFTGGGkI-pg2ZyWkq9e7mRhvR5Q9jGDwuk"
API_ID = "YOUR_API_ID"        # Kept as string or int
API_HASH = "YOUR_API_HASH"

bot = Client("SessionGeneratorBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Pyrogram", callback_data="gen_pyrogram")],
        [InlineKeyboardButton("Telethon", callback_data="gen_telethon")]
    ])
    await message.reply_text(
        "**Welcome to the String Session Generator!**\n\n"
        "Choose the library you want to generate a session for:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("gen_"))
async def generate_session(client, callback_query):
    lib_type = callback_query.data.split("_")[1]
    chat = callback_query.message.chat
    
    await callback_query.answer()
    
    try:
        # 1. Ask for Phone Number directly (skips API ID/Hash)
        await bot.send_message(chat.id, f"**Starting {lib_type.capitalize()} Session Generation...**\n\nSend your Phone Number with country code (e.g., +91...):")
        phone_msg = await bot.listen(chat.id, timeout=300)
        phone_number = phone_msg.text.replace(" ", "")

        # Pass the global API_ID and API_HASH automatically
        if lib_type == "pyrogram":
            await generate_pyrogram(chat.id, API_ID, API_HASH, phone_number)
        else:
            await generate_telethon(chat.id, API_ID, API_HASH, phone_number)
            
    except asyncio.TimeoutError:
        await bot.send_message(chat.id, "Time limit exceeded. Send /start again.")
    except Exception as e:
        await bot.send_message(chat.id, f"**Error:** `{e}`")

async def generate_pyrogram(chat_id, api_id, api_hash, phone_number):
    user_client = Client(":memory:", api_id=api_id, api_hash=api_hash)
    await user_client.connect()
    
    try:
        code_info = await user_client.send_code(phone_number)
        await bot.send_message(chat_id, "Code sent! Send the OTP.\n\n*(Note: If Telegram deletes your code, send it with spaces like `1 2 3 4 5`)*")
        
        otp_msg = await bot.listen(chat_id, timeout=300)
        # Fixes space/no-space OTP by extracting only the numbers
        otp = re.sub(r'\D', '', otp_msg.text)
        
        try:
            await user_client.sign_in(phone_number, code_info.phone_code_hash, otp)
        except Exception as e:
            if "SessionPasswordNeeded" in str(e):
                await bot.send_message(chat_id, "2FA is enabled! Send your password:")
                pwd_msg = await bot.listen(chat_id, timeout=300)
                await user_client.check_password(pwd_msg.text)
            else:
                raise e
                
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
        await bot.send_message(chat_id, "Code sent! Send the OTP.\n\n*(Note: If Telegram deletes your code, send it with spaces like `1 2 3 4 5`)*")
        
        otp_msg = await bot.listen(chat_id, timeout=300)
        # Fixes space/no-space OTP by extracting only the numbers
        otp = re.sub(r'\D', '', otp_msg.text)
        
        try:
            await client.sign_in(phone_number, code_info.phone_code_hash, otp)
        except SessionPasswordNeededError:
            await bot.send_message(chat_id, "2FA is enabled! Send your password:")
            pwd_msg = await bot.listen(chat_id, timeout=300)
            await client.sign_in(password=pwd_msg.text)
            
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
    text = f"**{lib_type} String Session**\n\n`{session_string}`\n\n**Keep this private!**"
    await user_client.send_message("me", text)
    await bot.send_message(chat_id, "**Success!** Your string session has been sent to your **Saved Messages** securely.")

if __name__ == "__main__":
    bot.run()
