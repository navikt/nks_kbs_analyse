"""Tester for nettleser basert autentisering."""

import os
from typing import cast

import httpx
import pytest
from pydantic import HttpUrl

from nks_kbs_analyse.auth import BrowserSessionAuthentication, BrowserType


@pytest.mark.interactive
@pytest.mark.parametrize(
    "url",
    [
        HttpUrl("https://nks-vdb.ansatt.dev.nav.no"),
        HttpUrl("https://nks-kbs.ansatt.dev.nav.no"),
    ],
)
def test_authentication(url: HttpUrl) -> None:
    """Sjekk at autentisering fungerer."""
    auth = BrowserSessionAuthentication(
        base_url=url,
        browser=cast(BrowserType, os.getenv("BROWSER")),
        profile_path=os.getenv("PROFILE_PATH"),
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
        base_url=HttpUrl(base_url),
        browser=cast(BrowserType, os.getenv("BROWSER")),
        profile_path=os.getenv("PROFILE_PATH"),
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
