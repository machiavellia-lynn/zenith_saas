"""
tg_login.py — one-time interactive Telegram login for the scraper session.

Run it yourself so the OTP never passes through a chat:
    python scripts/tg_login.py

It asks for your phone number, then the code Telegram sends (and the 2FA
password if the account has one). Nothing secret is printed or logged. On
success it saves the session file at TG_SESSION_PATH and checks that the account
can actually read the four BST topics.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from config import (  # noqa: E402
    TG_API_ID, TG_API_HASH, TG_SESSION_PATH, TG_GROUP_ID,
    TG_TOPIC_SMART, TG_TOPIC_BAD, TG_TOPIC_MF_PLUS, TG_TOPIC_MF_MINUS,
)

TOPICS = {
    "SM": TG_TOPIC_SMART, "BM": TG_TOPIC_BAD,
    "MF+": TG_TOPIC_MF_PLUS, "MF-": TG_TOPIC_MF_MINUS,
}


async def main() -> int:
    if not TG_API_ID or not TG_API_HASH:
        print("TG_API_ID / TG_API_HASH belum diisi di .env")
        return 2

    from telethon import TelegramClient

    os.makedirs(os.path.dirname(TG_SESSION_PATH), exist_ok=True)
    print(f"Session akan disimpan di: {TG_SESSION_PATH}.session")

    client = TelegramClient(TG_SESSION_PATH, TG_API_ID, TG_API_HASH)
    # start() prompts for phone / code / 2FA password on the terminal.
    await client.start()
    me = await client.get_me()
    print(f"Login OK sebagai: {me.first_name or ''} (id {me.id})")

    try:
        await client.get_dialogs()
        group = await client.get_entity(TG_GROUP_ID)
        print(f"Grup ditemukan: {getattr(group, 'title', TG_GROUP_ID)}")
    except Exception as e:
        print(f"GAGAL membuka grup BST ({TG_GROUP_ID}): {type(e).__name__}: {e}")
        print("Pastikan akun ini sudah join grup BST, lalu jalankan lagi.")
        await client.disconnect()
        return 3

    ok = True
    for label, topic in TOPICS.items():
        try:
            msgs = await client.get_messages(TG_GROUP_ID, limit=1, reply_to=topic)
            has = bool(msgs)
            print(f"  topik {label:<3} ({topic}): {'bisa dibaca' if has else 'KOSONG / tidak ada pesan'}")
            ok = ok and has
        except Exception as e:
            ok = False
            print(f"  topik {label:<3} ({topic}): GAGAL {type(e).__name__}: {e}")

    await client.disconnect()
    print("Selesai." if ok else "Selesai, tapi ada topik yang tidak terbaca — cek keanggotaan grup.")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
