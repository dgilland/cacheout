from pathlib import Path

from mypy import api
import pytest

import cacheout
from cacheout import Cache

from .test_typing import MEMOIZERS, PUBLIC_IMPORTS


def test_memoized_method_binding_and_helpers():
    cache = Cache()

    class Service:
        @cache.memoize()
        def load(self, value: int, /, *, label: str) -> str:
            return f"{label}: {value}"

    service = Service()
    assert service.load(1, label="item") == "item: 1"
    assert Service.load(service, 1, label="item") == "item: 1"
    assert service.load.uncached(service, 1, label="item") == "item: 1"
    assert service.load.cache_key(service, 1, label="item") in cache
    assert service.load.invalidate() == 1


def test_memoized_method_signatures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "consumer.py"
    prefix = (
        PUBLIC_IMPORTS + "from typing import Hashable\nfrom typing_extensions import assert_type\n"
    )
    classes = "\n".join(
        f"""
class Service_{i}:
    @{memoizer}()
    def load(self, value: int, /, *, label: str) -> str:
        return f"{{label}}: {{value}}"

    @{memoizer}()
    async def async_load(self, value: int, /, *, label: str) -> str:
        return self.load(value, label=label)

service_{i} = Service_{i}()
"""
        for i, memoizer in enumerate(MEMOIZERS)
    )
    checks = "\n".join(
        f"""
assert_type(service_{i}.load(1, label="item"), str)
assert_type(Service_{i}.load(service_{i}, 1, label="item"), str)
assert_type(service_{i}.load.uncached(service_{i}, 1, label="item"), str)
assert_type(service_{i}.load.cache_key(service_{i}, 1, label="item"), Hashable)
assert_type(service_{i}.load.cache, Cache)
assert_type(service_{i}.load.invalidate(), int)

async def check_{i}() -> None:
    assert_type(await service_{i}.async_load(1, label="item"), str)
    assert_type(await Service_{i}.async_load(service_{i}, 1, label="item"), str)
    assert_type(await service_{i}.async_load.uncached(service_{i}, 1, label="item"), str)
    assert_type(service_{i}.async_load.cache_key(service_{i}, 1, label="item"), Hashable)
"""
        for i in range(len(MEMOIZERS))
    )
    source.write_text(prefix + classes + checks, encoding="utf-8")
    config = tmp_path / "mypy.ini"
    package_root = Path(cacheout.__file__).resolve().parent.parent
    config.write_text(f"[mypy]\nstrict = True\nmypy_path = {package_root}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MYPYPATH", raising=False)
    arguments = [
        "--config-file",
        str(config),
        "--no-incremental",
        "--follow-untyped-imports",
        "--cache-dir",
        str(tmp_path / "cache"),
        str(source),
    ]
    output, errors, status = api.run(arguments)
    assert status == 0, output + errors

    calls = [
        call
        for i in range(len(MEMOIZERS))
        for call in (
            f'service_{i}.load("wrong", label="item")',
            f"service_{i}.load(1)",
            f'service_{i}.load(value=1, label="item")',
            f'service_{i}.load.uncached(service_{i}, "wrong", label="item")',
            f'service_{i}.load.cache_key(service_{i}, "wrong", label="item")',
            f'service_{i}.load.uncached(1, label="item")',
            f'service_{i}.load.cache_key(1, label="item")',
        )
    ]
    source.write_text(prefix + classes + "\n" + "\n".join(calls), encoding="utf-8")
    output, errors, status = api.run(arguments)
    assert status == 1, output + errors
    assert errors == ""
    first_line = (prefix + classes + "\n").count("\n") + 1
    for line in range(first_line, first_line + len(calls)):
        assert f"consumer.py:{line}: error:" in output, output
