"""Project version information.
"""

from pkg_resources import get_distribution, DistributionNotFound


try:
    __version__ = get_distribution(__name__.split('.')[0]).version
except DistributionNotFound:  # pragma: no cover
    # Package is not installed.
    __version__ = None
