# ---------------------------------------------------------------------------
# 3) Cloud desktop / custom device backend (Lybic)
# https://lybic.ai/docs/api/executeComputerUseAction
# ---------------------------------------------------------------------------
from typing import Dict
from ..Action import (
    Action,
    Click,
    DoubleClick,
    Move,
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
    Screenshot,
    Memorize,
    # SetCellValues,
    # SwitchApplications,
    # Open
)

from .Backend import Backend
from ...lybic.lybic_client import LybicClient
import asyncio, httpx, time, logging
from typing import Dict, Any, List, Optional
from httpx import HTTPStatusError, TimeoutException
from io import BytesIO
from PIL import Image
import os

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  helper: mapping enums / units → lybic spec
# ---------------------------------------------------------------------------
def _px(v: int) -> Dict[str, Any]:
    return {"type": "px", "value": v}



class LybicBackend(Backend):
    # _supported = {Click, DoubleClick, Move, Drag, TypeText, Scroll, Hotkey,
    #                Wait, Screenshot, Memorize, SetCellValues, SwitchApplications, Open}
    _supported = {Click, DoubleClick, Move, Drag, TypeText, Scroll, Hotkey,
                   Wait, Screenshot, Memorize}

    # ---------- ctor ----------
    def __init__(self, 
                 api_key: str | None = None, 
                 org_id: str | None = None, 
                 *,
                 base_url: str | None = None,
                 sandbox_opts: Optional[Dict[str, Any]] = None,
                 max_retries: int = 2,
                 precreate_sid: str | None = None,
                 **kwargs
                ):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.api_key = api_key or os.getenv("LYBIC_API_KEY")
        self.org_id = org_id or os.getenv("LYBIC_ORG_ID")
        self.base_url = base_url or os.getenv("LYBIC_ENDPOINT_URL")
        self.precreate_sid = precreate_sid or os.getenv("LYBIC_PRECREATE_SID")

        self.client = LybicClient(self.api_key, self.base_url, self.org_id) # type: ignore
        self.max_retries = max_retries
        
        if self.precreate_sid is None:
            print("Creating sandbox...")
            max_life_seconds = int(os.getenv("LYBIC_MAX_LIFE_SECONDS", "3600"))
            self.loop.run_until_complete(
                self.client.create_sandbox(name="agent-run",
                                        maxLifeSeconds=max_life_seconds,
                                        **(sandbox_opts or {}))
            )

    # ---------- public sync API ----------
    def execute(self, action: Action):
        if not self.supports(type(action)):
            raise NotImplementedError(f"{type(action).__name__} unsupported")

        if   isinstance(action, Click):        self._click(action)
        elif isinstance(action, DoubleClick):         self._doubleClick(action)
        elif isinstance(action, Move):         self._move(action)
        elif isinstance(action, Drag):         self._drag(action)
        elif isinstance(action, TypeText):     self._type(action)
        elif isinstance(action, Scroll):       self._scroll(action)
        elif isinstance(action, Hotkey):       self._hotkey(action)
        elif isinstance(action, Screenshot):   return self._screenshot()   # type: ignore
        elif isinstance(action, Wait):         time.sleep(action.duration if action.duration is not None else 0.2)
        elif isinstance(action, Memorize):     log.info(f"Memorizing information: {action.information}")  # Abstract action, no hardware execution needed
        # elif isinstance(action, SetCellValues): self._set_cell_values(action)
        # elif isinstance(action, SwitchApplications): self._switch_applications(action)
        # elif isinstance(action, Open):         self._open(action)

    # ---------- internal helpers ----------
    def _do(self, lybic_action: Dict[str, Any]):
        """Send **one** action; centralised retries + error mapping."""
        async def _send():
            act_type = lybic_action.get("type", "").lower()
            if act_type in {"screenshot", "system:preview"}:
                # /preview doesn't need action payload
                if self.precreate_sid is not None:
                    res =  await self.client.preview(self.precreate_sid)
                else:
                    res =  await self.client.preview()
                return res
            else:
                if self.precreate_sid is not None:
                    res =  await self.client.exec_action(action=lybic_action, sid=self.precreate_sid)
                else:
                    res =  await self.client.exec_action(action=lybic_action)
                return res

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
    
    def _move(self, act: Move) -> None:
        self._do({
            "type": "mouse:move",
            "x": _px(act.x),
            "y": _px(act.y),
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
            "holdKey": "+".join(act.holdKey)
        })

    def _type(self, act: TypeText) -> None:
        # 1) Optional focus
        if act.x is not None and act.y is not None:
            self._do({
                "type": "mouse:click",
                "x": _px(act.x),
                "y": _px(act.y),
                "button": 1,
                "holdKey": ""
            })
        # 2) Optional overwrite
        if act.overwrite:
            # select all + backspace via hotkeys
            self._do({
                "type": "keyboard:hotkey",
                "keys": "+".join(["ctrl", "a"]),
                "duration": 80
            })
            self._do({
                "type": "keyboard:press",
                "key": "backspace"
            })
        # 3) Type content
        self._do({"type": "keyboard:type", "content": act.text})
        # 4) Optional enter
        if act.enter:
            self._do({
                "type": "keyboard:press",
                "key": "enter"
            })

    def _scroll(self, act: Scroll) -> None:
        if act.stepVertical is None:
            self._do({
                "type": "mouse:scroll",
                "x": _px(act.x),
                "y": _px(act.y),
                "stepVertical": 0,
                "stepHorizontal": act.stepHorizontal
            })
        elif act.stepHorizontal is None:
            self._do({
                "type": "mouse:scroll",
                "x": _px(act.x),
                "y": _px(act.y),
                "stepVertical": act.stepVertical,
                "stepHorizontal": 0
            })
        else:
            self._do({
                "type": "mouse:scroll",
                "x": _px(act.x),
                "y": _px(act.y),
                "stepVertical": act.stepVertical,
                "stepHorizontal": act.stepHorizontal
            })
    
    def _hotkey(self, act: Hotkey) -> None:
        if act.duration is None:
            duration = 80
        elif  1 <= act.duration <= 5000:
            duration = act.duration
        else:
            raise ValueError("Hotkey duration must be between 1 and 1000")

        self._do({
            "type": "keyboard:hotkey",
            "keys": "+".join(act.keys),          # ["ctrl","c"] / ["command","space"]
            "duration": duration
        })
  
    def _screenshot(self):
        """
        Call /preview ➜ Get webp URL ➜ Download as bytes ➜ Open with Pillow
        Finally returns `PIL.Image.Image`, with cursorPosition metadata in its .info.
        """
        # 1. Take screenshot with Lybic, returns {"screenShot": "...webp", "cursorPosition": {...}}
        meta = self._do({"type": "screenshot"})
        url  = meta.get("screenShot")
        if not url:
            raise RuntimeError("Lybic response missing 'screenShot' field")

        # 2. Download webp
        async def _fetch():
            r = await self.client.http.get(url, follow_redirects=True)
            r.raise_for_status()
            return r.content
        webp_bytes: bytes = self.loop.run_until_complete(_fetch())

        # 3. Open with Pillow (Pillow ≥8.0 supports WebP by default; otherwise need apt-get install libwebp)
        img = Image.open(BytesIO(webp_bytes))

        # 4. Insert cursor information into image.info for caller's use
        if isinstance(meta.get("cursorPosition"), dict):
            img.info["cursorPosition"] = meta["cursorPosition"]

        # 5. Optional: Convert to RGBA / PNG memory format (can be deleted if requirements differ)
        # img = img.convert("RGBA")
        # print("_screenshot", img, meta)

        return img

    # def _set_cell_values(self, act: SetCellValues) -> None:
    #     """Set cell values in spreadsheet via Lybic cloud backend"""
    #     # Convert cell values to Lybic format
    #     cell_data = []
    #     for cell_ref, value in act.cell_values.items():
    #         cell_data.append({
    #             "cell": cell_ref,
    #             "value": value,
    #             "app": act.app_name,
    #             "sheet": act.sheet_name
    #         })
        
    #     self._do({
    #         "type": "spreadsheet:set_cells",
    #         "cells": cell_data
    #     })

    # def _switch_applications(self, act: SwitchApplications) -> None:
    #     """Switch to a different application via Lybic cloud backend"""
    #     self._do({
    #         "type": "system:switch_app",
    #         "app_name": act.app_code
    #     })

    # def _open(self, act: Open) -> None:
    #     """Open an application or file via Lybic cloud backend"""
    #     self._do({
    #         "type": "system:open",
    #         "target": act.app_or_filename
    #     })
    
