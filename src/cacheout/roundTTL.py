"""The roundTTL module provides the :class:`RoundTTL` class."""

import datetime
import math
import typing as t

from dateutil.relativedelta import relativedelta

from .cache import T_TTL


class RoundTTL:
    @staticmethod
    def round(
        key_start: str, delta: t.Dict[str, int], now: t.Optional[datetime.datetime] = None
    ) -> T_TTL:
        """
        Rounding the remaining TTL based on a specific period: every month / every day / every hour.

        / every 20 minutes of an hour ...

        :param key_start: Accepted values are 'year', 'month', week, 'day', 'hour', 'minute'
        :param delta: Any parameter for the function relativedelta
        :return: Number of seconds until expiration
        More info on relativedelta (https://dateutil.readthedocs.io/en/stable/relativedelta.html)
        """

        accepted_keys: t.Tuple[str, ...] = ("year", "month", "week", "day", "hour", "minute")
        if key_start not in accepted_keys:
            raise ValueError(f"keyStart must be on of the following values: {accepted_keys}")

        if now is None:
            now = datetime.datetime.now()

        # Init params to always have a correct date with year, month & day
        datetime_params: t.Dict[str, int] = {
            "month": 1,
            "day": 1,
        }

        if key_start == "week":
            datetime_params["year"] = now.year
            weekday = 0
            if "weekday" in delta:
                weekday = delta["weekday"]
                del delta["weekday"]
            time_start: datetime.datetime = datetime.datetime(
                **datetime_params  # type: ignore
            ) + relativedelta(weekday=weekday, weeks=-1)
        else:
            # Preparing the parameters of the datetime to get the beginning of the period.
            # For example, if we want to check every hour (key_start= 'hour'),
            # we need to get the datetime of the beginning of the current hour
            for key in ("year", "month", "day", "hour", "minute"):
                datetime_params[key] = getattr(now, key)
                if key == key_start:
                    break

            # Datetime we count from
            time_start: datetime.datetime = datetime.datetime(**datetime_params)  # type: ignore

        # Elapsed time
        time_diff: datetime.timedelta = now - time_start

        # Custom time delta
        time_delta: datetime.timedelta = (
            time_start + relativedelta(**delta) - time_start  # type: ignore
        )

        time_delta_seconds: float = time_delta.total_seconds()
        delta_coef: int = 1
        if time_delta_seconds > 0:
            """
            Getting the periodic coefficient.
            Example:
                reset the cache every 20 minutes of an hour, and the current time is 2:35.
                The cache will expire in 5 minutes, so coef = 2. coef * 20min - currentMinutes
            """
            delta_coef = math.ceil(time_diff.total_seconds() / time_delta_seconds)

        return int(
            (
                time_start + datetime.timedelta(seconds=delta_coef * time_delta_seconds) - now
            ).total_seconds()
        )

    @classmethod
    def everyXHoursOfDay(cls, hours: int, now: t.Optional[datetime.datetime] = None) -> T_TTL:
        return cls.round("day", {"hours": hours}, now=now)

    @classmethod
    def everyXMinutesOfHour(cls, minutes: int, now: t.Optional[datetime.datetime] = None) -> T_TTL:
        return cls.round("hour", {"minutes": minutes}, now=now)

    @classmethod
    def everyWhatDayOfWeek(cls, day_name: str, now: t.Optional[datetime.datetime] = None) -> T_TTL:
        mapping_days = {
            "sunday": 0,
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
        }
        if day_name not in mapping_days:
            raise ValueError(f"Accepted day_name are: {mapping_days.keys()}")

        return cls.round("week", {"weeks": 1, "weekday": mapping_days[day_name]}, now=now)

    @classmethod
    def everyXMonths(cls, months: int, now: t.Optional[datetime.datetime] = None) -> T_TTL:
        return cls.round("year", {"months": months}, now=now)
