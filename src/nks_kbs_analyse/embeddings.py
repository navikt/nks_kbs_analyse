"""Oppsett for å sette opp embedding funksjonalitet gjennom LangChain."""

from langchain_core.embeddings import Embeddings

from .settings import settings


def get_embedding() -> Embeddings:
    """Hjelpemetode som konfigurerer riktig embedding modell.

    Basert på innstillinger for prosjektet
    """
    from langchain_openai import AzureOpenAIEmbeddings

    return AzureOpenAIEmbeddings(  # type: ignore[no-any-return]
        api_key=settings.api_key.get_secret_value(),
        api_version=settings.azure.api_versjon,
        azure_deployment=settings.azure.embedding_deployment,
        azure_endpoint=str(settings.endpoint),
        chunk_size=settings.azure.chunk_size,
        model=settings.azure.embedding_model,
    )
