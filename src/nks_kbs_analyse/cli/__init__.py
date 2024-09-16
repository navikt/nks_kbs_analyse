"""Kommandolinjeverktøy for å jobbe med NKS VDB og NKS KBS."""

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

    from pydantic_core import Url

    return BrowserSessionAuthentication(
        Url(url), browser=cast(BrowserType, os.getenv("BROWSER"))
    )
