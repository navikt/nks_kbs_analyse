"""Underkommando for NKS KBS."""

import json
from typing import Annotated

import httpx
import typer
from rich.live import Live
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
                data = {}
                with Live(console=console, auto_refresh=False, transient=True) as live:
                    with client.stream(
                        "POST", "/api/v1/stream/chat", json=json_req, timeout=timeout
                    ) as reply:
                        reply = reply.raise_for_status()
                        for line in reply.iter_lines():
                            if line.startswith("data: "):
                                _, msg = line.split(" ", maxsplit=1)
                                data = json.loads(msg)
                                live.update(data["answer"]["text"], refresh=True)
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
