"""Konfigurasjon.

Noen innstillinger er ment å settes med miljøvariabler. For eksempel kan man
benytte '.env' filer
"""

from pydantic import AliasChoices, BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AzureConfig(BaseModel):
    """Konfigurasjon for tilkobling mot Azure OpenAI."""

    embedding_deployment: str = "text-embedding-3-large"
    """Navn på embedding modell deployment på Azure OpenAI Studio"""
    embedding_model: str = "text-embedding-3-large"
    """Type embedding modell for valgt embedding deployment"""
    api_versjon: str = "2023-05-15"
    """OpenAI API versjon å benytte"""
    chunk_size: int = 1024
    """Antall dokumenter som kan sendes til embedding samtidig"""
    search_index: str = "chunk_size_1500"
    """Navn på Azure Search index"""


class GCPConfig(BaseModel):
    """Konfigurasjon for tilkobling mot GCP og BigQuery."""

    prosjekt: str = "nks-aiautomatisering-prod-194a"
    """GCP prosjekt å benytte."""

    datasett: str = "kunnskapsbase"
    """GCP datasett i prosjekt."""


class Settings(BaseSettings):
    """Innstillinger."""

    model_config = SettingsConfigDict(
        env_prefix="nks_kbs_analyse_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

    # Følgende felter kan ikke plasseres i under modeller fordi man trenger at
    # 'validation_alias' fungerer uten prefix
    api_key: SecretStr = Field(
        validation_alias=AliasChoices(
            "nks_ds_api_key", "azure_openai_api_key", "openai_api_key"
        ),
    )
    """Azure OpenAI API nøkkel"""
    endpoint: str = Field(
        default="https://nks-digital-assistent.openai.azure.com/",
        validation_alias=AliasChoices(
            "nks_ds_endpoint", "azure_openai_endpoint", "openai_endpoint"
        ),
    )

    azure_search_endpoint: str = Field(
        default="https://nks-digital-assistent.search.windows.net",
        validation_alias=AliasChoices(
            "azure_search_endpoint", "azure_ai_search_endpoint"
        ),
    )
    """Azure AI Search API endepunkt"""
    azure_search_admin_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "azure_search_admin_key",
            "azure_search_api_key",
            "azure_ai_search_admin_key",
        ),
    )
    """Azure AI Search API nøkkel"""

    azure: AzureConfig = AzureConfig()
    """Innstillinger for Azure tilkobling"""
    gcp: GCPConfig = GCPConfig()
    """Innstillinger for GCP."""


# MERK: Vi ignorerer 'call-arg' for mypy ved instansiering på grunn av følgende
# bug: https://github.com/pydantic/pydantic/issues/6713

settings = Settings()
"""Instansiering av konfigurasjon som burde benyttes for å hente innstillinger."""
