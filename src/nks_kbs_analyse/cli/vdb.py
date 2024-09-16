"""Underkommando for NKS VDB."""

from typing import Annotated, Any

import httpx
import typer

from . import console, get_auth
from .settings import settings

app = typer.Typer(name="vdb", help="Interager med 'nks-vdb'")
"""Inngang for kommandolinjeverktøy for NKS VDB"""
VDB_URL = httpx.URL(str(settings.vdb_url))
"""URL til NKS VDB endepunkter"""


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Søke teksten")],
    num_results: Annotated[
        int, typer.Option(min=1, max=30, help="Antall resultater")
    ] = 5,
    fts_weight: Annotated[
        float, typer.Option(min=0.0, help="Vekting av ordsøket")
    ] = 1.0,
    semantic_weight: Annotated[
        float, typer.Option(min=0.0, help="Vekting av det semantiskesøket")
    ] = 1.0,
) -> None:
    """Søk etter dokumenter i vektordatabasen."""
    from rich.table import Table

    auth = get_auth(str(VDB_URL))
    params = {
        "query": query,
        "num_results": str(num_results),
        "fts_weight": str(fts_weight),
        "semantic_weight": str(semantic_weight),
    }
    response = httpx.get(
        VDB_URL.copy_with(path="/api/v1/search"),
        params=params,
        cookies=auth.get_cookie(),
    ).raise_for_status()
    data = response.json()
    doc_table = Table(title=f"Fant følgende dokumenter for '{query}'")
    doc_table.add_column("Tittel")
    doc_table.add_column("Seksjon")
    doc_table.add_column("Fane")
    doc_table.add_column("Score")
    doc_table.add_column("Semantisklikhet")
    for doc in data:
        metadata = doc["metadata"]
        doc_table.add_row(
            metadata["Title"],
            metadata["Section"],
            metadata["Tab"],
            str(doc["score"]),
            str(doc["semantic_similarity"]),
        )
    console.print(doc_table)


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
        float, typer.Option(help="Hvor lenge, i sekunder, skal man vente på 'nks_vdb'")
    ] = 300.0,
) -> None:
    """Indekser vektordatabasen fra BigQuery."""
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
                data: dict[str, Any] = json.loads(content)
                if "finished" in data:
                    progress.update(
                        idx_task, total=float(data["total"]), completed=data["finished"]
                    )
                else:
                    console.print("[green bold]Fullførte indeksering")
                    console.print(
                        f"\tSiste endring i vektordatabase: {data['last_modified']}"
                    )
                    console.print(
                        f"\tAntall nye kunnskapsartikler: {data['knowledge_articles']}"
                    )
                    console.print(
                        f"\tAntall oppdaterte rader: {data['split_fragments']}"
                    )
                    console.print(
                        f"\tAntall kunnskapsartikler slettet: {data['knowledge_articles_deactivated']}"
                    )
