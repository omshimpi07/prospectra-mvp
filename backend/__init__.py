"""Prospectra backend package."""

import asyncio
import sys

# On Windows, psycopg 3 async requires a SelectorEventLoop rather than ProactorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
