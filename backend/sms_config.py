import os


def welcome_sms_enabled() -> bool:
    return os.environ.get("ENABLE_WELCOME_SMS", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
