"""Oppsett for å hente ut kunnskapsartikler fra den originale NKS kunnskapsbasen.

Vi benytter kunnskapsbasen på BigQuery som er gjengitt i
[Quarto](https://data.ansatt.nav.no/quarto/e7b3e02a-0c45-4b5c-92a2-a6d364120dfb/index.html)
"""

import re
from datetime import datetime
from typing import Iterable, Tuple, Union

from langchain_core.documents import Document

from .settings import settings

METADATA_COLUMNS: list[str] = [
    "ArticleType",
    "DataCategories",
    "KnowledgeArticleId",
    "KnowledgeArticle_QuartoUrl",
    "LastModifiedBQ",
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
    "EmployerInformation__c": dict(
        Section="Til arbeidsgiver", Tab="Arbeidsgiver", Fragment="ag-til-bruker"
    ),
    "EmployerInformationInternal__c": dict(
        Section="Mer informasjon", Tab="Arbeidsgiver", Fragment="ag-mer-informasjon"
    ),
    # International
    "InternationalInformation__c": dict(
        Section="Til brukeren", Tab="Internasjonalt", Fragment="int-til-bruker"
    ),
    "InternationalInformationInternal__c": dict(
        Section="Mer informasjon", Tab="Internasjonalt", Fragment="int-mer-informasjon"
    ),
    # Doctor & handler
    "AdvisorInformation__c": dict(
        Section="Til samhandler", Tab="Lege og behandler", Fragment="samh-til-bruker"
    ),
    "AdvisorInformationInternal__c": dict(
        Section="Mer informasjon",
        Tab="Lege og behandler",
        Fragment="samh-mer-informasjon",
    ),
    # Other
    "NKS_Nav_no__c": dict(Section="nav.no", Tab="Annen"),
    "NKS_Legislation__c": dict(Section="Lovverk", Tab="Annen"),
    "WhoDoesWhat__c": dict(
        Section="Hvem gjør hva", Tab="Annen", Fragment="hvem-gjr-hva"
    ),
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
        fragment = "intern-rutine"
    elif "Felles" in title:
        pb_tab = "Generelt"
        article_section = "Mer informasjon"
        fragment = "mer-informasjon"
    else:
        pb_tab = "Personbruker"
        article_section = "Mer informasjon"
        fragment = "mer-informasjon"
    if column_name == "NKS_User__c":
        return dict(Section="Til brukeren", Tab=pb_tab, Fragment="til-bruker")
    elif column_name == "Article__c":
        return dict(Section=article_section, Tab=pb_tab, Fragment=fragment)
    else:
        return METADATA_MAPPING[column_name]


def __format_query(
    content_column: str, min_length: int = 30, last_modified: datetime | None = None
) -> str:
    """Intern metode som formaterer spørring til kunnskapsbasen for å hente dokumenter.

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
        sql += f" AND LastModifiedBQ > '{last_modified.isoformat()}'"
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

    client = bigquery.Client(project=settings.gcp.prosjekt)
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

    client = bigquery.Client(project=settings.gcp.prosjekt)
    query = (
        "SELECT KnowledgeArticleId"
        " FROM `kunnskapsbase.kunnskapsartikler`"
        " WHERE PublishStatus = 'Online'"
    )
    raw_results = client.query(query).result()
    return set(row["KnowledgeArticleId"] for row in raw_results)


def _clean_document(doc: Document) -> Document:
    """Prøv å rense kunnskapsartikkel (`doc`) med enkle regex-er."""
    import re

    new_content = doc.page_content
    # Fjerne for mange newline etter overskrift
    new_content = re.sub(r"(#{1,6}.*\n)\n+", r"\1", new_content)
    # Bytter 3 eller flere newlines med 2 newlines
    new_content = re.sub(r"(\n\n)\s+", r"\1", new_content)
    # Fjerne tomme markdown overskrifter
    new_content = re.sub(r"^#{1,6}\s*\n", "", new_content, flags=re.MULTILINE)
    return Document(page_content=new_content, metadata=doc.metadata)


def clean_documents(docs: Iterable[Document]) -> list[Document]:
    """Prøv å rense kunnskapsartikler (`docs`) med enkle regex-er."""
    return [_clean_document(doc) for doc in docs]


class CustomMarkdownHeaderSplitter:
    """Klasse for å splitte tekst basert på markdownoverskrifter.

    Klassen er en re-implementasjon av MarkdownHeaderTextSplitter fra
    langchain_text_splitters.

    """

    DEFAULT_HEADER_KEYS = {"#": "#", "##": "##", "###": "###"}
    """Default headers å splitte teksten på"""

    def __init__(
        self,
        headers_to_split_on: Union[list[Tuple[str, str]], None] = None,
        strip_headers: bool = True,
    ):
        """Setter opp en CustomMarkdownHeaderSplitter."""
        self.chunks: list[Document] = []
        self.current_chunk = Document(page_content="")
        self.current_header_stack: list[Tuple[int, str]] = []
        self.strip_headers = strip_headers
        if headers_to_split_on:
            self.splittable_headers = dict(headers_to_split_on)
        else:
            self.splittable_headers = self.DEFAULT_HEADER_KEYS

    def split_text(self, text: str) -> list[Document]:
        """Splitt opp en gitt tekst basert på markdownoverskrifter.

        Identifiserte overskrifter (headers) skal trekkes ut av teksten og legges til
        som metadata i dokumentet.

        Til forskjell fra hvordan MarkdownHeaderTextSplitter er implementert vil denne
        metoden bevare original formatering ellers i teksten. Koden er sterkt inspirert
        av implementasjonen i ExperimentalMarkdownSyntaxTextSplitter i langchain.

        """
        raw_lines = text.splitlines(keepends=True)

        while raw_lines:
            raw_line = raw_lines.pop(0)
            header_match = self._match_header(raw_line)
            if header_match:
                self._complete_chunk_doc()

                if not self.strip_headers:
                    self.current_chunk.page_content += raw_line

                # Add the header to the stack
                header_depth = len(header_match.group(1))
                header_text = header_match.group(2)
                self._resolve_header_stack(header_depth, header_text)
            else:
                self.current_chunk.page_content += raw_line

        self._complete_chunk_doc()
        return self.chunks

    def _resolve_header_stack(self, header_depth: int, header_text: str) -> None:
        for i, (depth, _) in enumerate(self.current_header_stack):
            if depth == header_depth:
                self.current_header_stack[i] = (header_depth, header_text)
                self.current_header_stack = self.current_header_stack[: i + 1]
                return
        self.current_header_stack.append((header_depth, header_text))

    def _complete_chunk_doc(self) -> None:
        chunk_content = self.current_chunk.page_content
        # Discard any empty documents
        if chunk_content and not chunk_content.isspace():
            # Apply the header stack as metadata
            for depth, value in self.current_header_stack:
                header_key = self.splittable_headers.get("#" * depth)
                self.current_chunk.metadata[header_key] = value
            self.chunks.append(self.current_chunk)
        # Reset the current chunk
        self.current_chunk = Document(page_content="")

    def _match_header(self, line: str) -> Union[re.Match[str], None]:
        match = re.match(r"^(#{1,6}) (.*)", line)
        # Only matches on the configured headers
        if match and match.group(1) in self.splittable_headers:
            return match
        return None


def _split_documents_on_headers(
    documents: Iterable[Document],
    headers_to_split_on: Union[list[Tuple[str, str]], None] = None,
) -> list[Document]:
    """Splitt dokumenter basert på markdownoverskrifter.

    Returner de splittede dokumentene med overskriftene som ekstra metadata.
    """
    split_docs: list[Document] = []
    for document in documents:
        markdown_header_splitter = CustomMarkdownHeaderSplitter(
            headers_to_split_on=headers_to_split_on, strip_headers=True
        )
        fragments = markdown_header_splitter.split_text(document.page_content)
        doc_metadata = document.metadata.copy()
        split_docs.extend(
            Document(
                page_content=fragment.page_content,
                metadata={**doc_metadata, "Headers": fragment.metadata.copy()},
            )
            for fragment in fragments
        )
    return split_docs


def _combine_headers_and_content(documents: list[Document]) -> list[Document]:
    """Legg til kontekst fra metadata i page_content for dokumenter.

    Args:
        documents:
            Dokumentene som skal oppdateres
    """
    combined_docs: list[Document] = []
    for document in documents:
        header_metadata = document.metadata["Headers"]
        headers = "\n".join(
            [f"{key} {value}" for key, value in header_metadata.items()]
        )

        new_page_content = (
            f"{headers}\n\n{document.page_content}"
            if headers
            else document.page_content
        )

        combined_docs.append(
            Document(page_content=new_page_content, metadata=document.metadata)
        )
    return combined_docs


def split_documents(
    docs: Iterable[Document],
    chunk_size: int = 1000,
    overlap: int = 100,
    headers_to_split_on: Union[list[Tuple[str, str]], None] = None,
) -> list[Document]:
    """Splitt dokumenter ned til mindre dokumenter.

    Hensikt: slik at de er passende for å sende til en embedding modell

    Gjør først en splitt basert på markdown headers.
    Deretter splitt basert på antall tegn.
    Metadata fra markdown headers legges til i de resulterende dokumentene.

    Args:
        docs:
            Dokumentene som potensielt skal splittes
        chunk_size:
            Hvor store skal et nytt dokument være når det splittes
        overlap:
            Når det splittes, hvor mye tekst kan/skal overlappe mellom en splitt
        headers_to_split_on:
            Hvilke overskriftsnivå som skal splittes på.
            (Default er #, ## og ###)

    Returns:
        De originale dokumentene potensielt splittet i mindre dokumenter med
        kontekst fra headers lagt til
    """
    from langchain_text_splitters import Language, RecursiveCharacterTextSplitter

    text_splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.MARKDOWN, chunk_size=chunk_size, chunk_overlap=overlap
    )

    # Først splitt dokumentene basert på markdown headers
    header_split_docs = _split_documents_on_headers(docs, headers_to_split_on)

    # Deretter splitt basert på antall tegn
    recursive_split_docs = text_splitter.transform_documents(header_split_docs)

    # Legg til markdown headers som metadata i de splittede dokumentene
    split_docs_with_context = _combine_headers_and_content(recursive_split_docs)

    return split_docs_with_context
