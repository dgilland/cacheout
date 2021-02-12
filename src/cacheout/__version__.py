"""Project version information."""

import typing as t

from pkg_resources import DistributionNotFound, get_distribution


__version__: t.Optional[str] = None
try:
    __version__ = get_distribution(__name__.split(".")[0]).version
except DistributionNotFound:  # pragma: no cover
    # Package is not installed.
    pass
