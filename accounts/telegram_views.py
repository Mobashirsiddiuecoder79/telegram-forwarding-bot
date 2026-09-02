import asyncio
import os
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from dotenv import dotenv_values
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    FloodWaitError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from .models import TelegramConnection
from .forms import TelegramPhoneForm, TelegramCodeForm, Telegram2FAForm
from .services.telegram_session import (
    encrypt_session,
    decrypt_session,
)


def get_telegram_config():
    env = dotenv_values(".env")

    api_id = env.get("TELEGRAM_API_ID")
    api_hash = env.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        raise RuntimeError(
            "TELEGRAM_API_ID or TELEGRAM_API_HASH is missing."
        )

    return int(api_id), api_hash


def pending_telegram_login_expired(request):
    started_at = request.session.get(
        "telegram_login_started_at"
    )

    if not started_at:
        return True

    from django.utils import timezone

    started = timezone.datetime.fromtimestamp(
        started_at,
        tz=timezone.get_current_timezone(),
    )

    return timezone.now() - started > timedelta(minutes=10)



async def send_code(phone):
    api_id, api_hash = get_telegram_config()

    client = TelegramClient(
        StringSession(),
        api_id,
        api_hash,
    )

    await client.connect()

    try:
        sent = await client.send_code_request(phone)

        session_string = client.session.save()

        return {
            "session": session_string,
            "phone_code_hash": sent.phone_code_hash,
        }

    finally:
        await client.disconnect()


async def verify_code(
    session_string,
    phone,
    code,
    phone_code_hash,
):
    api_id, api_hash = get_telegram_config()

    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
    )

    await client.connect()

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash,
        )

        me = await client.get_me()

        return {
            "status": "connected",
            "session": client.session.save(),
            "telegram_user_id": me.id,
            "telegram_username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
        }

    except SessionPasswordNeededError:
        return {
            "status": "2fa_required",
            "session": client.session.save(),
        }

    finally:
        await client.disconnect()


async def verify_password(
    session_string,
    password,
):
    api_id, api_hash = get_telegram_config()

    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
    )

    await client.connect()

    try:
        await client.sign_in(password=password)

        me = await client.get_me()

        return {
            "status": "connected",
            "session": client.session.save(),
            "telegram_user_id": me.id,
            "telegram_username": me.username or "",
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
        }

    finally:
        await client.disconnect()


@login_required
def telegram_connection(request):
    connection, _ = TelegramConnection.objects.get_or_create(
        user=request.user
    )

    return render(
        request,
        "accounts/telegram_connection.html",
        {
            "connection": connection,
            "phone_form": TelegramPhoneForm(),
            "code_form": TelegramCodeForm(),
            "two_fa_form": Telegram2FAForm(),
            "pending_code": bool(
                request.session.get("telegram_pending_session")
            ),
            "pending_2fa": bool(
                request.session.get("telegram_2fa_required")
            ),
        },
    )


@login_required
def telegram_send_code(request):
    if request.method != "POST":
        return redirect("telegram_connection")

    phone = request.POST.get("phone", "").strip()

    if not phone:
        messages.error(request, "Please enter your Telegram phone number.")
        return redirect("telegram_connection")

    try:
        result = asyncio.run(send_code(phone))

    except FloodWaitError as exc:
        messages.error(
            request,
            f"Telegram requested a wait of {exc.seconds} seconds.",
        )
        return redirect("telegram_connection")

    except Exception as exc:
        messages.error(
            request,
            f"Telegram login could not be started: {exc}",
        )
        return redirect("telegram_connection")

    # Temporary authorization state belongs to THIS Django session.
    from django.utils import timezone

    request.session["telegram_pending_session"] = encrypt_session(
        result["session"]
    )
    request.session["telegram_pending_phone"] = phone
    request.session["telegram_login_started_at"] = timezone.now().timestamp()
    request.session["telegram_phone_code_hash"] = (
        result["phone_code_hash"]
    )
    request.session["telegram_2fa_required"] = False

    messages.success(
        request,
        "Telegram verification code sent.",
    )

    return redirect("telegram_connection")


@login_required
def telegram_resend_code(request):
    if request.method != "POST":
        return redirect("telegram_connection")

    phone = request.session.get("telegram_pending_phone")

    if not phone:
        messages.error(
            request,
            "Your Telegram login session expired. Please enter your phone number again.",
        )
        clear_pending_telegram_login(request)
        return redirect("telegram_connection")

    try:
        result = asyncio.run(send_code(phone))

    except FloodWaitError as exc:
        messages.error(
            request,
            f"Telegram requested a wait of {exc.seconds} seconds before sending another code.",
        )
        return redirect("telegram_connection")

    except Exception as exc:
        messages.error(
            request,
            f"Could not resend the Telegram verification code: {exc}",
        )
        return redirect("telegram_connection")

    from django.utils import timezone

    request.session["telegram_pending_session"] = encrypt_session(
        result["session"]
    )
    request.session["telegram_pending_phone"] = phone
    request.session["telegram_login_started_at"] = timezone.now().timestamp()
    request.session["telegram_phone_code_hash"] = result["phone_code_hash"]
    request.session["telegram_2fa_required"] = False
    request.session.modified = True

    messages.success(
        request,
        "A new Telegram verification code has been sent.",
    )

    return redirect("telegram_connection")


