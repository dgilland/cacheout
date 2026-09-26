"""
This module provides the CLI interface for invoke tasks.

All tasks can be executed from this file's directory using:

$ inv <task>

Where <task> is a function defined below with the @task decorator.
"""

from functools import partial
import os

from invoke import Context, Exit, UnexpectedExit, run as _run, task


PACKAGE_NAME = "cacheout"
PACKAGE_SOURCE = f"src/{PACKAGE_NAME}"
TEST_TARGETS = f"{PACKAGE_SOURCE} tests"
LINT_TARGETS = f"{TEST_TARGETS} tasks.py"
EXIT_EXCEPTIONS = (Exit, UnexpectedExit, SystemExit)


# Set pyt=True to enable colored output when available.
run = partial(_run, pty=True)


@task()
def fmt(ctx: Context, target: str = "", quiet: bool = False) -> None:
    """Autoformat code and docstrings."""
    if not quiet:
        print("Running ruff format")
    ruff_format(ctx, target, quiet=quiet)

    if not quiet:
        print("Running ruff lint fixes")
    ruff_fix(ctx, target, quiet=quiet)


@task()
def ruff_format(ctx: Context, target: str = "", quiet: bool = False) -> None:
    """Autoformat code and docstrings using ruff."""
    run(f"ruff format {target}", hide=quiet)


@task()
def ruff_fix(ctx: Context, target: str = "", quiet: bool = False) -> None:
    """Autofix fixable lint issues using ruff."""
    run(f"ruff check {target} --fix", hide=quiet)


@task()
def ruff_format_check(ctx: Context) -> None:
    """Check code for static errors using pylint."""
    run("ruff format --check")


@task()
def ruff_check(ctx: Context) -> None:
    """Check code for static errors using pylint."""
    run("ruff check")


@task()
def mypy(ctx: Context) -> None:
    """Check code using mypy type checker."""
    run(f"mypy {LINT_TARGETS}")


@task()
def lint(ctx: Context) -> None:
    """Run linters."""
    linters = {
        "ruff-format-check": ruff_format_check,
        "ruff-check": ruff_check,
        "mypy": mypy,
    }

    failures = []

    print(f"Preparing to run linters: {', '.join(linters)}\n")

    for name, linter in linters.items():
        print(f"Running {name}")
        try:
            linter(ctx)
        except EXIT_EXCEPTIONS:
            failures.append(name)
            result = "FAILED"
        else:
            result = "PASSED"
        print(f"{result}\n")

    if failures:
        failed = ", ".join(failures)
        raise Exit(f"ERROR: linters failed: {failed}")


@task(help={"args": "Override default pytest arguments"})
def test(ctx: Context, args: str = f"{TEST_TARGETS} --cov={PACKAGE_NAME}"):
    """Run unit tests using pytest."""
    tox_env_site_packages_dir = os.getenv("TOX_ENV_SITE_PACKAGES_DIR")
    if tox_env_site_packages_dir:
        # Re-path package source to match tox env so that we generate proper coverage report.
        tox_env_pkg_src = os.path.join(tox_env_site_packages_dir, os.path.basename(PACKAGE_SOURCE))
        args = args.replace(PACKAGE_SOURCE, tox_env_pkg_src)

    run(f"pytest {args}")


@task()
def ci(ctx: Context) -> None:
    """Run linters and tests."""
    print("Building package")
    build(ctx)

    print("Building docs")
    docs(ctx)

    print("Checking linters")
    lint(ctx)

    print("Running unit tests")
    test(ctx)


@task()
def docs(ctx: Context, serve: bool = False, bind: str = "127.0.0.1", port: int = 8000) -> None:
    """Build docs."""
    run("rm -rf docs/_build")
    run("sphinx-build -q -W -b html docs docs/_build/html")

    if serve:
        print(f"Serving docs on {bind} port {port} (http://{bind}:{port}/) ...")
        run(f"python -m http.server -b {bind} --directory docs/_build/html {port}", hide=True)


@task()
def build(ctx: Context) -> None:
    """Build Python package."""
    run("rm -rf dist build docs/_build")
    run("python -m build")


@task
def clean(ctx):
    """Remove temporary files related to development."""
    run("find . -type f -name '*.py[cod]' -delete -o -type d -name __pycache__ -delete")
    run("rm -rf .tox .coverage .cache .pytest_cache **/.egg* **/*.egg* dist build .mypy_cache")


@task(pre=[build])
def release(ctx: Context) -> None:
    """Release Python package."""
    run("twine upload dist/*")
