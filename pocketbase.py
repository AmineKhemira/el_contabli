import httpx
from config import POCKETBASE_URL, POCKETBASE_EMAIL, POCKETBASE_PASSWORD

_token: str = ""


async def _auth(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        f"{POCKETBASE_URL}/api/collections/users/auth-with-password",
        json={"identity": POCKETBASE_EMAIL, "password": POCKETBASE_PASSWORD},
    )
    resp.raise_for_status()
    return resp.json()["token"]


async def _headers(client: httpx.AsyncClient) -> dict:
    global _token
    if not _token:
        _token = await _auth(client)
    return {"Authorization": _token}


async def _request(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=30) as client:
        headers = await _headers(client)
        resp = await client.request(method, f"{POCKETBASE_URL}{path}", headers=headers, **kwargs)
        if resp.status_code == 401:
            # token expired — re-auth once
            global _token
            _token = await _auth(client)
            headers = {"Authorization": _token}
            resp = await client.request(method, f"{POCKETBASE_URL}{path}", headers=headers, **kwargs)
        resp.raise_for_status()
        return resp.json()


async def create_record(collection: str, data: dict) -> dict:
    return await _request("POST", f"/api/collections/{collection}/records", json=data)


async def list_records(collection: str, params: dict | None = None) -> list[dict]:
    result = await _request("GET", f"/api/collections/{collection}/records", params=params or {})
    return result.get("items", [])


async def update_record(collection: str, record_id: str, data: dict) -> dict:
    return await _request("PATCH", f"/api/collections/{collection}/records/{record_id}", json=data)
