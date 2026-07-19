"""Unused scaffold for eBay's Browse API."""

import base64
from dataclasses import dataclass

import requests

SCOPE = "https://api.ebay.com/oauth/api_scope"


@dataclass(frozen=True)
class EbayClient:
    client_id: str
    client_secret: str
    sandbox: bool = False
    marketplace_id: str = "EBAY_US"

    @property
    def host(self):
        return "api.sandbox.ebay.com" if self.sandbox else "api.ebay.com"

    def application_token(self):
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        response = requests.post(
            f"https://{self.host}/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": SCOPE},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["access_token"]

    def search(self, query, limit=50):
        response = requests.get(
            f"https://{self.host}/buy/browse/v1/item_summary/search",
            headers={
                "Authorization": f"Bearer {self.application_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            },
            params={"q": query, "limit": limit},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("itemSummaries", [])
