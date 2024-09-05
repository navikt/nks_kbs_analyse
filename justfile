# Fiks feil og formater kode med ruff
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Sjekk at alt ser bra ut med pre-commit
lint:
    uv run pre-commit run --all-files --color always
