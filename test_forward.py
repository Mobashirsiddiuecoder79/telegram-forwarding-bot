import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.patched import Message

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

SOURCE = -1003214652417
DESTINATION = -1003936673162

client = TelegramClient("telegram_session", api_id, api_hash)

async def main():
    await client.start()

    async for message in client.iter_messages(SOURCE):
        if isinstance(message, Message):
            await client.forward_messages(DESTINATION, message)
            print(f"Forwarded message ID: {message.id}")
            break
    else:
        print("No forwardable messages found.")

    await client.disconnect()

asyncio.run(main())
