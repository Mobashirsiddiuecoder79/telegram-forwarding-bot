Telegram Forwarding Bot

A Python-based Telegram message forwarding system built with Telethon.

This project forwards messages from Telegram source channels to configured destination channels while maintaining local duplicate tracking and handling Telegram FloodWait limits.


⸻

📌 Features

* Multiple source → destination channel pairs
* Multiple sources can use the same destination
* Forward text messages
* Forward images and videos
* Forward documents and supported media
* Preserve captions and links when Telegram permits forwarding
* Skip Telegram service messages
* Duplicate protection using SQLite
* Resume processing after interruption
* Automatic Telegram FloodWait handling
* FloodWait resume timestamps
* Telegram user-account authentication using Telethon
* Local credential and session protection


⸻

🏗️ Architecture

                  Telegram
                     │
                     ▼
              Source Channels
                     │
                     ▼
                 Telethon
                     │
                     ▼
            Forwarding Program
                     │
                     ▼
           Destination Channels

Multiple Source → Destination Mapping

Source A ──────────────► Destination A
Source B ──────────────► Destination B
Source C ──────────────► Destination A
Source D ──────────────► Destination C

Multiple source channels can therefore forward to the same destination channel.


⸻

📁 Project Structure

telegram-forwarding-bot/
│
├── bot.py
├── channel
├── channels.json
│
├── forward_history.py
├── forward_history_backup.py
├── forward_multiple.py
│
├── list_channels.py
├── telegram_login.py
├── test_forward.py
│
├── requirements.txt
├── README.md
│
├── .env                     # 🔒 Local only
├── forwarding.db            # 🔒 Local only
├── telegram_session.session # 🔒 Local only
└── venv/                    # 🔒 Local only


Important Local Files

The following files contain local or sensitive information and should never be pushed to GitHub:

.env
*.session
*.session-journal
*.db
venv/
__pycache__/
*.pyc


⸻

⚙️ Requirements

Before running the project, make sure you have:

* Python 3.12+
* A Telegram account
* Telegram API ID
* Telegram API Hash
* Access to the source channels
* Permission to post in destination channels
* An active internet connection


⸻

🚀 Installation

1. Clone the Repository

git clone https://github.com/Mobashirsiddiuecoder79/telegram-forwarding-bot.git
cd telegram-forwarding-bot


2. Create Virtual Environment

python3.12 -m venv venv


3. Activate Virtual Environment

macOS / Linux

source venv/bin/activate

Windows

venv\Scripts\activate


4. Install Dependencies

pip install -r requirements.txt


⸻

🔐 Environment Configuration

Create a .env file in the project root:

BOT_TOKEN=YOUR_BOT_TOKEN
TELEGRAM_API_ID=YOUR_API_ID
TELEGRAM_API_HASH=YOUR_API_HASH

For the Django web application, configure the required environment variables in .env.

Example:

DJANGO_SECRET_KEY=YOUR_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com
EMAIL_HOST_PASSWORD=YOUR_EMAIL_PASSWORD
RAZORPAY_KEY_ID=YOUR_RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET=YOUR_RAZORPAY_WEBHOOK_SECRET
TELEGRAM_SESSION_ENCRYPTION_KEY=YOUR_ENCRYPTION_KEY


⚠️ Security

Never publish:

BOT_TOKEN
TELEGRAM_API_ID
TELEGRAM_API_HASH
DJANGO_SECRET_KEY
EMAIL_HOST_PASSWORD
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET
TELEGRAM_SESSION_ENCRYPTION_KEY

The .env file is excluded from Git using .gitignore.


⸻

🤖 Telegram Bot Setup

If using the Telegram Bot API:

1. Open Telegram.
2. Search for @BotFather.
3. Run:

/newbot

4. Create your bot.
5. Copy the generated bot token.
6. Store it only inside .env.

The main forwarding system uses Telethon with a Telegram user account because a normal bot cannot read messages from a source channel unless it has the required access.


⸻

🔑 Telegram API Setup

Telethon requires an API ID and API Hash.

Open:

https://my.telegram.org

Then:

1. Log in with your Telegram account.
2. Open API development tools.
3. Create an application.
4. Obtain:

api_id
api_hash

Store them in .env.

Never publish your API Hash.


⸻

👤 Telegram Account Login

Run:

python telegram_login.py

Telethon will ask for your Telegram phone number and login verification code.

After successful authentication, a local session file will be created:

telegram_session.session

⚠️ Never upload the session file to GitHub.

The session file can contain authentication information for your Telegram account.


⸻

🔎 Find Telegram Channel IDs

Run:

python list_channels.py

The program will display channels accessible to your Telegram account.

Example:

-1001234567890 | Source Channel
-1009876543210 | Destination Channel

Use these numeric IDs in channels.json.


⸻

🔀 Multiple Channel Mapping

The system supports multiple source and destination combinations.

