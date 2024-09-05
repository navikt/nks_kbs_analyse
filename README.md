# Analyse verktøy for å jobbe med NKS Bob

Dette prosjektet inneholder verktøy for å jobbe med NKS Bob
([`nks_vdb`](https://github.com/navikt/nks_vdb) og
[`nks_kbs`](https://github.com/navikt/nks_kbs)).

## Utvikling

Prosjektet bruker [`uv`](https://docs.astral.sh/uv/) og man kan installere
prosjektet, og avhengigheter, med:

```bash
uv sync --frozen
```

> [!IMPORTANT]
> Pass på å aktivere `pre-commit` med `uv run pre-commit install` første gang
> man kloner prosjektet. Dette gir en ekstra sikkerhet for at kodekvalitet blir
> vedlikeholdt mellom forskjellige maskiner, IDE-er og utviklerverktøy.

> [!TIP]
> Prosjektet inneholder en [`justfile`](https://github.com/casey/just) som
> automatiserer en del enkle oppgaver.
>
> Man kan for eksempel få `ruff` til å fikse koden ved å kjøre `just fix` eller
> kjøre tester med `just test`.
