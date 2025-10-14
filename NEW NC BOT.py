import asyncio
import logging
import os
import random
import sys
import requests
import time
from collections import defaultdict
from urllib.parse import unquote
from itertools import count
from playwright.async_api import async_playwright
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ChatAction
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID", "❤❤❤❤❤❤❤❤❤❤")
APPROVED_USERS_FILE = "approved_users.txt"
running_tasks = defaultdict(list)

if os.path.exists(APPROVED_USERS_FILE):
    with open(APPROVED_USERS_FILE, "r") as f:
        APPROVED_USERS = set(line.strip() for line in f)
else:
    APPROVED_USERS = set([OWNER_ID])

COLORS = {
    'red': '\033[1;31m',
    'green': '\033[1;32m',
    'yellow': '\033[1;33m',
    'cyan': '\033[36m',
    'blue': '\033[1;34m',
    'reset': '\033[0m',
}

ufo_bases = [
    "  ⭞ ᴄᴜᴅ ￫", "  ⭞ ʀᴏᴏ ￫", "  ⭞ ᴛᴍᴋᴄ ￫", "  ⭞ ᴄʜᴜᴛ ￫",
    "  ⭞ ʟᴜɴᴅ ￫", "  ⭞ ᴍᴄ ￫", "  ⭞ ʙᴄ ￫", "  ⭞ ʙᴋʟ ￫",
    "  ⭞ ᴍᴋʟ ￫", "  ⭞ ᴛᴍᴋʟ ￫", "  ⭞ ᴛʙᴋʟ ￫", "  ⭞ ᴛʙᴋᴄ ￫",
    "  ⭞ ᴄᴠʀ ᴋᴀʀ ￫", "  ⭞ ᴍᴀʀᴀ ￫", "  ⭞ ʀᴀɴᴅ ￫", "  ⭞ ᴄʜɪɴᴀʟ ￫",
    "  ⭞ ᴄᴜᴅᴀ ￫", "  ⭞ ᴛᴀᴛᴛᴀ ￫", "  ⭞ ᴋᴜᴛɪʏᴀ ￫", "  ⭞ ɢᴜᴜ ᴋʜᴀ ￫",
    "  ⭞ ɢɴᴅ ᴅɪᴋʜᴀ ￫", "  ⭞ ʟᴜɴᴅ ʟᴇ ￫", "  ⭞ ʀɴᴅɪᴋᴇ ￫", "  ⭞ ᴄʜɪɴᴀʟ ￫",
    "  ⭞ ʙɪᴛᴄʜ ￫", "  ⭞ ɢᴀʀᴇᴇʙ ￫", "  ⭞ ɢᴜʟᴀᴍ ￫", "  ⭞ ᴛᴅᴋʟ ￫",
    "  ⭞ ʀɴᴅ ￫", "  ⭞ ᴄᴜᴅᴀᴀ ￫", "  ⭞ ʀɴᴅɪᴄᴀ ￫", "  ⭞ ᴋᴜᴛɪʏᴀ ￫",
    "  ⭞ ᴄʜᴀᴍᴀʀ ￫", "  ⭞ ᴄᴠʀ ᴄʀʀ ￫", "  ⭞ ᴋᴀᴍᴢᴏʀ ￫"
]
emoji_suffixes = ["⚡", "💋", "👅", "🖕", "🐷", "💩", "🔥"]
name_counter = count(1)
used_names = defaultdict(set)  # Per chat or group, but keeping global for simplicity
success_count = 0
fail_count = 0
lock = asyncio.Lock()

async def is_user_approved(user_id):
    return str(user_id) in APPROVED_USERS

async def rename_loop(context, dm_url, session_id, user_prefix, task_count, delay=0.01):
    global success_count, fail_count
    page = await context.new_page()
    try:
        await page.goto(dm_url)
        await page.add_cookies([{"name": "sessionid", "value": session_id, "domain": ".instagram.com"}])
        gear = page.locator('svg[aria-label="Conversation information"]')
        await gear.click()
        change_btn = page.locator('div[aria-label="Change group name"]')
        group_input = page.locator('input[aria-label="Group name"]')
        save_btn = page.locator('div:has-text("Save")')
        while not asyncio.current_task().done():
            name = generate_name(user_prefix)
            await change_btn.click()
            await group_input.fill(name)
            if await save_btn.get_attribute("aria-disabled") != "true":
                await save_btn.click()
                async with lock:
                    success_count += 1
            else:
                async with lock:
                    fail_count += 1
            await asyncio.sleep(max(delay, 0.01))
    except asyncio.CancelledError:
        logging.info("Task cancelled.")
    except Exception as e:
        async with lock:
            fail_count += 1
        logging.error(f"Rename failed: {e}")

def generate_name(user_prefix):
    while True:
        base = random.choice(ufo_bases).strip()
        emoji = random.choice(emoji_suffixes)
        suffix = next(name_counter)
        name = f"{user_prefix} {base} {emoji}_{suffix}"
        if name not in used_names:  # Simple global check
            used_names.add(name)
            return name

async def live_stats(update, context):
    message = await context.bot.send_message(update.effective_chat.id, "Starting for multiple groups...")
    while not asyncio.current_task().done():
        async with lock:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=message.message_id,
                text=f"Progress: Success: {success_count} | Failed: {fail_count}"
            )
        await asyncio.sleep(5)

async def run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_approved(update.effective_user.id):
        await context.bot.send_message(update.effective_chat.id, "Access denied.")
        return
    if len(context.args) < 5 or len(context.args) > 6:
        await context.bot.send_message(update.effective_chat.id, "Usage: /run <username> <password> <group_urls> <prefix> <tasks> [delay_in_seconds]")
        return
    username, password, group_urls_str, user_prefix, tasks_str = context.args[:5]
    delay = float(context.args[5]) if len(context.args) > 5 else 0.01
    task_count = int(tasks_str)
    group_urls = [url.strip() for url in group_urls_str.split(',')]  # Split comma-separated URLs
    try:
        session_id = await get_session_id(username, password)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context_playwright = await browser.new_context()
            tasks = []
            for url in group_urls:
                loop_tasks = [asyncio.create_task(rename_loop(context_playwright, url, session_id, user_prefix, task_count, delay)) for _ in range(task_count)]
                tasks.extend(loop_tasks)
            stats_task = asyncio.create_task(live_stats(update, context))
            tasks.append(stats_task)
            running_tasks[update.effective_chat.id] = tasks  # Store all tasks
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                await context.bot.send_message(update.effective_chat.id, "Processes stopped.")
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Error: {e}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_approved(update.effective_user.id):
        await context.bot.send_message(update.effective_chat.id, "Access denied.")
        return
    chat_id = update.effective_chat.id
    if chat_id in running_tasks and running_tasks[chat_id]:
        for task in running_tasks[chat_id]:
            task.cancel()
        running_tasks[chat_id] = []
        await context.bot.send_message(update.effective_chat.id, "All running processes have been stopped.")
    else:
        await context.bot.send_message(update.effective_chat.id, "No running processes to stop.")

if __name__ == '__main__':
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('approve', approve_user))
    application.add_handler(CommandHandler('run', run))
    application.add_handler(CommandHandler('ban', ban_user))
    application.add_handler(CommandHandler('listusers', listusers))
    application.add_handler(CommandHandler('tban', tban_user))
    application.add_handler(CommandHandler('stop', stop))
    application.run_polling()