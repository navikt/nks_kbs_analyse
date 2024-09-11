"""Oppsett for å hente ut kunnskapsartikler fra den originale NKS kunnskapsbasen.

Vi benytter kunnskapsbasen på BigQuery som er gjengitt i
[Quarto](https://data.ansatt.nav.no/quarto/e7b3e02a-0c45-4b5c-92a2-a6d364120dfb/index.html)
"""

from datetime import datetime
from typing import Iterable

from langchain_core.documents import Document

METADATA_COLUMNS: list[str] = [
    "ArticleType",
    "DataCategories",
    "KnowledgeArticleId",
    "KnowledgeArticle_QuartoUrl",
    "LastModifiedDate",
    "Title",
]
"""Liste over metadata som hentes fra kunnskapsbasen og legges ved dokumentene
som produseres"""

CONTENT_COLUMNS: list[str] = [
    "Article__c",
    "NKS_User__c",
    "WhoDoesWhat__c",
    "EmployerInformation__c",
    "EmployerInformationInternal__c",
    "InternationalInformation__c",
    "InternationalInformationInternal__c",
    "AdvisorInformation__c",
    "AdvisorInformationInternal__c",
    "How_you_send_a_task__c",
]
"""Liste over kolonner som hentes ut fra kunnskapsbasen som er basis for
innholdet i dokumentene som produseres"""

METADATA_MAPPING: dict[str, dict[str, str]] = {
    # Translations
    "NKS_English__c": dict(Section="Engelsk - Personbruker", Tab="Oversettelser"),
    "NKS_English_Employer__c": dict(
        Section="Engelsk - Arbeidsgiver", Tab="Oversettelser"
    ),
    "NKS_Nynorsk__c": dict(Section="Nynorsk - Personbruker", Tab="Oversettelser"),
    "NKS_Nynorsk_Employer__c": dict(
        Section="Nynorsk - Arbeidsgiver", Tab="Oversettelser"
    ),
    # Employer
    "EmployerInformation__c": dict(Section="Til arbeidsgiver", Tab="Arbeidsgiver"),
    "EmployerInformationInternal__c": dict(
        Section="Mer informasjon", Tab="Arbeidsgiver"
    ),
    # International
    "InternationalInformation__c": dict(Section="Til brukeren", Tab="Internasjonalt"),
    "InternationalInformationInternal__c": dict(
        Section="Mer informasjon", Tab="Internasjonalt"
    ),
    # Doctor & handler
    "AdvisorInformation__c": dict(Section="Til samhandler", Tab="Lege og behandler"),
    "AdvisorInformationInternal__c": dict(
        Section="Mer informasjon", Tab="Lege og behandler"
    ),
    # Other
    "NKS_Nav_no__c": dict(Section="nav.no", Tab="Annen"),
    "NKS_Legislation__c": dict(Section="Lovverk", Tab="Annen"),
    "WhoDoesWhat__c": dict(Section="Hvem gjør hva", Tab="Annen"),
    "How_you_send_a_task__c": dict(Section="Slik sender du oppgave", Tab="Annen"),
}
"""Mapping av kolonne til ekstra metadata"""


def get_column_metadata(
    column_name: str, article_type: str, title: str
) -> dict[str, str]:
    """Hjelpemetode for å hente ut metadata om en kolonne fra BigQuery."""
    # Sett opp typer for de vanligste seksjonene og sidene
    if article_type == "Intern rutine":
        pb_tab = "Intern rutine"
        article_section = ""
    elif "Felles" in title:
        pb_tab = "Generelt"
        article_section = "Mer informasjon"
    else:
        pb_tab = "Personbruker"
        article_section = "Mer informasjon"
    if column_name == "NKS_User__c":
        return dict(Section="Til brukeren", Tab=pb_tab)
    elif column_name == "Article__c":
        return dict(Section=article_section, Tab=pb_tab)
    else:
        return METADATA_MAPPING[column_name]


