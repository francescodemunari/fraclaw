"""
handler.py — Backward compatibility shim.

All Telegram handler logic has moved to src.gateway.telegram.
This file exists only so existing imports don't break.
"""

from src.gateway.telegram import create_telegram_app as create_application

__all__ = ["create_application"]
