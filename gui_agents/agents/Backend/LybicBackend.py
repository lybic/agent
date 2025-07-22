# ---------------------------------------------------------------------------
# 3) Cloud desktop / custom device backend (Lybic)
# https://lybic.ai/docs/api/executeComputerUseAction
# ---------------------------------------------------------------------------
from typing import Dict
from gui_agents.agents.Action import (
    Action,
    Click,
    DoubleClick,
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
from io import BytesIO
from PIL import Image


log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  helper: mapping enums / units → lybic spec
# ---------------------------------------------------------------------------
def _px(v: int) -> Dict[str, Any]:
    return {"type": "px", "value": v}




class LybicBackend(Backend):
    _supported = {Click, DoubleClick, Drag, TypeText, Scroll, Hotkey,
                   Wait, Screenshot }

    # ---------- ctor ----------
    def __init__(self, 
                 api_key: str = 'lysk-NxXUpGKgvtQwQMUjZroRQtQYAVOBoXjfPTiXxaTlOzOLjCvwvWjnJBcMLnLfEsaI', 
                 org_id: str = 'ORG-01K0NFM1AK8RT8GVJ6TN7PPXR6', 
                 *,
                 base_url="https://api.lybic.cn",
                 sandbox_opts: Optional[Dict[str, Any]] = None,
                 max_retries: int = 2,
                 **kwargs
                ):
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
        elif isinstance(action, DoubleClick):         self._doubleClick(action)
        elif isinstance(action, Drag):         self._drag(action)
        elif isinstance(action, TypeText):     self._type(action)
        elif isinstance(action, Scroll):       self._scroll(action)
        elif isinstance(action, Hotkey):       self._hotkey(action)
        elif isinstance(action, Screenshot):   return self._screenshot()   # type: ignore
        elif isinstance(action, Wait):         time.sleep(action.duration)

    # ---------- internal helpers ----------
    def _do(self, lybic_action: Dict[str, Any]):
        """Send **one** action; centralised retries + error mapping."""
        async def _send():
            act_type = lybic_action.get("type", "").lower()
            if act_type in {"screenshot", "system:preview"}:
                # /preview 不需要 action payload
                res =  await self.client.preview()
                return res
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
        # 超过重试次数
        raise RuntimeError(f"Lybic exec_action failed: {exc}") from exc

    def _click(self, act: Click):
        self._do({
            "type": "mouse:click",
            "x": _px(act.x),
            "y": _px(act.y),
            "button": act.button,
            "holdKey": "+".join(act.holdKey)
        })

    def _doubleClick(self, act: DoubleClick):
        self._do({
            "type": "mouse:doubleClick",
            "x": _px(act.x),
            "y": _px(act.y),
            "button": act.button,
            "holdKey": "+".join(act.holdKey)
        })
    
    def _drag(self, act: Drag) -> None:
        self._do({
            "type": "mouse:drag",
            "startX": _px(act.startX),
            "startY": _px(act.startY),
            "endX":   _px(act.endX),
            "endY":   _px(act.endY),
            # "button":
            "holdKey": "+".join(act.holdKey) or []
        })

    def _type(self, act: TypeText) -> None:
        # 输入正文
        self._do(
            {"type": "keyboard:type", "content": act.text}
        )

    def _scroll(self, act: Scroll) -> None:
        self._do({
            "type": "mouse:scroll",
            "x": _px(act.x),
            "y": _px(act.y),
            "stepVertical": act.stepVertical,
            "stepHorizontal": act.stepHorizontal
        })
    
    def _hotkey(self, act: Hotkey) -> None:
        self._do({
            "type": "keyboard:hotkey",
            "keys": "+".join(act.keys),          # ["ctrl","c"] / ["command","space"]
            "duration": act.duration
        })
  
    def _screenshot(self):
        """
        调 /preview ➜ 得到 webp URL ➜ 下载为 bytes ➜ 交给 Pillow 打开
        最终返回 `PIL.Image.Image`，其 .info 里带 cursorPosition 元数据。
        """
        # 1. 让 Lybic 截图，返回 {"screenShot": "...webp", "cursorPosition": {...}}
        meta = self._do({"type": "screenshot"})
        url  = meta.get("screenShot")
        if not url:
            raise RuntimeError("Lybic 返回缺少 'screenShot' 字段")

        # 2. 下载 webp
        async def _fetch():
            r = await self.client.http.get(url, follow_redirects=True)
            r.raise_for_status()
            return r.content
        webp_bytes: bytes = self.loop.run_until_complete(_fetch())

        # 3. 交给 Pillow 打开（Pillow ≥8.0 默认支持 WebP；若无则需 apt-get install libwebp）
        img = Image.open(BytesIO(webp_bytes))

        # 4. 把光标信息塞进 image.info 方便调用方使用
        if isinstance(meta.get("cursorPosition"), dict):
            img.info["cursorPosition"] = meta["cursorPosition"]

        # 5. 可选：统一转成 RGBA / PNG 内存格式（需求不同可删）
        # img = img.convert("RGBA")
        # print("_screenshot", img, meta)

        return img
    
