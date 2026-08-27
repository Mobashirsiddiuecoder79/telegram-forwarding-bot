from telethon import TelegramClient
from telethon.sessions import StringSession

from accounts.models import TelegramConnection
from accounts.services.telegram_session import decrypt_session


def get_telegram_client(user):
    """
    Return a Telethon client using ONLY the Telegram session
    belonging to the supplied Django user.
    """

    connection = TelegramConnection.objects.filter(
        user=user,
        is_connected=True,
    ).first()

    if not connection:
        raise ValueError(
            "This user does not have a connected Telegram account."
        )

    if not connection.encrypted_session:
        raise ValueError(
            "This user's Telegram session is missing."
        )

    from dotenv import dotenv_values

    env = dotenv_values(".env")

    api_id = env.get("TELEGRAM_API_ID")
    api_hash = env.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError(
            "Telegram API credentials are not configured."
        )

    session_string = decrypt_session(
        connection.encrypted_session
    )

    return TelegramClient(
        StringSession(session_string),
        int(api_id),
        api_hash,
    )