Multiple source channels can therefore forward messages to the same destination channel.

Example:

{
    "channels": [
        {
            "source": -1001111111111,
            "destination": -1002222222222
        },
        {
            "source": -1003333333333,
            "destination": -1004444444444
        },
        {
            "source": -1005555555555,
            "destination": -1002222222222
        }
    ]
}

This configuration means:

Source 1 ─────► Destination 1
Source 2 ─────► Destination 2
Source 3 ─────► Destination 1

The same destination can receive messages from multiple source channels.


Same Destination

Multiple sources can use the same destination:

{
    "channels": [
        {
            "source": -1001111111111,
            "destination": -1009999999999
        },
        {
            "source": -1002222222222,
            "destination": -1009999999999
        }
    ]
}


⸻

📤 History Forwarding

The forwarding program processes existing messages from configured source channels.

Run:

python forward_multiple.py

The program:

1. Reads channel mappings from channels.json.
2. Connects using the Telethon session.
3. Reads source channel messages.
4. Checks the duplicate database.
5. Forwards messages that have not been processed.
6. Records successfully forwarded messages.
7. Handles Telegram FloodWait automatically.


⸻

🧾 Duplicate Protection

The project uses SQLite:

forwarding.db

Each successfully processed message is identified using:

source_chat_id
source_message_id

Before forwarding:

Message
   │
   ▼
Already in database?
   │
 ┌─┴───────────┐
 │             │
 YES           NO
 │             │
 ▼             ▼
SKIP        FORWARD
               │
               ▼
        Save message ID


Benefits

* Prevents intentional duplicate forwarding
* Safe to restart after interruption
* Previously processed messages remain recorded
* Different source channels are tracked independently

Do not delete forwarding.db if you want to preserve duplicate history.


⸻

📦 Supported Message Types

The forwarding system can handle supported Telegram message types including:

* Text
* Images
* Videos
* Documents
* Audio
* Voice messages
* Animations
* Captions
* Links

Actual availability depends on Telegram permissions and channel restrictions.


⸻

⏳ FloodWait Handling

Telegram may temporarily limit forwarding requests.

The program catches:

FloodWaitError

and waits automatically.

Example:

==============================
TELEGRAM FLOOD WAIT
Started waiting : 2026-08-21 11:46:20 AM
Waiting         : 2467 seconds
Resume at       : 2026-08-21 12:27:32 PM
==============================

After the required waiting period, the program resumes automatically.


Why FloodWait Happens

Telegram may impose rate limits when many messages are forwarded within a short period.

This is especially important when processing large channel histories.

Do not repeatedly restart the program during a FloodWait period.


⸻

🛡️ Protected Telegram Content

Some Telegram channels have protected content enabled.

In this case, Telegram may reject forwarding with:

ChatForwardsRestrictedError

Example:

You can't forward messages from a protected chat

The project does not bypass Telegram's protected-content restrictions.


⸻

🌐 Internet Requirement

An active internet connection is required while the forwarding program is running.

The computer running the program must remain:

* Powered on
* Connected to the internet
* Logged into the Telegram session

A VPN can be used if required by the network.

Changing VPN servers repeatedly may cause connection instability.


⸻

🔒 Security

Never Commit These Files

.env
*.session
*.session-journal
*.db
venv/
__pycache__/
*.pyc


Never Publish These Credentials

Telegram Bot Token
Telegram API Hash
Telegram login codes
Telegram session files
Django secret key
Email passwords
Razorpay secret keys
Razorpay webhook secrets
Session encryption keys
Personal Telegram credentials

The repository .gitignore is configured to protect these files.


⸻

🌐 Django Web Application

The project also contains a Django-based web application for managing:

* User registration
* User login
* User profiles
* Password changes
* Password reset
* Telegram account connection
* Telegram verification
* Channel management
* Forwarding configuration
* Subscription plans
* Licensing
* Razorpay payments

The Django application uses environment variables for sensitive configuration.


⸻

👤 User Registration

The registration system supports:

* Username
* Full name
* Email address
* Phone number
* Date of birth
* Password
* Password confirmation

Username validation prevents duplicate usernames.

If a username already exists, the registration form displays:

Username already exists. Please choose another username.

Email addresses are also checked against existing users.

If an email address is already registered, the registration form displays an appropriate validation message.

User profile information is created or updated together with the Django user account.


⸻

💳 Payments

The Django application can use Razorpay for subscription payments.

Payment credentials must be stored in .env and must never be committed to GitHub.

Never publish:

RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET

Only the public Razorpay key required by the frontend should be exposed to the browser.

Secret keys and webhook secrets must remain server-side.


⸻

⚙️ Django Development Configuration

For local development using:

http://127.0.0.1:8000/

the application can use:

DJANGO_DEBUG=True

and:

DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

Local development should not blindly enable production HTTPS settings.

