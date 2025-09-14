import httpx
from typing import Optional, Dict, Any

class LybicClient:
    """Light-weight async wrapper for Lybic REST API."""

    # ---------- life-cycle ----------
    def __init__(self, api_key: str, base_url: str, org_id: str) -> None:
        self.base     = base_url.rstrip("/")
        self.org_id   = org_id
        self.http     = httpx.AsyncClient(
            headers={"X-Api-Key": api_key, "Content-Type": "application/json"},
            timeout=30,
        )

        # runtime cache (set by create_sandbox)
        self.sandbox: Optional[Dict[str, Any]] = None
        # self.connect_details: Optional[Dict[str, Any]] = None

    async def close(self) -> None:
        await self.http.aclose()

    # ---------- low-level ----------
    async def _req(self, path: str, method: str = "GET", json: Any = None):
        r = await self.http.request(method, f"{self.base}{path}", json=json)
        # ▶ 打印调试信息
        req = r.request                        # httpx.Request 对象
        print(
            "[HTTP]", req.method, req.url,     # 完整 URL（含 querystring）
            "json=",   json,
            "status=", r.status_code,
        )

        r.raise_for_status()
        return r.json()

    # ---------- high-level ----------
    async def create_sandbox(self, **opts) -> Dict[str, Any]:
        """
        Create a new sandbox and cache its metadata / connectDetails.
        Returns the full response dict.
        """
        resp = await self._req(
            f"/api/orgs/{self.org_id}/sandboxes", "POST", opts or {}
        )

        # cache
        self.sandbox          = resp
        # self.connect_details  = resp.get("connectDetails")
        return resp

    def _require_sandbox_id(self, sid: Optional[str]) -> str:
        if sid:
            return sid
        if self.sandbox:
            return self.sandbox["id"]
        raise RuntimeError("No sandbox_id specified and none cached — "
                           "call create_sandbox() first.")

    async def preview(self, sid: Optional[str] = None):
        sid = self._require_sandbox_id(sid)
        return await self._req(
            f"/api/orgs/{self.org_id}/sandboxes/{sid}/preview", "POST"
        )

    async def exec_action(self, action: dict, sid: Optional[str] = None):
        """
        Execute a single GUI action. `sid` optional if sandbox already cached.
        """
        sid = self._require_sandbox_id(sid)
        return await self._req(
            f"/api/orgs/{self.org_id}/sandboxes/{sid}/actions/computer-use",
            "POST",
            {"action": action},
        )

    async def parse_nl(self, text: str, model: str = "ui-tars"):
        return await self._req(
            "/api/computer-use/parse",
            "POST",
            {"model": model, "textContent": text},
        )

    # ---------- helpers ----------
    @property
    def sandbox_id(self) -> Optional[str]:
        return self.sandbox["id"] if self.sandbox else None

