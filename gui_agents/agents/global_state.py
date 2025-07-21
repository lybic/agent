# global_state.py
import json, os, time, logging, io
from pathlib import Path
from typing import List, Optional, Dict, Any

from PIL import Image

from gui_agents.utils.common_utils import Node

logger = logging.getLogger(__name__)

# ========= File Lock Tools =========
from contextlib import contextmanager
if os.name == "nt":
    import msvcrt, time as _t

    @contextmanager
    def locked(path: Path, mode: str):
        f = open(path, mode)
        try:
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    _t.sleep(0.01)
            yield f
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            f.close()
else:
    import fcntl

    @contextmanager
    def locked(path: Path, mode: str):
        f = open(path, mode)
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()

# ========= Node Encoding/Decoding =========
def node_to_dict(node: Node):
    if hasattr(node, "to_dict"):
        return node.to_dict() # type: ignore
    else:
        return vars(node)

def node_from_dict(d: dict) -> Node:
    if hasattr(Node, "from_dict"):
        return Node.from_dict(d)  # type: ignore
    return Node(**d)  # type: ignore

# ========= GlobalState =========
class GlobalState:
    """Centralized management for global state (screenshots / instructions / subtask lists, etc.) read and write"""

    def __init__(
        self,
        *,
        screenshot_dir: str,
        tu_path: str,
        search_query_path: str,
        completed_subtasks_path: str,
        failed_subtasks_path: str,
        remaining_subtasks_path: str,
        termination_flag_path: str,
        running_state_path: str,
        display_info_path: str = "",  # New parameter for storing display information
    ):
        self.screenshot_dir = Path(screenshot_dir)
        self.tu_path = Path(tu_path)
        self.search_query_path = Path(search_query_path)
        self.completed_subtasks_path = Path(completed_subtasks_path)
        self.failed_subtasks_path = Path(failed_subtasks_path)
        self.remaining_subtasks_path = Path(remaining_subtasks_path)
        self.termination_flag_path = Path(termination_flag_path)
        self.running_state_path = Path(running_state_path)
        
        # If display_info_path is not provided, create display.json in the same directory as running_state_path
        if not display_info_path:
            self.display_info_path = Path(os.path.join(self.running_state_path.parent, "display.json"))
        else:
            self.display_info_path = Path(display_info_path)

        # Ensure necessary directories / files exist
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        for p in [
            self.tu_path,
            self.search_query_path,
            self.completed_subtasks_path,
            self.failed_subtasks_path,
            self.remaining_subtasks_path,
            self.termination_flag_path,
            self.running_state_path,
            self.display_info_path,
        ]:
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("")

    # ---------- Common Private Tools ----------
    def _load_subtasks(self, path: Path) -> List[Node]:
        try:
            with locked(path, "r") as f:
                data = json.load(f)
            return [node_from_dict(d) for d in data]
        except Exception:
            return []

    def _save_subtasks(self, path: Path, nodes: List[Node]) -> None:
        tmp = path.with_suffix(".tmp")
        serialised = [node_to_dict(n) for n in nodes]
        with locked(tmp, "w") as f:
            json.dump(serialised, f, indent=2)
            f.flush(); os.fsync(f.fileno())
        tmp.replace(path)

    # ---------- Screenshot ----------
    def get_screenshot(self) -> Optional[bytes]:
        pngs = sorted(self.screenshot_dir.glob("*.png"))
        if not pngs:
            logger.warning("No screenshot found in %s", self.screenshot_dir)
            return None
        latest = pngs[-1]
        screenshot = Image.open(latest)
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return buf.getvalue()

    def set_screenshot(self, img: Image.Image) -> Path:
        ts = int(time.time() * 1000)
        out = self.screenshot_dir / f"{ts}.png"
        img.save(out)
        logger.debug("Screenshot saved to %s", out)
        return out
    
    def get_screen_size(self) -> List[int]:
        pngs = sorted(self.screenshot_dir.glob("*.png"))
        if not pngs:
            logger.warning("No screenshot found in %s, returning default size [1920, 1080]", self.screenshot_dir)
            return [1920, 1080]
        
        latest = pngs[-1]
        try:
            screenshot = Image.open(latest)
            width, height = screenshot.size
            logger.info("Current screen size from %s: [%d, %d]", latest.name, width, height)
            return [width, height]
        except Exception as e:
            logger.error("Failed to get screen size from %s: %s", latest, e)
            return [1920, 1080]
        

    # ---------- Tu ----------
    def get_Tu(self) -> str:
        try:
            with locked(self.tu_path, "r") as f:
                data = json.load(f)
            return data.get("instruction", "")
        except Exception:
            return ""

    def set_Tu(self, instruction: str) -> None:
        tmp = self.tu_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump({"instruction": instruction}, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        tmp.replace(self.tu_path)

    # ---------- search_query ----------
    def get_search_query(self) -> str:
        try:
            with locked(self.search_query_path, "r") as f:
                data = json.load(f)
            return data.get("query", "")
        except Exception:
            return ""

    def set_search_query(self, query: str) -> None:
        tmp = self.search_query_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump({"query": query}, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        tmp.replace(self.search_query_path)

    # ====== completed_subtasks ======
    def get_completed_subtasks(self) -> List[Node]:
        return self._load_subtasks(self.completed_subtasks_path)

    def set_completed_subtasks(self, nodes: List[Node]) -> None:
        self._save_subtasks(self.completed_subtasks_path, nodes)

    def add_completed_subtask(self, node: Node) -> None:
        lst = self.get_completed_subtasks()
        lst.append(node)
        self._save_subtasks(self.completed_subtasks_path, lst)

    # ====== failed_subtasks ======
    def get_failed_subtasks(self) -> List[Node]:
        return self._load_subtasks(self.failed_subtasks_path)

    def set_failed_subtasks(self, nodes: List[Node]) -> None:
        self._save_subtasks(self.failed_subtasks_path, nodes)

    def add_failed_subtask(self, node: Node) -> None:
        lst = self.get_failed_subtasks()
        lst.append(node)
        self._save_subtasks(self.failed_subtasks_path, lst)

    def get_latest_failed_subtask(self) -> Optional[Node]:
        lst = self.get_failed_subtasks()
        return lst[-1] if lst else None

    # ====== remaining_subtasks ======
    def get_remaining_subtasks(self) -> List[Node]:
        return self._load_subtasks(self.remaining_subtasks_path)

    def set_remaining_subtasks(self, nodes: List[Node]) -> None:
        self._save_subtasks(self.remaining_subtasks_path, nodes)

    def add_remaining_subtask(self, node: Node) -> None:
        lst = self.get_remaining_subtasks()
        lst.append(node)
        self._save_subtasks(self.remaining_subtasks_path, lst)

    # ---------- termination_flag ----------
    def get_termination_flag(self) -> str:
        try:
            with locked(self.termination_flag_path, "r") as f:
                data = json.load(f)
            return data or "not_terminated"
        except Exception:
            return "not_terminated"

    def set_termination_flag(self, flag: str) -> None:
        assert flag in {"terminated", "not_terminated"}
        tmp = self.termination_flag_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump(flag, f)
            f.flush(); os.fsync(f.fileno())
        tmp.replace(self.termination_flag_path)

    # ---------- running_state ----------
    def get_running_state(self) -> str:
        try:
            with locked(self.running_state_path, "r") as f:
                data = json.load(f)
            return data or "stopped"
        except Exception:
            return "stopped"

    def set_running_state(self, state: str) -> None:
        assert state in {"running", "stopped"}
        tmp = self.running_state_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump(state, f)
            f.flush(); os.fsync(f.fileno())
        tmp.replace(self.running_state_path)

    # ---------- High-level Wrappers ----------
    def get_obs_for_manager(self):
        return {
            "screenshot": self.get_screenshot(),
            "termination_flag": self.get_termination_flag(),
        }

    def get_obs_for_grounding(self):
        return {"screenshot": self.get_screenshot()}

    def get_obs_for_evaluator(self):
        return {
            "search_query": self.get_search_query(),
            "failed_subtasks": self.get_failed_subtasks(),
            "completed_subtasks": self.get_completed_subtasks(),
            "remaining_subtasks": self.get_remaining_subtasks(),
            "screenshot": self.get_screenshot(),
        }
        
    # ---------- Display Information Management ----------
    def get_display_info(self) -> Dict[str, Any]:
        """Get display information"""
        try:
            with locked(self.display_info_path, "r") as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except Exception as e:
            logger.warning(f"Failed to load display info: {e}")
            return {}
            
    def set_display_info(self, info: Dict[str, Any]) -> None:
        """Set display information (overwrite)"""
        tmp = self.display_info_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        tmp.replace(self.display_info_path)
        
    # ---------- New Unified Logging Method ----------
    def log_operation(self, module: str, operation: str, data: Dict[str, Any]) -> None:
        """
        Log operation information, organized by module and chronological order
        
        Args:
            module: Module name, such as 'manager', 'worker', 'grounding', etc.
            operation: Operation name, such as 'formulate_query', 'retrieve_knowledge', etc.
            data: Operation-related data, may include the following fields:
                - duration: Operation duration (seconds)
                - tokens: Token usage [input tokens, output tokens, total tokens]
                - cost: Cost information
                - content: Operation content or result
                - Other custom fields
        """
        info = self.get_display_info()
        
        # Ensure the module exists
        if "operations" not in info:
            info["operations"] = {}
            
        if module not in info["operations"]:
            info["operations"][module] = []
            
        # Normalize operation name, remove prefixes like "Manager.", "Worker.", etc.
        normalized_operation = operation
        for prefix in ["Manager.", "Worker.", "Hardware."]:
            if normalized_operation.startswith(prefix):
                normalized_operation = normalized_operation[len(prefix):]
                break
        
        # Find if there's an existing record for the same operation
        found = False
        for i, op in enumerate(info["operations"][module]):
            # Normalize existing operation name
            existing_op_name = op["operation"]
            for prefix in ["Manager.", "Worker.", "Hardware."]:
                if existing_op_name.startswith(prefix):
                    existing_op_name = existing_op_name[len(prefix):]
                    break
                    
            # If found the same operation and timestamp is close (within 5 seconds), merge the data
            if (existing_op_name == normalized_operation or 
                op["operation"] == operation) and \
                abs(op["timestamp"] - time.time()) < 5.0:
                # Merge data, keep original timestamp
                for key, value in data.items():
                    op[key] = value
                found = True
                break
        
        # If no matching operation found, create new record
        if not found:
            # Add timestamp and operation name
            operation_data = {
                "operation": operation,
                "timestamp": time.time(),
                **data
            }
            
            # Add to the operation list of the corresponding module
            info["operations"][module].append(operation_data)
        
        self.set_display_info(info)
