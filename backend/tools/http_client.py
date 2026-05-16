import asyncio
from typing import Dict, Optional

import httpx


class HTTPClient:
    """Shared HTTP client with retry and backoff support."""

    def __init__(self, timeout: float = 30.0):
        self.client = httpx.AsyncClient(timeout=timeout)

    async def get_with_retries(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 5,
        retry_delay: float = 1.0,
    ) -> httpx.Response:
        """Perform a GET request with retries on rate limiting."""
        last_response: Optional[httpx.Response] = None
        for attempt in range(1, max_retries + 1):
            response = await self.client.get(url, headers=headers)
            if response.status_code != 429:
                return response
            last_response = response
            if attempt == max_retries:
                return response
            await asyncio.sleep(retry_delay * attempt)
        return last_response  # type: ignore[return-value]

    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()


# Singleton instance for shared use
http_client = HTTPClient()


if __name__ == "__main__":
    import argparse
    import json

    async def main():
        parser = argparse.ArgumentParser(description="HTTP Client Test")
        parser.add_argument("url", help="URL to fetch")
        args = parser.parse_args()

        response = await http_client.get_with_retries(args.url)
        print("Status Code:", response.status_code)
        print("Response:", response.text)

    asyncio.run(main())