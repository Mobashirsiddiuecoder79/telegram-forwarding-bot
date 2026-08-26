import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("telegram_session", api_id, api_hash)

async def main():
    await client.start()

    dialogs = await client.get_dialogs()

    for dialog in dialogs:
        if dialog.is_channel:
            print(f"{dialog.id} | {dialog.title}")

    await client.disconnect()

asyncio.run(main())
