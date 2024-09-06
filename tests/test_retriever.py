"""Test NKS LangChain retrieveren."""

import os
from typing import cast

import pytest
from pydantic_core import Url

from nks_kbs_analyse.auth import BrowserSessionAuthentication, BrowserType
from nks_kbs_analyse.retriever import NKSRetriever


@pytest.fixture
def retriever() -> NKSRetriever:
    """Hjelpemetode for å lage en retriever for tester."""
    auth = BrowserSessionAuthentication(
        Url("https://nks-vdb.ansatt.dev.nav.no"),
        cast(BrowserType, os.getenv("BROWSER")),
    )
    return NKSRetriever(auth=auth)


@pytest.mark.interactive
def test_retriever(retriever: NKSRetriever) -> None:
    """Sjekk at retriever fungerer."""
    docs = retriever.invoke("Hva er samordning mellom dagpenger og sykepenger?")
    assert docs, "Fikk ikke dokumenter fra retriever"
    assert len(docs) == retriever.k, "Antall dokumenter hentet samsvarer ikke"


@pytest.mark.interactive
def test_num_documents(retriever: NKSRetriever) -> None:
    """Sjekk at vi kan endre antall dokumenter hentet."""
    docs = retriever.invoke("Hva er dagpenger?")
    assert len(docs) == retriever.k
    docs = retriever.invoke("Hva er sykepenger?", k=3)
    assert len(docs) == 3
