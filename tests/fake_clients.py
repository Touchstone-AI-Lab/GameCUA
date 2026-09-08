from types import SimpleNamespace


def plain(value):
    if callable(getattr(value, "model_dump", None)):
        return value.model_dump()
    if isinstance(value, SimpleNamespace):
        return {k: plain(v) for k, v in vars(value).items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


class SdkShapedClient:
    def __init__(self, create):
        self.create = create

    def complete(self, body, *, timeout=120, cancel=None):
        return plain(self.create(**body, timeout=timeout, cancel=cancel))

    def close(self):
        pass