def __format_query(
    content_column: str, min_length: int = 30, last_modified: datetime | None = None
) -> str:
    """Intern metode som benyttes for å formatere spørring til kunnskapsbasen for å hente ut dokumenter.

    Args:
        content_column:
            Kolonnen som skal benyttes som innhold for dokumentet
        min_length:
            Det må minst være `min_length` antall tegn i innholdet for at det
            skal regnes som et dokument. Dette brukes for å filtrere ut kolonner
            som ikke er NULL eller bare inneholder ' ', men som fortsatt ikke
            inneholder meningsfylt tekst.
        last_modified:
            Valgbar tidspunkt for å filtrere kolonner som er eldre enn
            `last_modified`
    Returns:
        SQL spørring for å hente ut `content_column` som et dokument
    """
    metadata_columns = ", ".join(METADATA_COLUMNS)
    sql = (
        "SELECT {metadata_columns},"
        " {content_column} AS Content,"
        " FROM `kunnskapsbase.kunnskapsartikler`"
        " WHERE PublishStatus = 'Online'"
        " AND {content_column} IS NOT NULL"
        " AND {content_column} != ''"
        " AND CHAR_LENGTH({content_column}) >= {min_length}"
    )
    if last_modified:
        sql += f" AND LastModifiedDate > '{last_modified.isoformat()}'"
    return sql.format(
        metadata_columns=metadata_columns,
        content_column=content_column,
        min_length=min_length,
    )


def load(last_modified: datetime | None = None) -> Iterable[Document]:
    """Last inn kunnskapsbasen fra BigQuery og produser LangChain dokumenter.

    Args:
        last_modified (valgbar):
            Bare last inn dokumenter nyere enn `last_modified`
    Returns:
        Generator som produserer dokumenter
    """
    from google.cloud import bigquery

    client = bigquery.Client(project="nks-aiautomatisering-prod-194a")
    # Vi itererer gjennom alle innholdkolonnene for å minimere minnebruk ved å
    # ikke hente ut alle kunnskapsartikler på en gang
    for column in CONTENT_COLUMNS:
        query = __format_query(column, last_modified=last_modified)
        raw_results = client.query(query).result()
        # For hver rad (mao. hver artikkel) henter vi ut innhold og metadata som
        # tilsammen produserer et dokument
        for row in raw_results:
            metadata = {k: v for k, v in row.items() if k in METADATA_COLUMNS}
            metadata |= get_column_metadata(column, row["ArticleType"], row["Title"])
            metadata["ContentColumn"] = column
            content = row["Content"]
            yield Document(page_content=content, metadata=metadata)


def get_active_article_ids() -> set[str]:
    """Hent ut ID-er for kunnskapsartikler som er aktive.

    Returns:
        Set med KnowledgeArticleId på aktive artikler
    """
    from google.cloud import bigquery

    client = bigquery.Client(project="nks-aiautomatisering-prod-194a")
    query = (
        "SELECT KnowledgeArticleId"
        " FROM `kunnskapsbase.kunnskapsartikler`"
        " WHERE PublishStatus = 'Online'"
    )
    raw_results = client.query(query).result()
    return set(row["KnowledgeArticleId"] for row in raw_results)


def split_documents(
    docs: Iterable[Document], chunk_size: int = 1000, overlap: int = 100
) -> list[Document]:
    """Split dokumenter ned til mindre dokumenter slik at de er passende for å sende til en embedding modell.

    Args:
        docs:
            Dokumentene som potensielt skal splittes
        chunk_size:
            Hvor store skal et nytt dokument være når det splittes
        overlap:
            Når det splittes, hvor mye tekst kan/skal overlappe mellom en split
    Returns:
        De originale dokumentene potensielt splittet i mindre dokumenter
    """
    from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.MARKDOWN, chunk_size=chunk_size, chunk_overlap=overlap
    )
    splits: list[Document] = text_splitter.transform_documents(docs)
    return splits


def clean_doc(doc: Document) -> Document:
    """Prøv å rense dokument med enkle regex-er."""
    import re

    new_content = doc.page_content
    # Fjerne for mange newline etter overskrift
    new_content = re.sub(r"(#{1,6}.*\n)\n+", r"\1", new_content)
    # Bytter 3 eller flere newlines med 2 newlines
    new_content = re.sub(r"(\n\n)\s+", r"\1", new_content)
    # Fjerne tomme markdown overskrifter
    new_content = re.sub(r"^#{1,6}\s*\n", "", new_content, flags=re.MULTILINE)
    return Document(page_content=new_content, metadata=doc.metadata)