@login_required
def telegram_cancel(request):
    if request.method != "POST":
        return redirect("telegram_connection")

    clear_pending_telegram_login(request)

    messages.info(
        request,
        "Telegram connection was cancelled.",
    )

    return redirect("telegram_connection")


@login_required
def telegram_verify_code(request):
    if request.method != "POST":
        return redirect("telegram_connection")

    if pending_telegram_login_expired(request):
        clear_pending_telegram_login(request)

        messages.error(
            request,
            "Your Telegram verification session expired. Please request a new code.",
        )

        return redirect("telegram_connection")

    encrypted_session = request.session.get(
        "telegram_pending_session"
    )
    phone = request.session.get("telegram_pending_phone")
    phone_code_hash = request.session.get(
        "telegram_phone_code_hash"
    )
    code = request.POST.get("code", "").strip()

    if not encrypted_session or not phone or not phone_code_hash:
        messages.error(
            request,
            "Your Telegram login session expired. Please request a new code.",
        )
        return redirect("telegram_connection")

    if not code:
        messages.error(request, "Please enter the Telegram verification code.")
        return redirect("telegram_connection")

    try:
        result = asyncio.run(
            verify_code(
                decrypt_session(encrypted_session),
                phone,
                code,
                phone_code_hash,
            )
        )

    except PhoneCodeInvalidError:
        messages.error(request, "The Telegram verification code is invalid.")
        return redirect("telegram_connection")

    except PhoneCodeExpiredError:
        messages.error(request, "The Telegram verification code has expired.")
        return redirect("telegram_connection")

    except FloodWaitError as exc:
        messages.error(
            request,
            f"Telegram requested a wait of {exc.seconds} seconds.",
        )
        return redirect("telegram_connection")

    except Exception as exc:
        messages.error(
            request,
            f"Telegram verification failed: {exc}",
        )
        return redirect("telegram_connection")

    if result["status"] == "2fa_required":
        request.session["telegram_pending_session"] = encrypt_session(
            result["session"]
        )
        request.session["telegram_2fa_required"] = True

        messages.info(
            request,
            "Your Telegram account has two-step verification enabled.",
        )

        return redirect("telegram_connection")

    save_telegram_connection(request, phone, result)
    clear_pending_telegram_login(request)

    messages.success(
        request,
        "Telegram account connected successfully.",
    )

    return redirect("channel_management")


@login_required
def telegram_verify_2fa(request):
    if request.method != "POST":
        return redirect("telegram_connection")

    if pending_telegram_login_expired(request):
        clear_pending_telegram_login(request)

        messages.error(
            request,
            "Your Telegram verification session expired. Please start again.",
        )

        return redirect("telegram_connection")

    encrypted_session = request.session.get(
        "telegram_pending_session"
    )
    phone = request.session.get("telegram_pending_phone")
    password = request.POST.get("password", "")

    if not encrypted_session or not phone:
        messages.error(
            request,
            "Your Telegram login session expired. Please start again.",
        )
        return redirect("telegram_connection")

    if not password:
        messages.error(
            request,
            "Please enter your Telegram two-step verification password.",
        )
        return redirect("telegram_connection")

    try:
        result = asyncio.run(
            verify_password(
                decrypt_session(encrypted_session),
                password,
            )
        )

    except Exception as exc:
        messages.error(
            request,
            f"Telegram two-step verification failed: {exc}",
        )
        return redirect("telegram_connection")

    save_telegram_connection(request, phone, result)
    clear_pending_telegram_login(request)

    messages.success(
        request,
        "Telegram account connected successfully.",
    )

    return redirect("channel_management")


def save_telegram_connection(request, phone, result):
    connection, _ = TelegramConnection.objects.get_or_create(
        user=request.user
    )

    connection.phone_number = phone
    connection.telegram_user_id = result["telegram_user_id"]
    connection.telegram_username = result["telegram_username"]
    connection.first_name = result["first_name"]
    connection.last_name = result["last_name"]
    connection.encrypted_session = encrypt_session(
        result["session"]
    )
    connection.is_connected = True

    from django.utils import timezone

    connection.connected_at = timezone.now()
    connection.save()


def clear_pending_telegram_login(request):
    request.session.pop("telegram_pending_session", None)
    request.session.pop("telegram_pending_phone", None)
    request.session.pop("telegram_phone_code_hash", None)
    request.session.pop("telegram_2fa_required", None)


@login_required
def telegram_disconnect(request):
    if request.method != "POST":
        return redirect("telegram_connection")

    connection = TelegramConnection.objects.filter(
        user=request.user
    ).first()

    if not connection:
        clear_pending_telegram_login(request)

        messages.info(
            request,
            "No Telegram account is connected.",
        )

        return redirect("telegram_connection")

    if connection.encrypted_session:
        try:
            asyncio.run(
                disconnect_telegram_session(
                    connection.encrypted_session
                )
            )
        except Exception:
            # Even if Telegram-side logout fails, remove the local
            # credential so it cannot be reused by this application.
            pass

    connection.delete()

    clear_pending_telegram_login(request)

    messages.success(
        request,
        "Your Telegram account has been disconnected.",
    )

    return redirect("telegram_connection")


async def disconnect_telegram_session(encrypted_session):
    api_id, api_hash = get_telegram_config()

    session_string = decrypt_session(encrypted_session)

    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
    )

    await client.connect()

    try:
        if await client.is_user_authorized():
            await client.log_out()
    finally:
        await client.disconnect()

