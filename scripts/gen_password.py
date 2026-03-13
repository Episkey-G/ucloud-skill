#!/usr/bin/env python3
"""Generate a random password meeting UCloud requirements and output base64-encoded.

UCloud password requirements:
- 8-30 characters (we use 12 for good security)
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 digit
- At least 1 special character from !@#$%^&*
- No spaces or ambiguous characters (0/O, l/1)

Usage:
    python3 gen_password.py
    python3 gen_password.py --length 16

Output:
    Password: Kx9#mTp4$vR2
    Base64: S3g5I21UcDQkdlIy
"""

import base64
import secrets
import string
import sys


# Character sets (excluding ambiguous: 0, O, l, 1)
UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"       # no O
LOWER = "abcdefghjkmnpqrstuvwxyz"         # no l
DIGITS = "23456789"                        # no 0, 1
SPECIAL = "!@#$%^&*"

ALL_CHARS = UPPER + LOWER + DIGITS + SPECIAL


def generate_password(length: int = 12) -> str:
    """Generate a random password meeting UCloud requirements."""
    while True:
        # Guarantee at least one of each required type
        password = [
            secrets.choice(UPPER),
            secrets.choice(LOWER),
            secrets.choice(DIGITS),
            secrets.choice(SPECIAL),
        ]

        # Fill remaining with random chars from all sets
        for _ in range(length - 4):
            password.append(secrets.choice(ALL_CHARS))

        # Shuffle to avoid predictable positions
        secrets.SystemRandom().shuffle(password)
        result = "".join(password)

        # Double-check requirements (should always pass, but be safe)
        has_upper = any(c in UPPER for c in result)
        has_lower = any(c in LOWER for c in result)
        has_digit = any(c in DIGITS for c in result)
        has_special = any(c in SPECIAL for c in result)

        if has_upper and has_lower and has_digit and has_special:
            return result


def main():
    length = 12
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--length" and i + 1 <= len(sys.argv) - 1:
            length = int(sys.argv[i + 1])

    password = generate_password(length)
    encoded = base64.b64encode(password.encode()).decode()

    print(f"Password: {password}")
    print(f"Base64: {encoded}")


if __name__ == "__main__":
    main()
