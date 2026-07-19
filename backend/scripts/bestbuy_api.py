"""Unused scaffold for Best Buy's official Products API."""

from dataclasses import dataclass
from urllib.parse import quote

import requests


@dataclass(frozen=True)
class BestBuyClient:
    api_key: str

    def search(self, query, page_size=25):
        filters = "&".join(
            f"search={quote(term, safe='')}" for term in query.split()
        )
        response = requests.get(
            f"https://api.bestbuy.com/v1/products({filters})",
            params={
                "apiKey": self.api_key,
                "format": "json",
                "pageSize": page_size,
                "show": "sku,name,manufacturer,modelNumber,salePrice,url,image",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("products", [])
