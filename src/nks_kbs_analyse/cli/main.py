"""Inngangen til kommandolinjeverktøyet."""

import typer

from .kbs import app as kbs_app
from .vdb import app as vdb_app

# Opprett CLI apper
app = typer.Typer()
# Legg til kommandogrupper til hoved applikasjonen
app.add_typer(vdb_app, name="vdb")
app.add_typer(kbs_app, name="kbs")


if __name__ == "__main__":
    app()
