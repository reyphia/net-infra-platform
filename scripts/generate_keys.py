#!/usr/bin/env python3
"""Generate a SECRET_KEY and ENCRYPTION_KEY for .env.

Usage: python3 scripts/generate_keys.py
"""
import secrets

from cryptography.fernet import Fernet

print(f"SECRET_KEY={secrets.token_hex(32)}")
print(f"ENCRYPTION_KEY={Fernet.generate_key().decode()}")
