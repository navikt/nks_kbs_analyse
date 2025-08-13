"""Underkommando for NAVNO VDB."""

from typing import Annotated, Any

import httpx
import typer

from . import console, get_auth
from .settings import settings

app = typer.Typer(name="navno_vdb", help="Interager med 'navno-vdb'")
"""Inngang for kommandolinjeverktøy for NAVNO VDB"""
VDB_URL = httpx.URL(str(settings.navno_vdb_url))
"""URL til NAVNO VDB endepunkter"""


@app.command()
def clear(
    dry_run: Annotated[
        bool, typer.Option(help="Prøv kommando uten å gjøre faktiske endringer")
    ] = True,
) -> None:
    """Tøm vektordatabasen for innhold."""
    if not dry_run:
        _ = typer.confirm(
            "Er du sikker på at du vil tømme vektordatabasen?",
            abort=True,
        )
    auth = get_auth(str(VDB_URL))
    params = {"dry_run": dry_run}
    __ = httpx.delete(
        VDB_URL.copy_with(path="/admin/clear"), cookies=auth.get_cookie(), params=params
    ).raise_for_status()
    if not dry_run:
        console.print("[bold red]Tømte vektordatabasen!")
    else:
        console.print("[bold yellow]Velykket test")


@app.command()
def reindex(
    dry_run: Annotated[
        bool, typer.Option(help="Prøv kommando uten å gjøre faktiske endringer")
    ] = True,
    timeout: Annotated[
        float,
        typer.Option(help="Hvor lenge, i sekunder, skal man vente på 'navno_vdb'"),
    ] = 300.0,
) -> None:
    """Indekser vektordatabasen fra navno."""
    import json

    from rich.progress import Progress

    auth = get_auth(str(VDB_URL))
    params = {"dry_run": dry_run}
    if not dry_run:
        _ = typer.confirm(
            "Er du sikker du vil indeksere vektordatabasen?", default=True, abort=True
        )
    with httpx.stream(
        "PUT",
        VDB_URL.copy_with(path="/admin/reindex"),
        params=params,
        cookies=auth.get_cookie(),
        timeout=timeout,
    ) as response:
        response = response.raise_for_status()
        with Progress(console=console) as progress:
            idx_task = progress.add_task("Indekserer vektordatabase")
            for content in response.iter_lines():
                if content.startswith("data:"):
                    data: dict[str, Any] = json.loads(
                        content.split(" ", maxsplit=1)[-1]
                    )
                    if "finished" in data:
                        progress.update(
                            idx_task,
                            total=float(data["total"]),
                            completed=data["finished"],
                        )
                    else:
                        console.print("[green bold]Fullførte indeksering")
                        console.print(data)
