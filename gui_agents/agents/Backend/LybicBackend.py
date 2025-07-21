# ---------------------------------------------------------------------------
# 3) Cloud desktop / custom device backend (Lybic)
# https://lybic.ai/docs/api/executeComputerUseAction
# ---------------------------------------------------------------------------
from typing import Dict
from gui_agents.agents.Action import (
    Action,
    Click,
    Drag,
    TypeText,
    Scroll,
    Hotkey,
    # HoldAndPress,
    Wait,
    # MouseButton,
    # ScrollAxis,
    # Open,
    # SwitchApp,
    Screenshot
)

from gui_agents.agents.Backend.Backend import Backend
from gui_agents.lybic.lybic_client import LybicClient
import asyncio, httpx, time, logging
from typing import Dict, Any, List, Optional
from httpx import HTTPStatusError, TimeoutException

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  helper: mapping enums / units → lybic spec
# ---------------------------------------------------------------------------





class LybicBackend(Backend):
    _supported = {Click, Drag, TypeText, Scroll, Hotkey,
                   Wait, Screenshot }

    # ---------- ctor ----------
    def __init__(self, api_key: str, org_id: str, *,
                 base_url="https://api.lybic.ai",
                 sandbox_opts: Optional[Dict[str, Any]] = None,
                 max_retries: int = 2):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.client = LybicClient(api_key, base_url, org_id)
        self.max_retries = max_retries

        self.loop.run_until_complete(
            self.client.create_sandbox(name="agent-run",
                                       maxLifeSeconds=3600,
                                       **(sandbox_opts or {}))
        )

    # ---------- public sync API ----------
    def execute(self, action: Action):
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} unsupported")

        if   isinstance(action, Click):        self._click(action)
        elif isinstance(action, Drag):         self._drag(action)
        elif isinstance(action, TypeText):     self._type(action)
        elif isinstance(action, Scroll):       self._scroll(action)
        elif isinstance(action, Hotkey):       self._hotkey(action)
        elif isinstance(action, HoldAndPress): self._hold_and_press(action)
        elif isinstance(action, Open):         self._open_app(action)
        elif isinstance(action, SwitchApp):    self._switch_app(action)
        elif isinstance(action, Screenshot):   return self._screenshot()   # type: ignore
        elif isinstance(action, Wait):         time.sleep(action.seconds)

    # ---------- internal helpers ----------
    def _do(self, lybic_action: Dict[str, Any]):
        """Send **one** action; centralized retries + error mapping."""
        async def _send():
            act_type = lybic_action.get("type", "").lower()
            if act_type in {"screenshot", "system:preview"}:
                # /preview endpoint doesn't need action payload
                return await self.client.preview()
            else:
                return await self.client.exec_action(action=lybic_action)

        exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                return self.loop.run_until_complete(_send())
            except (HTTPStatusError, TimeoutException) as e:
                exc = e
                log.warning(f"Lybic action failed (try {attempt}/{self.max_retries+1}): {e}")
                time.sleep(0.4 * attempt)               # back-off
        # Exceeded retry attempts
        raise RuntimeError(f"Lybic exec_action failed: {exc}") from exc

    # def _click(self, act: Click):
    #     self._do({
    #         "type": "mouse:click",
    #         "x": _px(act.xy[0]),
    #         "y": _px(act.xy[1]),
    #         "button": _btn(act.button_type),
    #         "clickCount": act.num_clicks,
    #         "modifiers": act.hold_keys or [],
    #     })
    
    # def _drag(self, act: Drag) -> None:
    #     self._do({
    #         "type": "mouse:drag",
    #         "startX": _px(act.start[0]),
    #         "startY": _px(act.start[1]),
    #         "endX":   _px(act.end[0]),
    #         "endY":   _px(act.end[1]),
    #         "button": _btn[MouseButton.LEFT],
    #         "modifiers": act.hold_keys or []
    #     })

    # def _type(self, act: TypeText) -> None:
    #     if act.xy:
    #         self._click(Click(xy=act.xy, element_description=act.element_description, num_clicks=1, button_type=MouseButton.LEFT, hold_keys=[]))
    #     # (可选) 全选+删除
    #     if act.overwrite:
    #         self._hotkey(Hotkey(keys=["ctrl", "a"]))
    #         self._do({"type": "keyboard:press", "key": "backspace"})

    #     # 输入正文
    #     self._do({"type": "keyboard:type", "text": act.text})

    #     if act.enter:
    #         self._do({"type": "keyboard:press", "key": "enter"})

    # def _scroll(self, act: Scroll) -> None:
    #     self._do({
    #         "type": "mouse:scroll",
    #         "x": _px(act.xy[0]),
    #         "y": _px(act.xy[1]),
    #         "scrollAxis": "VERTICAL" if act.vertical else "HORIZONTAL",
    #         "clicks": act.clicks
    #     })
    # def _hotkey(self, act: Hotkey) -> None:
    #     self._do({
    #         "type": "keyboard:hotkey",
    #         "keys": act.keys          # ["ctrl","c"] / ["command","space"]
    #     })
  
    # def _screenshot(self):
    #     """
    #     利用 /preview 端点；返回字典，含 base64 图片或公网 URL，
    #     交给上层决定保存还是解析。
    #     """
    #     return self._do({"type": "screenshot"})   # Lybic 允许把 preview 看作一种 action
    
