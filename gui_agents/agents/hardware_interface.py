from __future__ import annotations

from gui_agents.agents.Backend.Backend import Backend
from gui_agents.agents.Backend.ADBBackend import ADBBackend
from gui_agents.agents.Backend.LybicBackend import LybicBackend
try:
    from gui_agents.agents.Backend.PyAutoGUIBackend import PyAutoGUIBackend
except ImportError:
    PyAutoGUIBackend = None
    pass
# from gui_agents.agents.Backend.PyAutoGUIVMwareBackend import PyAutoGUIVMwareBackend
"""hardware_interface.py  ▸  Execute Action objects on real devices / emulators
===============================================================================
This module is the *single entry point* that upper‑layer planners / executors
use to perform UI operations.  It is deliberately thin:

*   Accepts one `Action` **or** a `List[Action]` (defined in *actions.py*).
*   Delegates to a concrete *Backend* which knows how to translate the `Action`
    into platform‑specific calls (PyAutoGUI, ADB, Lybic cloud device, …).
*   Performs minimal capability checks + error propagation.

The default backend implemented here is **PyAutoGUIBackend**.  
Available backends: **ADBBackend**, **LybicBackend**, and **PyAutoGUIVMwareBackend**.

--------------------------------------------------------------------------
Quick usage
--------------------------------------------------------------------------
```python
from actions import Click
from hardware_interface import HardwareInterface

hwi = HardwareInterface(backend="pyautogui")
# Or use Lybic SDK backend
hwi_lybic = HardwareInterface(backend="lybic_sdk")

# Single action
hwi.dispatch(Click(xy=(960, 540)))

# Batch
plan = [Click(xy=(100,200)), Click(xy=(300,400))]
hwi.dispatch(plan)

# actionDict
hwi.dispatchDict({"type": "Click", "xy": [200, 300]})

```
"""

from typing import List, Type, Dict, Set, Union

# Import your Action primitives
from gui_agents.agents.Action import (
    Action,
    Screenshot,
)

__all__ = [
    "HardwareInterface",
    "Backend",
    "PyAutoGUIBackend",
    "ADBBackend",
    "LybicBackend",
   # "PyAutoGUIVMwareBackend",
]



# ---------------------------------------------------------------------------
# Facade – single entry point
# ---------------------------------------------------------------------------
class HardwareInterface:
    """High‑level facade that routes Action objects to a chosen backend."""

    BACKEND_MAP: Dict[str, Type[Backend]] = {
        "pyautogui": PyAutoGUIBackend,
        "adb": ADBBackend,
        "lybic": LybicBackend,
    }
    if PyAutoGUIBackend is not None:
        BACKEND_MAP["pyautogui_vmware"] = PyAutoGUIBackend

    # ------------------------------------------------------------------
    def __init__(self, backend: str | Backend = "pyautogui", **backend_kwargs):
        if isinstance(backend, Backend):
            self.backend: Backend = backend
        else:
            key = backend.lower()
            if key not in self.BACKEND_MAP:
                raise ValueError(f"Unsupported backend '{backend}'. Available: {list(self.BACKEND_MAP)}")
            
            # For GUI backends, provide helpful error message in headless environments
            if key in ["pyautogui", "pyautogui_vmware"]:
                import os
                if os.name == 'posix' and not os.environ.get('DISPLAY'):
                    raise RuntimeError(
                        f"Cannot create '{backend}' backend: No DISPLAY environment variable found. "
                        f"This typically occurs in headless/containerized environments. "
                        f"Consider using 'lybic' or 'adb' backend instead."
                    )
            
            self.backend = self.BACKEND_MAP[key](**backend_kwargs)

    # ------------------------------------------------------------------
    def dispatch(self, actions: Action | List[Action]):
        """Execute one or multiple actions *in order*.

        Args:
            actions: `Action` instance or list thereof.
        """
        if isinstance(actions, Action):
            actions = [actions]

        for act in actions:
            # 特殊处理Memorize动作，不传递给后端执行
            if type(act).__name__ == "Memorize":
                return None
            if not self.backend.supports(type(act)):
                raise NotImplementedError(
                    f"{type(act).__name__} is not supported by backend {self.backend.__class__.__name__}"
                )
            if (not isinstance(actions, list)) or (len(actions)==1):
                return self.backend.execute(act)
            else:
                self.backend.execute(act)

    def dispatchDict(self, actionDict: Dict):
        """Execute one  actions *in order*.

        Args:
            actionDict: `Action` instance or list thereof.
        """
        """
        Convenience helper – accept JSON-style dict(s) instead of Action objects.

        Parameters
        ----------
        payload : Dict | List[Dict]
            - Dict:  single action, e.g. {"type": "Click", "xy": [100,200], ...}
            - List:  sequence of actions in the above format
        """
        if isinstance(actionDict, list):
            actions = [Action.from_dict(item) for item in actionDict]
        else:
            actions = Action.from_dict(actionDict)

        return self.dispatch(actions)
