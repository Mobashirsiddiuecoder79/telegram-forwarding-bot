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

git clone https://github.com/YOUR_USERNAME/telegram-forwarding-bot.git
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

⚠️ Security

Never publish:

BOT_TOKEN
TELEGRAM_API_ID
TELEGRAM_API_HASH

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

🔀 Channel Configuration

Channel mappings are stored in:

channels.json

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

⸻

🛡️ Protected Telegram Content

Some Telegram channels have protected content enabled.

In this case, Telegram may reject forwarding with:

ChatForwardsRestrictedError

Example:

You can't forward messages from a protected chat

The project does not bypass Telegram’s protected-content restrictions.

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
Personal Telegram credentials

The repository .gitignore is configured to protect these files.

⸻

🧪 Testing

Before processing a large channel history, test with a small number of messages.

Example test:

python test_forward.py

Verify that the message appears correctly in the destination channel before starting a large history migration.

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

The program does not bypass this restriction.

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

📜 Disclaimer

Use this project only with Telegram channels and content that you are authorized to access and redistribute.

Make sure your use complies with:

* Telegram’s Terms of Service
* Applicable copyright laws
* Content ownership and redistribution rights

This project does not attempt to bypass Telegram’s protected-content restrictions.

⸻

📄 License

For personal and educational use.