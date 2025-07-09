class Registry:
    _services = {}
    @classmethod
    def register(cls, name, obj):
        cls._services[name] = obj
    @classmethod
    def get(cls, name):
        return cls._services[name]
