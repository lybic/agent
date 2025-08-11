import pytest
from concurrent.futures import ThreadPoolExecutor

from gui_agents.store.registry import Registry

@pytest.fixture(autouse=True)
def clean_registry():
    """Each test clears the Registry to ensure isolation."""
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
    Registry.register("svc", second)      # Register again with the same name -> override
    assert Registry.get("svc") is second

def test_thread_safety_under_simple_race():
    """Concurrent scenario: two threads write the same key almost at the same time, the final result is predictable."""
    a = object()
    b = object()

    def task(obj):
        Registry.register("key", obj)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pool.submit(task, a)
        pool.submit(task, b)

    # After both threads end, the key must exist, and the value must be in {a,b}
    assert Registry.get("key") in {a, b}
