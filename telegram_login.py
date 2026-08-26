import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

api_id = int(os.getenv("TELEGRAM_API_ID"))
api_hash = os.getenv("TELEGRAM_API_HASH")

client = TelegramClient("telegram_session", api_id, api_hash)

async def main():
    me = await client.get_me()
    print(f"Logged in as: {me.first_name}")
    print(f"Username: @{me.username}" if me.username else "Username: None")

with client:
    client.start()
    client.loop.run_until_complete(main())
