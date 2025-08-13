"""Innstillinger fra miljøvariabler."""

from typing import Annotated

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Konfigurasjon for CLI."""

    model_config = SettingsConfigDict(
        env_prefix="nks_bob_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    vdb_url: Annotated[HttpUrl, Field("https://nks-vdb.ansatt.dev.nav.no")]
    """URL til NKS-VDB tjenesten"""

    navno_vdb_url: Annotated[HttpUrl, Field("https://navno-vdb.ansatt.dev.nav.no")]
    """URL til NKS-VDB tjenesten"""

    kbs_url: Annotated[HttpUrl, Field("https://nks-kbs.ansatt.dev.nav.no")]
    """URL til NKS-KBS tjenesten"""


settings = Settings()
