"""
Telegram personal userbot (Telethon)

Commands (type them in ANY chat; your message gets edited/handled):
  .sol .btc .eth ...      -> edits your message into "SOL - \n\n<tap-to-copy address>"
  .addrs                  -> list all saved coin commands
  .addaddr NAME ADDRESS   -> add/update an address   (e.g. .addaddr DOGE D8abc...)
  .deladdr NAME           -> remove an address
  .block                  -> block the user (private chat, or reply to a user in a group)
  .id                     -> private chat: their id | reply: replied user's id | group: chat id
  /purgeall               -> delete ALL your messages in the current chat
  /purge1hr               -> delete your messages from the last 1 hour in the current chat
"""
import json
import os
from datetime import datetime, timedelta, timezone

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.contacts import BlockRequest
from telethon.tl.types import User

# ---------- CONFIG ----------
API_ID = int(os.getenv("TG_API_ID", "36470288"))
API_HASH = os.getenv("TG_API_HASH", "0aa5ff785388e0ae0dedd74730bccac0")
SESSION = "userbot_session"
ADDR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "addresses.json")
BLOCK_TEXT = "🚫 Blocked CRAZY ~ SM EXPERT"
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


def load_addresses():
    if not os.path.exists(ADDR_FILE):
        save_addresses(DEFAULT_ADDRESSES)
        return dict(DEFAULT_ADDRESSES)
    with open(ADDR_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_addresses(data):
    with open(ADDR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


SESSION_STRING = os.getenv(
    "TG_SESSION",
    "1BVtsOK4BuzdFuZ8B-VgNRrY7KHhJjbgybhz2vIdIuDFOrocf3X1Bt6sRGLMfPEJLHrUBkDBaq9kklkQaFdSGiVc6dAQ3DFnsrBZ4KqsqWbUgVLI_uavD3iL-n-8D2VmSQ08cOx0OCg9Gy_2hWePEaQ5BfwpgSSLtYhG560stAvQn06aOpej1jnU_uRm_zl1ynzofX9JyqwVJSHJqvXMZzHm7bAC5HSKe6IgunExDzPE2lYpSE3I3UPPXnk0xfCF3HUV64kp5yZjLJy5NZUwq7qgrjw0q0rCRjSiFM9GDnfrNHGOaV8RS6fXDxPjfDqQZv5JG70aA2KYTfTEDAqKmNwCHX4smaPA=",
)
client = TelegramClient(
    StringSession(SESSION_STRING) if SESSION_STRING else SESSION, API_ID, API_HASH
)


async def delete_in_chunks(chat, ids):
    for i in range(0, len(ids), 100):
        await client.delete_messages(chat, ids[i:i + 100], revoke=True)


# ---------- ADDRESS COMMANDS ----------
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.addrs$"))
async def list_addrs(event):
    addrs = load_addresses()
    lines = [f"`.{k.lower()}`  →  {k}" for k in addrs]
    await event.edit("**Saved commands:**\n\n" + "\n".join(lines))


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.addaddr\s+(\S+)\s+(\S+)$"))
async def add_addr(event):
    name = event.pattern_match.group(1).upper()
    addr = event.pattern_match.group(2)
    addrs = load_addresses()
    addrs[name] = addr
    save_addresses(addrs)
    await event.edit(f"✅ Saved **{name}** → use `.{name.lower()}`")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.deladdr\s+(\S+)$"))
async def del_addr(event):
    name = event.pattern_match.group(1).upper()
    addrs = load_addresses()
    if name in addrs:
        del addrs[name]
        save_addresses(addrs)
        await event.edit(f"🗑 Removed **{name}**")
    else:
        await event.edit(f"❌ {name} not found")


@client.on(events.NewMessage(outgoing=True, pattern=r"^\.(\w+)$"))
async def send_addr(event):
    cmd = event.pattern_match.group(1).upper()
    addrs = load_addresses()
    if cmd in addrs:
        # backticks = monospace, tap to copy
        await event.edit(f"{cmd} -\n\n`{addrs[cmd]}`")


# ---------- BLOCK ----------
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.block$"))
async def block_user(event):
    target = None
    if event.is_reply:
        reply = await event.get_reply_message()
        target = await reply.get_sender()
    elif event.is_private:
        target = await event.get_chat()

    if not isinstance(target, User):
        await event.edit("❌ Use in a private chat, or reply to a user's message.")
        return
    try:
        await client(BlockRequest(id=target.id))
        name = (target.first_name or "") + (f" {target.last_name}" if target.last_name else "")
        name = name.strip() or (f"@{target.username}" if target.username else str(target.id))
        await event.edit(f"🚫 Blocked {name}")
    except Exception as e:
        await event.edit(f"❌ Failed: {e}")


# ---------- ID ----------
@client.on(events.NewMessage(outgoing=True, pattern=r"^\.id$"))
async def get_id(event):
    chat = await event.get_chat()
    if event.is_reply:
        reply = await event.get_reply_message()
        sender = await reply.get_sender()
        text = f"👤 **User ID:** `{sender.id}`"
        if getattr(sender, "username", None):
            text += f"\n🔗 **Username:** @{sender.username}"
        text += f"\n💬 **Chat ID:** `{event.chat_id}`"
    elif event.is_private:
        text = f"👤 **User ID:** `{chat.id}`"
        if getattr(chat, "username", None):
            text += f"\n🔗 **Username:** @{chat.username}"
    else:
        text = f"💬 **Chat ID:** `{event.chat_id}`"
    await event.edit(text)


# ---------- PURGE ----------
@client.on(events.NewMessage(outgoing=True, pattern=r"^/purgeall$"))
async def purge_all(event):
    chat = event.chat_id
    ids = [event.id]
    async for m in client.iter_messages(chat, from_user="me"):
        ids.append(m.id)
    await delete_in_chunks(chat, list(set(ids)))


@client.on(events.NewMessage(outgoing=True, pattern=r"^/purge1hr$"))
async def purge_1hr(event):
    chat = event.chat_id
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    ids = [event.id]
    async for m in client.iter_messages(chat, from_user="me"):
        if m.date < cutoff:
            break
        ids.append(m.id)
    await delete_in_chunks(chat, list(set(ids)))


if __name__ == "__main__":
    if not API_ID or not API_HASH:
        raise SystemExit("Set TG_API_ID and TG_API_HASH first (see README.md)")
    load_addresses()
    print(
        f"DEBUG: TG_API_ID set={bool(API_ID)}, TG_API_HASH set={bool(API_HASH)}, "
        f"TG_SESSION length={len(SESSION_STRING)} (should be ~350+)"
    )

    async def main():
        await client.connect()
        if not await client.is_user_authorized():
            raise SystemExit(
                "NOT LOGGED IN: TG_SESSION is missing, empty or invalid. "
                "Generate a new one with gen_session.py and set it in Railway variables."
            )
        me = await client.get_me()
        print(f"Userbot running as {me.first_name} (id {me.id})")
        await client.run_until_disconnected()

    client.loop.run_until_complete(main())
