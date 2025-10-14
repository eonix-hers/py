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
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters
from telegram.constants import ChatAction
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables
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
used_names = defaultdict(set)
success_count = 0
fail_count = 0
lock = asyncio.Lock()

# Conversation states for /run
STATE_USERNAME, STATE_PASSWORD, STATE_URL, STATE_PREFIX, STATE_TASKS = range(5)

async def is_user_approved(user_id):
    return str(user_id) in APPROVED_USERS

async def get_session_id(username, password):
    url = 'https://www.instagram.com/api/v1/web/accounts/login/ajax/'
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'x-csrftoken': 'missing',
        'referer': 'https://www.instagram.com/'
    }
    timestamp = str(int(time.time()))
    data = {
        'username': username,
        'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{timestamp}:{password}'
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200 and "sessionid" in response.cookies:
            return response.cookies.get("sessionid")
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text[:100]}")
    except requests.RequestException as e:
        raise Exception(f"Network error: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_approved(update.effective_user.id):
        await context.bot.send_message(update.effective_chat.id, "Access denied.")
        return
    await context.bot.send_message(update.effective_chat.id, "Welcome! Use /run to start the process or /help for a list of commands.")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_approved(update.effective_user.id):
        await context.bot.send_message(update.effective_chat.id, "Access denied.")
        return
    help_message = """
Available commands and examples:

- /start: Sends a welcome message and instructions. Example: Send /start to begin.

- /run: Starts the step-by-step process to enter Instagram details and begin renaming groups. Example: Send /run, then follow prompts: enter username (e.g., @infame_eonix), password (e.g., eonix_password as a placeholder), URLs, prefix, and tasks.

- /help: Displays this list of commands and their descriptions. Example: Send /help to see this message.

- /approve <user_id>: Adds a user to the approved list (owner only). Example: Send /approve 123456789 to approve a user.

- /ban <user_id>: Permanently bans a user from using the bot (owner only). Example: Send /ban 123456789 to ban a user.

- /listusers: Lists all approved users (owner only). Example: Send /listusers to see the list.

- /tban <user_id> [duration]: Temporarily bans a user for a specified number of minutes (owner only). Example: Send /tban 123456789 60 to ban a user for 60 minutes.

- /stop: Stops all running processes for your session. Example: Send /stop during a /run process to cancel it.

Remember, examples like 'eonix_password' are placeholders. Always use your own secure password.
    """
    await context.bot.send_message(update.effective_chat.id, help_message)

async def run_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_approved(update.effective_user.id):
        await context.bot.send_message(update.effective_chat.id, "Access denied.")
        return ConversationHandler.END
    await context.bot.send_message(update.effective_chat.id, "Please enter your Instagram username:")
    return STATE_USERNAME

async def get_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    await context.bot.send_message(update.effective_chat.id, "Please enter your Instagram password:")
    return STATE_PASSWORD

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['password'] = update.message.text
    username = context.user_data['username']
    password = context.user_data['password']
    try:
        session_id = await get_session_id(username, password)
        context.user_data['session_id'] = session_id
        await context.bot.send_message(update.effective_chat.id, "Logged in successfully!")
        await context.bot.send_message(update.effective_chat.id, "Please enter the group URLs (comma-separated):")
        return STATE_URL
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Login failed: {str(e)}. Please start over with /run.")
        return ConversationHandler.END

async def get_urls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['group_urls'] = [url.strip() for url in update.message.text.split(',')]
    await context.bot.send_message(update.effective_chat.id, "Please enter the prefix:")
    return STATE_PREFIX

async def get_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['user_prefix'] = update.message.text
    await context.bot.send_message(update.effective_chat.id, "Please enter the number of tasks:")
    return STATE_TASKS

async def get_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['task_count'] = int(update.message.text)
    session_id = context.user_data['session_id']
    group_urls = context.user_data['group_urls']
    user_prefix = context.user_data['user_prefix']
    task_count = context.user_data['task_count']
    delay = 0.05  # Fixed delay
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context_playwright = await browser.new_context()
            tasks = []
            for url in group_urls:
                loop_tasks = [asyncio.create_task(rename_loop(context_playwright, url, session_id, user_prefix, task_count, delay)) for _ in range(task_count)]
                tasks.extend(loop_tasks)
            stats_task = asyncio.create_task(live_stats(update, context))
            tasks.append(stats_task)
            running_tasks[update.effective_chat.id] = tasks
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                await context.bot.send_message(update.effective_chat.id, "Processes stopped.")
        return ConversationHandler.END
    except Exception as e:
        await context.bot.send_message(update.effective_chat.id, f"Error starting process: {str(e)}")
        return ConversationHandler.END

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_user_approved(update.effective_user.id):
        await context.bot.send_message(update.effective_chat.id, "Access denied.")
        return ConversationHandler.END
    chat_id = update.effective_chat.id
    if chat_id in running_tasks and running_tasks[chat_id]:
        for task in running_tasks[chat_id]:
            task.cancel()
        running_tasks[chat_id] = []
        await context.bot.send_message(update.effective_chat.id, "All running processes have been stopped.")
    else:
        await context.bot.send_message(update.effective_chat.id, "No running processes to stop.")
    return ConversationHandler.END

async def get_session_id(username, password):
    url = 'https://www.instagram.com/api/v1/web/accounts/login/ajax/'
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
        'x-csrftoken': 'missing',
        'referer': 'https://www.instagram.com/'
    }
    timestamp = str(int(time.time()))
    data = {
        'username': username,
        'enc_password': f'#PWD_INSTAGRAM_BROWSER:0:{timestamp}:{password}'
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        if response.status_code == 200 and "sessionid" in response.cookies:
            return response.cookies.get("sessionid")
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text[:100]}")
    except requests.RequestException as e:
        raise Exception(f"Network error: {str(e)}")

