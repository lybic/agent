# ---------------------------------------------------------------------------
# 3) Cloud desktop / custom device backend (Lybic)
# ---------------------------------------------------------------------------
from typing import Dict
from gui_agents.s2.agents.Action import (
    Action,
    Click,
    Drag,
    TypeText,
    Scroll,
    Hotkey,
    HoldAndPress,
    Wait,
    MouseButton,
    ScrollAxis,
)

from gui_agents.s2.agents.Backend import Backend



class LybicBackend(Backend):
    """Stub for Lybic cloud‑device backend (JSON RPC)."""

    _supported = {Click, Drag, TypeText, Scroll, Hotkey, Wait}

    def __init__(self, endpoint: str, auth_token: str):
        self.endpoint = endpoint
        self.auth_token = auth_token
        # In a real implementation you would establish a websocket or HTTP
        # session here.

    def execute(self, action: Action) -> None:
        # Serialize the action via registry helper
        payload: Dict = action.to_dict()
        # Send over HTTP as JSON; omitted for brevity
        # requests.post(self.endpoint + "/execute", json=payload, headers={"Authorization": f"Bearer {self.auth_token}"})
        raise NotImplementedError("LybicBackend.execute() not implemented – stub only.")

