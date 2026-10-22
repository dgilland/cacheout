from pathlib import Path

from mypy import api
import pytest

from cacheout import Cache, CacheManager, CacheStats


MEMOIZERS = (
    "Cache().memoize",
    "memoize",
    "fifo_memoize",
    "lifo_memoize",
    "lfu_memoize",
    "lru_memoize",
    "mru_memoize",
    "rr_memoize",
)
PUBLIC_IMPORTS = """
from cacheout import (
    UNSET, Cache, CacheManager, CacheStats, CacheStatsTracker, RemovalCause,
    FIFOCache, LFUCache, LIFOCache, LRUCache, MRUCache, RRCache,
    fifo_memoize, lfu_memoize, lifo_memoize, lru_memoize, memoize,
    mru_memoize, rr_memoize,
)
"""


SUPPORTED_CALLS = """
from re import compile as compile_pattern

def factory() -> Cache:
    return Cache()

def supported_calls() -> None:
    cache = Cache(maxsize=None)
    string_keys: list[str] = ["key"]
    integer_keys: list[int] = [1]
    cache.get_many(string_keys)
    cache.delete_many(string_keys)
    cache.get_many(integer_keys)
    cache.delete_many(integer_keys)
    cache.get_many("key*")
    cache.get_many(compile_pattern("key.*"))
    cache.get_many(lambda key: key == "key")
    CacheManager({"named": {}}, cache_class=factory)
    CacheManager(cache_class=FIFOCache)
    snapshot: CacheStats = CacheStats().copy()
"""


def test_supported_calls():
    cache = Cache(maxsize=None)
    cache.set("key", 1)
    keys: list[str] = ["key"]
    assert cache.get_many(keys) == {"key": 1}
    assert cache.delete_many(keys) == 1

    def factory() -> Cache:
        return Cache()

    manager = CacheManager({"named": {}}, cache_class=factory)
    assert isinstance(manager["named"], Cache)
    stats = CacheStats(hit_count=1)
    assert stats.copy() == stats
    assert stats.copy() is not stats


def test_public_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "consumer.py"
    source.write_text(
        PUBLIC_IMPORTS
        + SUPPORTED_CALLS
        + "\ndef function(value: int) -> int:\n    return value\n\n"
        + "\n".join(f"reveal_type({name}()(function).cache_key(1))" for name in MEMOIZERS)
        + "\n"
        + "\n".join(f"{name}(maxsize=None)(function)" for name in MEMOIZERS[1:]),
        encoding="utf-8",
    )
    config = tmp_path / "mypy.ini"
    config.write_text("[mypy]\nstrict = True\n", encoding="utf-8")
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
    assert output.count('note: Revealed type is "str"') == len(MEMOIZERS)

    prefix = (
        PUBLIC_IMPORTS
        + "\ndef wrong_factory() -> int:\n    return 1\nbad_keys: list[list[int]] = []\n"
    )
    calls = [
        *(f'{name}(typed="wrong")' for name in MEMOIZERS),
        'Cache(maxsize="wrong")',
        *(f'{name}(maxsize="wrong")' for name in MEMOIZERS[1:]),
        "Cache().get_many(bad_keys)",
        "Cache().delete_many(bad_keys)",
        "CacheManager(cache_class=wrong_factory)",
    ]
    source.write_text(prefix + "\n".join(calls), encoding="utf-8")
    output, errors, status = api.run(arguments)
    assert status == 1, output + errors
    assert errors == ""
    assert output.count("[arg-type]") == len(calls), output
    assert output.count("error:") == len(calls), output
    assert output.count('Argument "typed"') == len(MEMOIZERS), output
    assert output.count('Argument "maxsize"') == len(MEMOIZERS), output
    first_line = prefix.count("\n") + 1
    for line in range(first_line, first_line + len(calls)):
        assert f"consumer.py:{line}: error:" in output, output


def test_memoized_signatures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "consumer.py"
    prefix = (
        PUBLIC_IMPORTS
        + """
from typing_extensions import assert_type

def function(value: int, /, *, label: str) -> str:
    return f"{label}: {value}"

async def coroutine(value: int, /, *, label: str) -> str:
    return function(value, label=label)
"""
    )
    bindings = "\n".join(
        f"sync_{i} = {name}()(function)\nasync_{i} = {name}()(coroutine)"
        for i, name in enumerate(MEMOIZERS)
    )
    checks = "\n".join(
        f"""
assert_type(sync_{i}(1, label="item"), str)
assert_type(sync_{i}.uncached(1, label="item"), str)
assert_type(sync_{i}.cache_key(1, label="item"), str)
assert_type(sync_{i}.cache, Cache)

async def check_{i}() -> None:
    assert_type(await async_{i}(1, label="item"), str)
    assert_type(await async_{i}.uncached(1, label="item"), str)
    assert_type(async_{i}.cache_key(1, label="item"), str)
"""
        for i in range(len(MEMOIZERS))
    )
    source.write_text(prefix + bindings + checks, encoding="utf-8")
    config = tmp_path / "mypy.ini"
    config.write_text("[mypy]\nstrict = True\n", encoding="utf-8")
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
            f'sync_{i}("wrong", label="item")',
            f"sync_{i}(1)",
            f'sync_{i}(value=1, label="item")',
            f'sync_{i}.uncached("wrong", label="item")',
            f'sync_{i}.cache_key("wrong", label="item")',
        )
    ]
    source.write_text(prefix + bindings + "\n" + "\n".join(calls), encoding="utf-8")
    output, errors, status = api.run(arguments)
    assert status == 1, output + errors
    assert errors == ""
    assert output.count("error:") == len(calls), output
    first_line = (prefix + bindings + "\n").count("\n") + 1
    for line in range(first_line, first_line + len(calls)):
        assert f"consumer.py:{line}: error:" in output, output
