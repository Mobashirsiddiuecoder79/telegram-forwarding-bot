import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv


load_dotenv()


def _get_cipher():
    key = os.getenv("TELEGRAM_SESSION_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "TELEGRAM_SESSION_ENCRYPTION_KEY is not configured."
        )

    return Fernet(key.encode())


def encrypt_session(session_string):
    if not session_string:
        raise ValueError("Session string cannot be empty.")

    cipher = _get_cipher()

    return cipher.encrypt(
        session_string.encode()
    ).decode()


def decrypt_session(encrypted_session):
    if not encrypted_session:
        raise ValueError("Encrypted session cannot be empty.")

    cipher = _get_cipher()

    return cipher.decrypt(
        encrypted_session.encode()
    ).decode()
