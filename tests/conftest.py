"""Test-suite guards.

Force the suite offline-deterministic regardless of a developer's local `.env`: the
red-team GENERATOR runs on the deterministic seed (never a live/paid Gemma call), and
OTel spans don't spam the console. Tests that specifically exercise the Gemma toggle
(`test_gemma.py`) set `USE_REAL["gemma"]` explicitly per test.
"""
from __future__ import annotations

import sentinel.config as config

config.TRACE_CONSOLE = False
config.USE_REAL["gemma"] = False
