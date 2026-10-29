
import asyncio
import getpass
import secrets

import httpx

BASE_URL = "http://127.0.0.1:8000"


async def main():
    token = getpass.getpass(
        "Paste a fresh access token for the owner of wallet 2: "
    ).strip()

    if not token:
        print("No token provided. Test cancelled.")
        return

    headers = {"Authorization": f"Bearer {token}"}

    async def send_transfer(client, label):
        key = f"concurrency-{label}-{secrets.token_hex(8)}"

        try:
            response = await client.post(
                f"{BASE_URL}/api/transfers",
                headers={
                    **headers,
                    "Idempotency-Key": key,
                },
                json={
                    "sender_wallet_id": 2,
                    "receiver_wallet_id": 1,
                    "amount": "400.00",
                },
            )

            try:
                body = response.json()
            except ValueError:
                body = response.text

            return {
                "test": label,
                "status": response.status_code,
                "body": body,
            }

        except httpx.HTTPError as exc:
            return {
                "test": label,
                "error": str(exc),
            }

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = await asyncio.gather(
            send_transfer(client, "A"),
            send_transfer(client, "B"),
        )

    for result in results:
        print(f"\nTest {result['test']}:")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
