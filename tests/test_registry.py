import pytest
from concurrent.futures import ThreadPoolExecutor

from gui_agents.store.registry import Registry

@pytest.fixture(autouse=True)
def clean_registry():
    """每个测试前后都清空 Registry，保证隔离。"""
    Registry.clear()
    yield
    Registry.clear()

def test_register_and_get():
    obj = {"foo": 123}
    Registry.register("store", obj)
    assert Registry.get("store") is obj

def test_get_unregistered_should_raise():
    with pytest.raises(KeyError):
        Registry.get("not_exist")

def test_override_existing_registration():
    first = object()
    second = object()

    Registry.register("svc", first)
    Registry.register("svc", second)      # 再次注册同名 -> 覆盖
    assert Registry.get("svc") is second

def test_thread_safety_under_simple_race():
    """并发场景：两个线程几乎同时写同一个 key，最后结果可预测。"""
    a = object()
    b = object()

    def task(obj):
        Registry.register("key", obj)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(task, a)
        pool.submit(task, b)

    # 两个线程都结束后，key 至少得存在，且 value 属于 {a,b}
    assert Registry.get("key") in {a, b}
