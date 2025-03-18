"""Oppsett for å sette opp embedding funksjonalitet gjennom LangChain."""

from langchain_core.embeddings import Embeddings

from .settings import settings


def get_embedding() -> Embeddings:
    """Hjelpemetode som konfigurerer riktig embedding modell.

    Basert på innstillinger for prosjektet.
    """
    from langchain_openai import AzureOpenAIEmbeddings

    embedding: Embeddings = AzureOpenAIEmbeddings(
        dimensions=settings.azure_ai.embedding_size,
        api_key=settings.azure_api_key.get_secret_value(),
        api_version=settings.azure_ai.api_versjon,
        azure_deployment=settings.azure_ai.embedding_deployment,
        azure_endpoint=str(settings.azure_endpoint),
        chunk_size=settings.azure_ai.chunk_size,
        model=settings.azure_ai.embedding_model,
    )
    return embedding
