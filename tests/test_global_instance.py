# pytest -s tests/test_global_instance.py
from pathlib import Path
import json
import pytest
from gui_agents.agents.global_state import GlobalState




# ---------- 辅助函数：为测试构建一个干净的 GlobalInstance ----------
def build_store(tmp_path: Path) -> GlobalState:
    """
    在 pytest 的临时目录 tmp_path 下创建全套文件，返回 GlobalInstance 实例。
    其它字段即便本次用不到，也占个位以免初始化报错。
    """
    return GlobalState(
        screenshot_dir=tmp_path / "screens",
        tu_path=tmp_path / "tu.json",
        search_query_path=tmp_path / "search_query.json",
        failed_subtasks_path=tmp_path / "failed_subtasks.json",
        completed_subtasks_path=tmp_path / "completed_subtasks.json",
        remaining_subtasks_path=tmp_path / "remaining_subtasks.json",
        termination_flag_path=tmp_path / "termination_flag.json",
        running_state_path=tmp_path / "running_state.json",
    )

# ---------- 真正的测试用例 ----------
def test_tu_roundtrip(tmp_path: Path):
    """
    1. set_Tu 写入指令
    2. get_Tu 读回指令
    3. 校验磁盘文件内容
    """
    store = build_store(tmp_path)

    content = "打开微信，给张三发送：今晚 8 点见"
    store.set_Tu(content)

    # 输出路径
    tu_file = tmp_path / "tu.json"
    print("TU FILE PATH:", tu_file)

    # 读回
    assert store.get_Tu() == content

    # 额外：校验 JSON 文件确实是 {"instruction": "..."} 结构
    tu_json = json.loads((tmp_path / "tu.json").read_text(encoding="utf-8"))
    assert tu_json == {"instruction": content}
