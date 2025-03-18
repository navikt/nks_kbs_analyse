"""Funksjoner for å laste/fjerne dokumenter i Azure Search."""

from azure.search.documents.indexes.models import (
    SearchableField,
    SearchField,
    SearchFieldDataType,
)
from langchain_community.vectorstores.azuresearch import AzureSearch
from langchain_core.embeddings.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from .embeddings import get_embedding
from .knowledgebase import METADATA_COLUMNS
from .settings import settings


class ExtendedVectorStore(VectorStore):
    """Utvidet VectorStore som støtter ekstra funksjonalitet."""

    def clear(self) -> bool:
        """Tøm alle dokumenter fra VectorStore.

        Returns:
            Indikasjon på at databasen ble tømt
        """
        return False


class AzureExtended(AzureSearch, ExtendedVectorStore):  # type: ignore
    """Azure AI Search vector store med støtte for truncate.

    Utvidet fra `AzureSearch`
    """

    def clear(self) -> bool:
        """Slett innhold fra indeks."""
        # Azure har ingen innebygd funksjonalitet for å tømme indeksen,
        # så 'clear' vil i dette tilfellet være å slette den
        # Trenger da en SearchIndexClient-instans

        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents.indexes import SearchIndexClient

        assert settings.azure_search_admin_key is not None, (
            "'AZURE_SEARCH_ADMIN_KEY' må være satt i kjøretidsmiljøet "
            "for å kunne bruke 'azure_search'!"
        )

        azure_search_endpoint = settings.azure_search_endpoint
        azure_search_key = settings.azure_search_admin_key.get_secret_value()
        azure_search_credential = AzureKeyCredential(azure_search_key)

        index_client = SearchIndexClient(
            endpoint=azure_search_endpoint, credential=azure_search_credential
        )
        # finner eksisterende index
        existing_index = index_client.get_index(name=settings.azure_ai.search_index)
        # sletter indexen
        index_client.delete_index(settings.azure_ai.search_index)
        # gjenoppretter tom index
        index_client.create_index(existing_index)

        return True


def create_store(
    embedding: Embeddings | None = None,
) -> VectorStore | ExtendedVectorStore:
    """Lag en ny `langchain_core.vectorstores.VectorStore`.

    Args:
        embedding (Optional[langchain_core.embeddings.embeddings.Embeddings]):
            Modellen som brukes for å generere embeddings, hvis ikke oppgitt brukes default for prosjektet
    Returns:
        En `langchain_community.vectorstores.VectorStore` som kan brukes for å
        laste opp dokumenter til backend og søke etter lignende dokumenter.
    """
    if not embedding:
        embedding = get_embedding()

    assert settings.azure_search_admin_key is not None, (
        "'AZURE_SEARCH_ADMIN_KEY' må være satt i kjøretidsmiljøet "
        "for å kunne bruke 'azure_search'!"
    )

    embedding_function = embedding.embed_query
    # ønsker å legge til metadata som egne felter i indexen
    # spesifiserer derfor hvert felt eksplisitt

    # content-fields er default felter som må med
    CONTENT_FIELDS: list[SearchableField] = [
        SearchableField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            searchable=True,
        ),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=len(embedding_function("Text")),
            vector_search_profile_name="myHnswProfile",
        ),
        SearchableField(
            name="metadata",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
    ]
    # legger deretter til metadata-feltene
    METADATA_FIELDS: list[SearchableField] = []
    for column in METADATA_COLUMNS + [
        "Section",
        "Tab",
        "ContentColumn",
        "EmbeddingCreation",
    ]:
        field_args = {
            "name": column,
            "type": SearchFieldDataType.String,
            "filterable": True,
        }
        METADATA_FIELDS.append(SearchableField(**field_args))

    INDEX_FIELDS = CONTENT_FIELDS + METADATA_FIELDS

    return AzureExtended(
        azure_search_endpoint=settings.azure_search_endpoint,
        azure_search_key=settings.azure_search_admin_key.get_secret_value(),
        index_name=settings.azure_ai.search_index,
        embedding_function=embedding_function,
        fields=INDEX_FIELDS,
    )
