"""Tester for nettleser basert autentisering."""

import os
from typing import cast

import httpx
import pytest
from pydantic import HttpUrl
from pydantic_core import Url

from nks_kbs_analyse.auth import BrowserSessionAuthentication, BrowserType


@pytest.mark.interactive
@pytest.mark.parametrize(
    "url",
    [
        Url("https://nks-vdb.ansatt.dev.nav.no"),
        Url("https://nks-kbs.ansatt.dev.nav.no"),
    ],
)
def test_authentication(url: HttpUrl) -> None:
    """Sjekk at autentisering fungerer."""
    auth = BrowserSessionAuthentication(
        base_url=url, browser=cast(BrowserType, os.getenv("BROWSER"))
    )
    cookie = auth.get_cookie()
    print(cookie)
    assert cookie, f"Klarte ikke å autentisere mot: {url!s}"
    response = httpx.get(str(url) + "oauth2/session", cookies=cookie)
    assert (
        response.status_code == 200
    ), f"Fikk ikke tak i sesjonsinformasjon {response.request}"
    data = response.json()
    assert "session" in data, "Virker ikke som gyldig sesjonsinformasjon"
    assert data["session"]["active"], "Sesjon er ikke aktiv"
    assert (
        data["session"]["ends_in_seconds"] >= 5 * 60
    ), "Forventer at sesjon slutter om mer enn 5 minutter"


@pytest.mark.interactive
def test_vector_search() -> None:
    """Sjekk at kall til `/api/v1/search` fungerer med autentisering."""
    base_url = "https://nks-vdb.ansatt.dev.nav.no"
    auth = BrowserSessionAuthentication(
        base_url=Url(base_url),
        browser=cast(BrowserType, os.getenv("BROWSER")),
    )
    response = httpx.get(
        base_url + "/api/v1/search",
        params={"query": "Hva er samordning mellom dagpenger og sykepenger?"},
        cookies=auth.get_cookie(),
    )
    assert response.status_code == 200, f"Fikk ikke svar fra {response.request}"
    data = response.json()
    assert len(data) > 0, "Fikk ingen dokumenter tilbake!"
    for document in data:
        assert "content" in document
        assert "metadata" in document
        assert "semantic_similarity" in document
        assert "score" in document
