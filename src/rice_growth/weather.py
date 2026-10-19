"""可复现的演示天气，以及面向 PCSE 的显式单位转换。"""

from datetime import timedelta

import numpy as np
import pandas as pd

from .schema import validate_weather


def synthetic_weather(start, days, seed, temperature_offset=0.0):
    rng = np.random.default_rng(seed)
    t = np.arange(days)
    mean = 26 + temperature_offset + 2 * np.sin(2 * np.pi * t / 180) + rng.normal(0, 0.7, days)
    return pd.DataFrame(
        {
            "date": [start + timedelta(days=int(i)) for i in t],
            "tmin_c": mean - 4,
            "tmax_c": mean + 5,
            "radiation_mj_m2_day": np.clip(18 + rng.normal(0, 3, days), 5, 28),
            "rain_mm_day": rng.gamma(2, 4, days) * (rng.random(days) < 0.4),
            "vapour_pressure_kpa": np.full(days, 2.3),
            "wind_m_s": np.full(days, 2.0),
        }
    )


def pcse_weather_values(row):
    """公共格式使用 MJ、mm、kPa，PCSE 使用 J、cm、hPa。"""
    return dict(
        TMIN=float(row.tmin_c),
        TMAX=float(row.tmax_c),
        IRRAD=float(row.radiation_mj_m2_day) * 1e6,
        RAIN=float(row.rain_mm_day) / 10,
        VAP=float(row.vapour_pressure_kpa) * 10,
        WIND=float(row.wind_m_s),
    )


def pcse_provider(weather, site):
    from pcse.base import WeatherDataContainer, WeatherDataProvider
    from pcse.util import reference_ET

    validate_weather(weather)
    provider = WeatherDataProvider()
    provider.latitude = site["latitude"]
    provider.longitude = site["longitude"]
    provider.elevation = site["elevation_m"]
    provider.description = ["人工天气"]
    for row in weather.itertuples(index=False):
        day = pd.Timestamp(row.date).date()
        values = pcse_weather_values(row)
        e0, es0, et0 = reference_ET(
            DAY=day,
            LAT=provider.latitude,
            ELEV=provider.elevation,
            ANGSTA=0.25,
            ANGSTB=0.5,
            **values,
        )
        container = WeatherDataContainer(
            DAY=day,
            LAT=provider.latitude,
            LON=provider.longitude,
            ELEV=provider.elevation,
            E0=e0 / 10,
            ES0=es0 / 10,
            ET0=et0 / 10,
            **values,
        )
        provider._store_WeatherDataContainer(container, day)
    return provider