For example, these settings should remain appropriate for the local HTTP development environment:

SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False

Do not enable HTTPS-only settings for a local HTTP development server unless the local server is actually configured to serve HTTPS.


⸻

🔐 Production Security

For production deployment:

* Set DEBUG=False
* Configure production ALLOWED_HOSTS
* Serve the application through HTTPS
* Configure secure session cookies
* Configure secure CSRF cookies
* Configure HSTS after HTTPS is correctly working
* Keep all credentials outside Git
* Use a production WSGI or ASGI server
* Use a production database where appropriate
* Keep Telegram session files private
* Keep payment credentials private

These settings should be configured according to the actual production deployment architecture.

Do not blindly enable HTTPS-related settings for a local HTTP development server.

For example, Django security settings such as:

SECURE_SSL_REDIRECT
SESSION_COOKIE_SECURE
CSRF_COOKIE_SECURE
SECURE_HSTS_SECONDS

should be enabled and configured according to the actual HTTPS and reverse-proxy architecture.

If the application is behind a reverse proxy or load balancer, configure the relevant proxy headers and Django settings carefully.


⸻

🧪 Django System Checks

Before deployment, run:

python manage.py check

For additional deployment security checks, run:

python manage.py check --deploy

The deployment check may report warnings related to:

* DEBUG
* HTTPS redirects
* Secure cookies
* HSTS
* Other Django security settings

These warnings should be evaluated according to the actual production architecture.

A warning does not mean that production HTTPS settings should be enabled on a local HTTP development server.


⸻

🧪 Testing

Before processing a large channel history, test with a small number of messages.

Example test:

python test_forward.py

Verify that the message appears correctly in the destination channel before starting a large history migration.

For Django registration testing, verify:

* New users can register successfully.
* Existing usernames are rejected.
* Existing email addresses are rejected.
* Invalid dates of birth are rejected.
* Password validation works correctly.
* User profiles are created correctly.


⸻

💾 Local Backup

A known-good forwarding implementation is kept locally:

forward_history_backup.py

This file can be used as a fallback if future modifications cause problems.

The backup is local and does not need to be published.


⸻

🛠️ Troubleshooting

Telethon Not Found

If you see:

ModuleNotFoundError: No module named 'telethon'

activate the virtual environment:

source venv/bin/activate

Then install dependencies:

pip install -r requirements.txt


⸻

FloodWaitError

If you see:

FloodWaitError

the program should wait automatically.

Do not repeatedly restart the program during the waiting period.


⸻

Protected Chat Error

If you see:

ChatForwardsRestrictedError

the source channel has protected content or forwarding is otherwise restricted.

The project does not bypass this restriction.


⸻

Connection Error

If Telethon reports:

ConnectionError

check:

* Internet connection
* VPN connection
* Telegram availability
* Network stability


⸻

Django Registration Error

If registration stays on the registration page, check the form validation errors displayed below the relevant fields.

Common causes include:

* Username already exists
* Email address already exists
* Invalid date of birth
* Password validation failure
* Password confirmation mismatch
* Missing required fields

The registration form displays validation errors without creating the user when validation fails.


⸻

Django HTTPS Redirect During Local Development

If:

http://127.0.0.1:8000/

is unexpectedly redirected to HTTPS, verify:

DJANGO_DEBUG
DJANGO_ALLOWED_HOSTS
SECURE_SSL_REDIRECT
SESSION_COOKIE_SECURE
CSRF_COOKIE_SECURE

For local HTTP development, HTTPS redirect should not be enabled unless HTTPS has actually been configured.

Test the local server with:

curl -I http://127.0.0.1:8000/

A normal local HTTP response should not contain an unexpected HTTPS Location header.


⸻

📋 Git Security Checklist

Before pushing the project to GitHub:

1. Check repository status:

git status

2. Confirm .env is not tracked:

git ls-files .env

3. Check .gitignore:

grep -n "^\.env" .gitignore

4. Search the tracked repository for sensitive credentials:

git grep -n -I -E 'RAZORPAY_KEY_SECRET|RAZORPAY_WEBHOOK_SECRET|TELEGRAM_API_HASH|TELEGRAM_SESSION_ENCRYPTION_KEY|DJANGO_SECRET_KEY|EMAIL_HOST_PASSWORD'

5. Run Django checks:

python manage.py check

6. Review changes:

git diff

7. Stage only the intended files:

git add .

8. Review staged changes:

git diff --cached

9. Commit the changes:

git commit -m "Update registration validation and security configuration"

10. Push to GitHub:

git push origin main


⸻

📜 Disclaimer

Use this project only with Telegram channels and content that you are authorized to access and redistribute.

Make sure your use complies with:

* Telegram's Terms of Service
* Applicable copyright laws
* Content ownership and redistribution rights

This project does not attempt to bypass Telegram's protected-content restrictions.


⸻

📄 License

For personal and educational use.