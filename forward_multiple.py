import os
import json
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

DB_FILE = "forwarding.db"

client = TelegramClient("telegram_session", API_ID, API_HASH)


def load_channels():
    with open("channels.json", "r") as file:
        data = json.load(file)

    return data["channels"]


def is_forwarded(source, message_id):
    db = sqlite3.connect(DB_FILE)

    result = db.execute(
        """
        SELECT 1
        FROM forwarded_messages
        WHERE source_chat_id = ? AND source_message_id = ?
        """,
        (source, message_id)
    ).fetchone()

    db.close()

    return result is not None


def mark_forwarded(source, message_id):
    db = sqlite3.connect(DB_FILE)

    db.execute(
        """
        INSERT OR IGNORE INTO forwarded_messages
        (source_chat_id, source_message_id)
        VALUES (?, ?)
        """,
        (source, message_id)
    )

    db.commit()
    db.close()


async def forward_channel(source, destination):
    count = 0
    skipped = 0

    print("\n========================================")
    print(f"SOURCE      : {source}")
    print(f"DESTINATION : {destination}")
    print("========================================")

    async for message in client.iter_messages(source):

        if not isinstance(message, Message):
            continue

        if is_forwarded(source, message.id):
            skipped += 1
            continue

        while True:
            try:
                await client.forward_messages(
                    destination,
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

        mark_forwarded(source, message.id)

        count += 1

        print(
            f"[{datetime.now().strftime('%I:%M:%S %p')}] "
            f"Forwarded: {message.id} | "
            f"Total: {count}"
        )

    print("\n----------------------------------------")
    print(f"Finished: {source} -> {destination}")
    print(f"Forwarded: {count}")
    print(f"Skipped:   {skipped}")
    print("----------------------------------------")


async def main():
    await client.start()

    channels = load_channels()

    print("\nStarting multi-channel forwarding...")
    print(f"Channel pairs loaded: {len(channels)}")
    print("Duplicate checking: ENABLED")
    print("FloodWait handling: ENABLED")
    print("\nDo NOT delete forwarding.db or telegram_session.session.")

    for channel in channels:
        source = channel["source"]
        destination = channel["destination"]

        await forward_channel(source, destination)

    print("\n========================================")
    print("ALL CHANNELS FINISHED")
    print("========================================")

    await client.disconnect()


asyncio.run(main())
