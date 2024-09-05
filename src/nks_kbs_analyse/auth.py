"""Støtte for autentisering.

Autentisering skjer gjennom nettleseren til bruker og ved å benytte Wonderwall
sin sesjonshåndtering. Hvis ikke bruker er autentisert prøver vi å åpne en
nettleser og deretter lese cookies slik at vi kan gjenbruke sessions token.
"""

import datetime
import time
import webbrowser
from typing import Literal

import browser_cookie3
import httpx
from dateutil.parser import parse
from pydantic import HttpUrl

BrowserType = Literal[
    "firefox", "opera", "windows-default", "safari", "chrome", "chromium"
]
"""Type hint for nettleser utvalg"""


class BrowserSessionAuthentication:
    """Autentisering ved hjelp av nettleser og cookies."""

    base_url: httpx.URL
    """NAIS URL som man ønsker å autentisere mot"""

    client: httpx.Client
    """HTTP klient for mellomlagring av tilkoblinger"""

    browser: webbrowser.BaseBrowser
    """Kobling for å interagere med brukeren sin nettleser"""

    browser_type: BrowserType | None
    """Typen nettleser - brukes for å hente cookies fra riktig nettleser"""

    def __init__(self, base_url: HttpUrl, browser: BrowserType | None = None):
        """Lag et nytt autentiseringsobjekt som autentiserer for `base_url`."""
        self.base_url = httpx.URL(str(base_url))
        self.client = httpx.Client(base_url=self.base_url)
        self.browser = webbrowser.get(browser)
        self.browser_type = browser

    def _load_session(self) -> httpx.Cookies | None:
        """Last inn autentiserings sesjons cookie.

        Hvis `SESSION_COOKIE_NAME` ikke finnes returneres `None`.
        """
        if self.browser_type and hasattr(browser_cookie3, self.browser_type):
            cookie_method = getattr(browser_cookie3, self.browser_type)
            all_cookies = cookie_method()
        else:
            all_cookies = browser_cookie3.load()
        url_cookies = [
            cookie for cookie in all_cookies if cookie.domain in self.base_url.host
        ]
        if url_cookies:
            result = httpx.Cookies()
            for cookie in url_cookies:
                result.set(cookie.name, cookie.value, cookie.domain, cookie.path)
            return result
        return None

    def _check_session(self) -> bool:
        """Sjekk om det finnes en aktiv sesjon eller om bruker må reautentisere."""
        self.client.cookies = self._load_session()
        resp = self.client.get("/oauth2/session")
        # Hvis vi får 401 betyr det at det ikke finnes en sesjon eller at den
        # har utløpt, 302 indikerer at siden ønsker å videresende oss til
        # innlogging
        if resp.status_code == 401 or resp.status_code == 302:
            return False
        elif resp.status_code == 200:
            session = resp.json()
            active = session["session"]["active"]
            ends_at = parse(session["session"]["ends_at"])
            # Hvis sesjonen ikke er aktiv (mao. inaktiv) eller sesjonen utløper
            # innen 5 minutter så ber vi brukeren om å autentisere på nytt
            if not active or ends_at - datetime.timedelta(
                minutes=5
            ) < datetime.datetime.now(ends_at.tzinfo):
                return False
            # Hvis vi kommer hit må vi passe på at sesjonen finnes i en
            # nettleser mellomlagring
            return self._load_session() is not None
        else:
            raise RuntimeError(
                "Fikk ukjent status fra '/oauth2/session' grensesnitt: "
                f"{resp.status_code} - ({resp.text})"
            )

    def _request_auth(self) -> bool:
        """Få brukeren til å autentisere seg med en browser."""
        # Åpne nettleserfane for brukeren og diriger dem til login endepunkt
        return self.browser.open(
            str(self.base_url.copy_with(path="/oauth2/login")), new=2
        )

    def get_cookie(self) -> httpx.Cookies:
        """Hent sesjons header ved å be bruker om å autentisere med nettleser."""
        if not self._check_session():
            self._request_auth()
            num_refresh = 0
            while True:
                num_refresh += 1
                if self._check_session():
                    return self._load_session()
                elif num_refresh > 2:
                    raise TimeoutError("Klarte ikke å laste sesjonstoken")
                time.sleep(5)
        session = self._load_session()
        assert session, "Det finnes en aktiv sesjon, men den kunne ikke lastes!"
        return session

    def __call__(self) -> httpx.Cookies:
        """Hent autentiseringstoken som en header (samme som `get_session`)."""
        return self.get_cookie()
