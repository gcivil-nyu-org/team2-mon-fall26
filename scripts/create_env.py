"""Create local demo credentials without overwriting an existing .env."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parent.parent
target = root / ".env"
if target.exists():
    print(".env already exists; kept existing configuration.")
else:
    content = (root / ".env.example").read_text()
    for placeholder in (
        "replace-with-a-random-secret",
        "replace-with-a-random-password",
        "replace-with-a-different-random-password",
    ):
        content = content.replace(placeholder, secrets.token_hex(32))
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(content)
    print("Created .env for a local MySQL demo. Credentials were not printed.")