async def rename_loop(context, dm_url, session_id, user_prefix, task_count, delay=0.05):
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
            await asyncio.sleep(delay)
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
        if name not in used_names:
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


# ===== Admin Commands =====

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(OWNER_ID):
        await update.message.reply_text("Only the owner can approve users.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    user_id = context.args[0]
    APPROVED_USERS.add(user_id)
    with open(APPROVED_USERS_FILE, "w") as f:
        for uid in APPROVED_USERS:
            f.write(uid + "\n")

    await update.message.reply_text(f"✅ User {user_id} approved.")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(OWNER_ID):
        await update.message.reply_text("Only the owner can ban users.")
        return

    if len(context.args) != 1:
        await update.message.reply_text("Usage: /ban <user_id>")
        return

    user_id = context.args[0]
    if user_id in APPROVED_USERS:
        APPROVED_USERS.remove(user_id)
        with open(APPROVED_USERS_FILE, "w") as f:
            for uid in APPROVED_USERS:
                f.write(uid + "\n")
        await update.message.reply_text(f"🚫 User {user_id} has been banned.")
    else:
        await update.message.reply_text("User not found in approved list.")


async def listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(OWNER_ID):
        await update.message.reply_text("Only the owner can view approved users.")
        return

    if APPROVED_USERS:
        users_list = "\n".join(APPROVED_USERS)
        await update.message.reply_text(f"📜 Approved Users:\n{users_list}")
    else:
        await update.message.reply_text("No approved users found.")


async def tban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(OWNER_ID):
        await update.message.reply_text("Only the owner can temporarily ban users.")
        return

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /tban <user_id> <minutes>")
        return

    user_id, duration = context.args[0], int(context.args[1])

    if user_id in APPROVED_USERS:
        APPROVED_USERS.remove(user_id)
        await update.message.reply_text(f"⏳ User {user_id} temporarily banned for {duration} minutes.")

        # Restore approval after duration
        async def restore_user():
            await asyncio.sleep(duration * 60)
            APPROVED_USERS.add(user_id)
            with open(APPROVED_USERS_FILE, "w") as f:
                for uid in APPROVED_USERS:
                    f.write(uid + "\n")

        asyncio.create_task(restore_user())
    else:
        await update.message.reply_text("User not found in approved list.")


if __name__ == '__main__':
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('run', run_start)],
        states={
            STATE_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_username)],
            STATE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            STATE_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_urls)],
            STATE_PREFIX: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_prefix)],
            STATE_TASKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_tasks)],
        },
        fallbacks=[CommandHandler('stop', stop)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('approve', approve_user))
    application.add_handler(CommandHandler('ban', ban_user))
    application.add_handler(CommandHandler('listusers', listusers))
    application.add_handler(CommandHandler('tban', tban_user))
    application.add_handler(CommandHandler('stop', stop))
    application.run_polling()