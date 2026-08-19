import os
from dotenv import load_dotenv

load_dotenv()

PLIVO_AUTH_ID = os.environ.get("PLIVO_AUTH_ID", "")
PLIVO_AUTH_TOKEN = os.environ.get("PLIVO_AUTH_TOKEN", "")
PLIVO_FROM_NUMBER = os.environ.get("PLIVO_FROM_NUMBER", "")
TARGET_PHONE_NUMBER = os.environ.get("TARGET_PHONE_NUMBER", "")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
OTP_CODE = os.environ.get("OTP_CODE", "0000")
ASSOCIATE_NUMBER = os.environ.get("ASSOCIATE_NUMBER", "")

# Publicly hosted MP3 played for the "Level 2 -> press 1" branch.
# SoundHelix hosts long-lived public-domain sample tracks specifically for
# use as test/demo audio -- swap for your own hosted file if you prefer.
AUDIO_MESSAGE_URL = os.environ.get(
    "AUDIO_MESSAGE_URL",
    "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
)

REQUIRED_VARS = {
    "PLIVO_AUTH_ID": PLIVO_AUTH_ID,
    "PLIVO_AUTH_TOKEN": PLIVO_AUTH_TOKEN,
    "PLIVO_FROM_NUMBER": PLIVO_FROM_NUMBER,
    "TARGET_PHONE_NUMBER": TARGET_PHONE_NUMBER,
    "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
}


def check_config():
    """Raise a clear error early if required env vars are missing, instead of
    failing deep inside a Plivo webhook call where it's hard to debug."""
    missing = [k for k, v in REQUIRED_VARS.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing required .env values: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill these in."
        )
