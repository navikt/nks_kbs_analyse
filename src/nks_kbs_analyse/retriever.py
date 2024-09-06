"""LangChain integrasjon til NKS-VDB."""

from typing import Any, ClassVar

import httpx
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from .auth import BrowserSessionAuthentication


def _convert_response_docs(response: list[dict[str, Any]]) -> list[Document]:
    """Konverter JSON response fra NKS-VDB til LangChain dokumenter."""
    return [
        Document(
            page_content=resp["content"],
            metadata=resp["metadata"]
            | {
                "SemanticSimilarity": resp.get("semantic_similarity"),
                "Score": resp.get("score"),
            },
        )
        for resp in response
    ]


class NKSRetriever(BaseRetriever):
    """Klasse som henter dokumenter fra NKS-VDB.

    Klassen tar seg av autentisering på NAIS enten som en applikasjon eller på
    vegne av brukere.
    """

    k: int = 5
    """Antall dokumenter å hente fra NKS-VDB per kall"""

    auth: BrowserSessionAuthentication
    """Objekt for å hente autentisering"""

    conn: ClassVar[httpx.Client] = httpx.Client(
        base_url="https://nks-vdb.ansatt.dev.nav.no"
    )

    def _get_relevant_documents(self, query: str, **kwargs: Any) -> list[Document]:
        """Hent dokumenter fra NKS VDB."""
        self.conn.cookies = self.auth.get_cookie()
        # Bygg spørring til NKS-VDB
        params = {
            "query": query,
            "num_results": str(kwargs.get("k", self.k)),
            "fts_weight": str(kwargs.get("fts_weight", 1.0)),
            "semantic_weight": str(kwargs.get("semantic_weight", 1.0)),
        }
        # Kjør spørring
        response = self.conn.get(
            url="/api/v1/search",
            params=params,
            timeout=kwargs.get("timeout", 20.0),
        ).raise_for_status()
        return _convert_response_docs(response.json())
