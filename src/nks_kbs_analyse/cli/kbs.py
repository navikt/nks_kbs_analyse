"""Underkommando for NKS KBS."""

from typing import Annotated

import httpx
import typer
from rich.prompt import Prompt

from . import console, get_auth
from .settings import settings

app = typer.Typer(name="kbs", help="Interager med 'nks_kbs'")
"""Kommandolinjeverktøy for NKS KBS"""
KBS_URL = httpx.URL(str(settings.kbs_url))
"""URL til NKS KBS endepunkter"""


@app.command()
def chat(
    timeout: Annotated[
        float, typer.Option(help="Antall sekunder å vente på svar fra Bob")
    ] = 30.0,
) -> None:
    """Chat med NKS Bob."""
    auth = get_auth(str(KBS_URL))
    client = httpx.Client(cookies=auth.get_cookie(), base_url=KBS_URL)
    try:
        chat_history: list[dict[str, str]] = []
        while True:
            req = Prompt.ask("Spørsmål til Bob", console=console)
            if not req.startswith("?follow-up"):
                json_req = {"history": chat_history, "question": req.strip()}
                with console.status("Spør Bob...", spinner="dots"):
                    resp = client.post(
                        "/api/v1/chat", json=json_req, timeout=timeout
                    ).raise_for_status()
                data = resp.json()
                answer = data["answer"]
                chat_history.append({"role": "human", "content": req.strip()})
                chat_history.append({"role": "ai", "content": answer["text"]})
                console.print(answer["text"])
                for cite in answer["citations"]:
                    console.print(
                        cite["text"], style="bold white on blue", justify="right"
                    )
                    console.print(
                        f"({cite['section']}/{cite['title']})",
                        style="bold magenta",
                        justify="right",
                    )
            else:
                with console.status("Finner forslag til oppfølgning..."):
                    resp = client.post(
                        "/api/v1/followup", json=chat_history, timeout=timeout
                    ).raise_for_status()
                console.print(resp.json())
    except KeyboardInterrupt:
        pass
