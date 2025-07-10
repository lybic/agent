# gui_agents/s2/store/registry.py

# 使用方法，在任意文件中通过Registry.get获取
# from gui_agents.s2.store.registry import Registry
# GlobalStateStore = Registry.get("GlobalStateStore")

class Registry:
    _services: dict[str, object] = {}

    @classmethod
    def register(cls, name: str, obj: object):
        cls._services[name] = obj

    @classmethod
    def get(cls, name: str) -> object:
        if name not in cls._services:
            raise KeyError(f"{name!r} not registered in Registry")
        return cls._services[name]

    @classmethod
    def clear(cls):
        cls._services.clear()
