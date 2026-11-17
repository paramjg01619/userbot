"""
Telegram BUSINESS bot (official "Chat Automation" / Business Bots feature)

How it works:
- You create a bot with @BotFather and get a token (no login/OTP needed from users).
- Anyone (including you) goes to Telegram Settings -> Telegram Business ->
  Chatbots (the "Chat Automation" screen you showed) and adds this bot by its
  @username. Telegram itself asks them to grant permissions - nothing is
  collected by this bot/script.
- Once connected, the bot can act "on behalf of" that person in their PRIVATE
  chats: edit their own messages, send messages, delete messages it sent
  while connected.
- Each connected account gets its OWN saved addresses - totally separate.

LIMITATIONS vs a personal userbot (explained so nothing is oversold):
- No ".block" - the Bot API has no "block user" method, even for business bots.
- All .purge commands can only delete messages sent SINCE this bot started
  running and saw them (no access to old chat history).
- Business automation only covers PRIVATE chats. If you also add this bot to
  a GROUP as a normal member, it can reply to commands there too, but it
  posts its own reply instead of editing your message (bots can't edit
  other members' messages in a group).
- All commands use a "." prefix, so they won't show up in Telegram's built-in
  "/" command menu (that menu only lists "/" commands). Typing ".start" in
  chat still works and shows the full list.

Commands (owner types these in their own business-connected private chats,
or in a group if the bot is added there):
  .sol .btc .eth .bnb .xrp .ltc .trx   -> formatted address, tap to copy
  .addrs                                -> list saved coin commands
  .add NAME ADDRESS                     -> add/update an address
  .remove NAME                          -> remove an address
  .id                                   -> chat id / sender id info
  .purgeall                             -> delete tracked messages in this chat
  .purge1hr                             -> delete tracked messages from last 1 hour
  .purge1d                              -> delete tracked messages from last 1 day
  /start / /help                        -> show this command list

Note: ".block" is NOT included here. The Bot API has no "block user" method
at all, even for business-connected bots, so it can't be built here honestly.
That command only exists in the separate personal userbot script (bot.py),
which runs on your own account and can really block someone.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from telegram import Update, BotCommand
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, MessageHandler, filters

COMMAND_LIST_TEXT = (
    "Available commands:\n"
    ".btc .eth .bnb .xrp .sol .ltc .trx - send your saved address\n"
    ".addrs - list all saved addresses\n"
    ".add NAME ADDRESS - add/update an address\n"
    ".remove NAME - remove an address (e.g. .remove TON)\n"
    ".id - chat id, or reply to someone for their user id\n"
    ".purgeall - delete all tracked messages in this chat\n"
    ".purge1hr - delete tracked messages from the last 1 hour\n"
    ".purge1d - delete tracked messages from the last 1 day\n"
    "/start, /help - show this list\n"
    "(all .purge commands only reach messages seen since the bot last started.\n"
    "No .block here - the Bot API has no block method, even for business bots.)"
)

# ---------- CONFIG ----------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")   # from @BotFather
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "business_data.json")
# ----------------------------

DEFAULT_ADDRESSES = {
    "BTC": "bc1qx7j99qna5jzt39cpg9m544a6kdku900e0d633m",
    "ETH": "0xbF78D6AE5EE138eB5e2aE943eD3Ca5A9f4e0fdb7",
    "BNB": "0xbF78D6AE5EE138eB5e2aE943eD3Ca5A9f4e0fdb7",
    "XRP": "r3RkhyRSdYV3Ef4oQ3pno8mYNkiZGCWnMa",
    "SOL": "AqdGE2mN3McbxWb1R3tR9pkz2KQfQ84fzc5L7iKPVeJH",
    "LTC": "LfAgmYeBE1fBAp86s7e3xGMoqnsn6RMWX6",
    "TRX": "TBEu5zTzx9uGBdc7jJaekn4u5oX1g4WtRx",
}

# in-memory log of messages seen since startup, per chat, for purge
# { chat_id: [(message_id, business_connection_id_or_None, datetime), ...] }
seen_messages = defaultdict(list)


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_addresses(owner_key: str):
    data = load_data()
    if owner_key not in data:
        data[owner_key] = dict(DEFAULT_ADDRESSES)
        save_data(data)
    return data[owner_key]


def set_addresses(owner_key: str, addrs: dict):
    data = load_data()
    data[owner_key] = addrs
    save_data(data)


def owner_key_for(update: Update) -> str:
    """Isolates data per connected business account (or per bot-admin in a group)."""
    bcid = update.effective_message.business_connection_id
    if bcid:
        return f"biz:{bcid}"
    return f"chat:{update.effective_chat.id}"


# dot-commands that take no extra arguments (handled by exact text match)
PURGE_WINDOWS = {
    ".purge1hr": timedelta(hours=1),
    ".purge1d": timedelta(days=1),
}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg or not msg.text:
        return

    bcid = msg.business_connection_id
    chat_id = msg.chat_id
    text = msg.text.strip()

    # track for purge (only messages this bot actually saw)
    seen_messages[chat_id].append((msg.message_id, bcid, datetime.now(timezone.utc)))

    owner_key = owner_key_for(update)

    # ---- .add NAME ADDRESS ----
    m = re.match(r"^\.add\s+(\S+)\s+(\S+)$", text)
    if m:
        name, addr = m.group(1).upper(), m.group(2)
        addrs = get_addresses(owner_key)
        addrs[name] = addr
        set_addresses(owner_key, addrs)
        await edit_or_reply(context, msg, bcid, chat_id, f"Saved {name} -> use .{name.lower()}")
        return

    # ---- .remove NAME ----
    m = re.match(r"^\.remove\s+(\S+)$", text)
    if m:
        name = m.group(1).upper()
        addrs = get_addresses(owner_key)
        if name in addrs:
            del addrs[name]
            set_addresses(owner_key, addrs)
            await edit_or_reply(context, msg, bcid, chat_id, f"Removed {name}")
        else:
            await edit_or_reply(context, msg, bcid, chat_id, f"{name} not found")
        return

    # ---- .id ----
    if text == ".id":
        reply_to = msg.reply_to_message
        if reply_to and reply_to.from_user:
            info = f"User ID: {reply_to.from_user.id}\nChat ID: {chat_id}"
        else:
            info = f"Chat ID: {chat_id}"
        await edit_or_reply(context, msg, bcid, chat_id, info)
        return

    # ---- .purgeall ----
    if text == ".purgeall":
        await purge(context, chat_id, bcid, since=None)
        return

    # ---- .purge1hr / .purge1d ----
    if text in PURGE_WINDOWS:
        cutoff = datetime.now(timezone.utc) - PURGE_WINDOWS[text]
        await purge(context, chat_id, bcid, since=cutoff)
        return

    # ---- /start / /help ----
    if text in ("/start", "/help"):
        await context.bot.send_message(chat_id=chat_id, text=COMMAND_LIST_TEXT)
        return

    # ---- coin address commands: .btc .eth etc (checked last, after the
    #      fixed commands above, so e.g. ".addrs" can't collide with a coin) ----
    m = re.match(r"^\.(\w+)$", text)
    if m:
        cmd = m.group(1).upper()
        if cmd == "ADDRS":
            addrs = get_addresses(owner_key)
            lines = [f"<b>{k}</b> - <code>{v}</code>" for k, v in addrs.items()]
            await edit_or_reply(context, msg, bcid, chat_id, "\n".join(lines))
            return
        addrs = get_addresses(owner_key)
        if cmd in addrs:
            formatted = f"<b>{cmd}</b> - <code>{addrs[cmd]}</code>"
            await edit_or_reply(context, msg, bcid, chat_id, formatted)
            return


async def edit_or_reply(context, msg, bcid, chat_id, html_text):
    """Edit the owner's own message if it's a business message; otherwise reply."""
    try:
        if bcid:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg.message_id,
                text=html_text,
                parse_mode=ParseMode.HTML,
                business_connection_id=bcid,
            )
        else:
            # plain group/bot context - bot can't edit a human's message, so it replies
            await context.bot.send_message(
                chat_id=chat_id,
                text=html_text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=msg.message_id,
            )
    except Exception as e:
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"Error: {e}")
        except Exception:
            pass


async def purge(context, chat_id, bcid, since):
    ids = [
        mid for (mid, mbcid, ts) in seen_messages[chat_id]
        if mbcid == bcid and (since is None or ts >= since)
    ]
    deleted = 0
    for mid in ids:
        try:
            if bcid:
                await context.bot.delete_message(
                    chat_id=chat_id, message_id=mid, business_connection_id=bcid
                )
            else:
                await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            deleted += 1
        except Exception:
            pass
    seen_messages[chat_id] = [
        e for e in seen_messages[chat_id] if e[0] not in ids
    ]
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Purged {deleted} message(s) seen since bot started.",
        )
    except Exception:
        pass


async def post_init(app: Application):
    # /start and /help are the only slash-style commands, so they're the
    # only ones that appear in Telegram's built-in "/" command menu.
    await app.bot.set_my_commands([
        BotCommand("start", "Show all available commands"),
        BotCommand("help", "Show all available commands"),
    ])
    print(COMMAND_LIST_TEXT)


def main():
    if not BOT_TOKEN:
        raise SystemExit("Set BOT_TOKEN (from @BotFather) as an environment variable first.")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # business messages (private chats connected via Telegram Business)
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    print("Business bot running (polling)...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
