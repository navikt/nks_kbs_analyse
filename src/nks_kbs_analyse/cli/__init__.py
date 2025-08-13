"""Kommandolinjeverktøy for å jobbe med NAVNO VDB, NKS VDB og NKS KBS."""

from functools import cache
from typing import cast

from rich.console import Console

from nks_kbs_analyse.auth import BrowserSessionAuthentication, BrowserType

console = Console()
"""Fasiliteter for å printe med Rich"""


@cache
def get_auth(url: str) -> BrowserSessionAuthentication:
    """Hjelpemetode for å hente autentiseringsobjekt."""
    import os

    from pydantic import HttpUrl

    return BrowserSessionAuthentication(
        HttpUrl(url),
        browser=cast(BrowserType, os.getenv("BROWSER")),
        profile_path=os.getenv("PROFILE_PATH"),
    )
