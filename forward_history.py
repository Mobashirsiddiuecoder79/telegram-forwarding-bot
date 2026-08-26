import os
import sqlite3
import asyncio
from datetime import datetime, timedelta

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.patched import Message
from telethon.errors import FloodWaitError

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")

SOURCE = -1003214652417
DESTINATION = -1003936673162

DB_FILE = "forwarding.db"

client = TelegramClient("telegram_session", API_ID, API_HASH)


def is_forwarded(message_id):
    db = sqlite3.connect(DB_FILE)

    result = db.execute(
        """
        SELECT 1
        FROM forwarded_messages
        WHERE source_chat_id = ? AND source_message_id = ?
        """,
        (SOURCE, message_id)
    ).fetchone()

    db.close()

    return result is not None


def mark_forwarded(message_id):
    db = sqlite3.connect(DB_FILE)

    db.execute(
        """
        INSERT OR IGNORE INTO forwarded_messages
        (source_chat_id, source_message_id)
        VALUES (?, ?)
        """,
        (SOURCE, message_id)
    )

    db.commit()
    db.close()


async def main():
    await client.start()

    count = 0
    skipped = 0

    print("Starting history forwarding...")
    print("FloodWait will be handled automatically.")
    print("Do NOT delete forwarding.db or telegram_session.session.\n")

    async for message in client.iter_messages(SOURCE):

        if not isinstance(message, Message):
            continue

        if is_forwarded(message.id):
            skipped += 1
            continue

        while True:
            try:
                await client.forward_messages(
                    DESTINATION,
                    message
                )

                break

            except FloodWaitError as e:
                now = datetime.now()
                resume_time = now + timedelta(seconds=e.seconds + 5)

                print("\n==============================")
                print("TELEGRAM FLOOD WAIT")
                print(f"Started waiting : {now.strftime('%Y-%m-%d %I:%M:%S %p')}")
                print(f"Waiting         : {e.seconds} seconds")
                print(f"Resume at       : {resume_time.strftime('%Y-%m-%d %I:%M:%S %p')}")
                print("==============================\n")

                await asyncio.sleep(e.seconds + 5)

                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}] "
                    "FloodWait finished. Resuming...\n"
                )

        mark_forwarded(message.id)

        count += 1

        print(
            f"[{datetime.now().strftime('%I:%M:%S %p')}] "
            f"Forwarded: {message.id} | "
            f"Total: {count}"
        )

    print("\n================================")
    print("HISTORY FORWARDING FINISHED")
    print(f"Forwarded this run: {count}")
    print(f"Already forwarded: {skipped}")
    print("================================")

    await client.disconnect()


asyncio.run(main())
