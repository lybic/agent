# global_state.py
import json, os, time, logging
from pathlib import Path
from typing import List, Optional

from PIL import Image

from gui_agents.s2.utils.common_utils import Node

logger = logging.getLogger(__name__)


# ========= 文件锁工具 =========
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


# ========= Node 编解码 =========
def node_to_dict(node: Node):
    return node.to_dict() if hasattr(node, "to_dict") else vars(node)


def node_from_dict(d: dict) -> Node:
    if hasattr(Node, "from_dict"):
        return Node.from_dict(d)  # type: ignore
    return Node(**d)  # type: ignore


# ========= GlobalState =========
class GlobalState:
    """集中管理全局状态的读写"""

    def __init__(
        self,
        *,
        screenshot_dir: str,
        tu_path: str,
        search_query_path: str,
        completed_subtask_path: str,
        termination_flag_path: str,
        running_state_path: str,
        failed_subtask_path: str,      # ★ 新增
        remaining_subtask_path: str,   # ★ 新增
    ):
        self.screenshot_dir = Path(screenshot_dir)
        self.tu_path = Path(tu_path)
        self.search_query_path = Path(search_query_path)
        self.completed_subtask_path = Path(completed_subtask_path)
        self.termination_flag_path = Path(termination_flag_path)
        self.running_state_path = Path(running_state_path)
        self.failed_subtask_path = Path(failed_subtask_path)
        self.remaining_subtask_path = Path(remaining_subtask_path)

        # 保证必要目录存在
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        for p in [
            self.tu_path,
            self.search_query_path,
            self.failed_subtask_path,
            self.remaining_subtask_path,
            self.completed_subtask_path,
            self.termination_flag_path,
            self.running_state_path,
        ]:
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("")

    # ---------- Screenshot ----------
    def get_screenshot(self) -> Optional[Image.Image]:
        pngs = sorted(self.screenshot_dir.glob("*.png"))
        if not pngs:
            logger.warning("No screenshot found in %s", self.screenshot_dir)
            return None
        latest = pngs[-1]
        return Image.open(latest)

    def set_screenshot(self, img: Image.Image) -> Path:
        ts = int(time.time() * 1000)
        out = self.screenshot_dir / f"{ts}.png"
        img.save(out)
        logger.debug("Screenshot saved to %s", out)
        return out

    # ---------- Tu ----------
    def get_Tu(self) -> str:
        try:
            with locked(self.tu_path, "r") as f:
                data = json.load(f) if f.readable() and f.tell() == 0 else json.load(f)
            return data.get("instruction", "")
        except Exception:
            return ""

    def set_Tu(self, instruction: str):
        tmp = self.tu_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump({"instruction": instruction}, f)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.tu_path)

    # ---------- search_query ----------
    def get_search_query(self) -> str:
        try:
            with locked(self.search_query_path, "r") as f:
                data = json.load(f)
            return data.get("query", "")
        except Exception:
            return ""

    def set_search_query(self, query: str):
        tmp = self.search_query_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump({"query": query}, f)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.search_query_path)

    # ====== completed_subtask (rename 原 set/get_subtask) ======
    def get_completed_subtask(self) -> List[Node]:
        try:
            with locked(self.completed_subtask_path, "r") as f:
                data = json.load(f)
            return [node_from_dict(d) for d in data]
        except Exception:
            return []

    def set_completed_subtask(self, nodes: List[Node]):
        tmp = self.completed_subtask_path.with_suffix(".tmp")
        serialised = [node_to_dict(n) for n in nodes]
        with locked(tmp, "w") as f:
            json.dump(serialised, f, indent=2)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.completed_subtask_path)
    # ====== failed_subtask ======
    def get_failed_subtask(self) -> List[Node]:
        try:
            with locked(self.failed_subtask_path, "r") as f:
                data = json.load(f)
            return [node_from_dict(d) for d in data]
        except Exception:
            return []

    def set_failed_subtask(self, nodes: List[Node]):
        tmp = self.failed_subtask_path.with_suffix(".tmp")
        serialised = [node_to_dict(n) for n in nodes]
        with locked(tmp, "w") as f:
            json.dump(serialised, f, indent=2)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.failed_subtask_path)
    
    # ====== remaining_subtask ======
    def get_remaining_subtask(self) -> List[Node]:
        try:
            with locked(self.remaining_subtask_path, "r") as f:
                data = json.load(f)
            return [node_from_dict(d) for d in data]
        except Exception:
            return []

    def set_remaining_subtask(self, nodes: List[Node]):
        tmp = self.remaining_subtask_path.with_suffix(".tmp")
        serialised = [node_to_dict(n) for n in nodes]
        with locked(tmp, "w") as f:
            json.dump(serialised, f, indent=2)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.remaining_subtask_path)

    # ---------- termination_flag ----------
    def get_termination_flag(self) -> str:
        try:
            with locked(self.termination_flag_path, "r") as f:
                data = json.load(f)
            return data or "not_terminated"
        except Exception:
            return "not_terminated"

    def set_termination_flag(self, flag: str):
        assert flag in {"terminated", "not_terminated"}
        tmp = self.termination_flag_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump(flag, f)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.termination_flag_path)

    # ---------- running_state ----------
    def get_running_state(self) -> str:
        try:
            with locked(self.running_state_path, "r") as f:
                data = json.load(f)
            return data or "stopped"
        except Exception:
            return "stopped"

    def set_running_state(self, state: str):
        assert state in {"running", "stopped"}
        tmp = self.running_state_path.with_suffix(".tmp")
        with locked(tmp, "w") as f:
            json.dump(state, f)
            f.flush(), os.fsync(f.fileno())
        tmp.replace(self.running_state_path)

    # ---------- 高层封装 ----------
    def get_obs_for_manager(self):
        return {
            "Screenshot": self.get_screenshot(),
            "termination_flag": self.get_termination_flag(),
        }

    def get_obs_for_grounding(self):
        return {"Screenshot": self.get_screenshot()}

    def get_obs_for_evaluator(self):
        return {
            "search_query": self.get_search_query(),
            "failed_subtask": self.get_failed_subtask(),
            "completed_subtask": self.get_completed_subtask(),
            "remaining_subtask": self.get_remaining_subtask(),
            "Screenshot": self.get_screenshot(),
        }
