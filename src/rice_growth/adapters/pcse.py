"""WOFOST 7.2 水稻潜在生产模拟。"""

from datetime import timedelta

import pandas as pd

from ..schema import ROOT, validate_trajectory
from ..weather import pcse_provider


class PcseAdapter:
    def __init__(self, parameter_dir=None):
        self.parameter_dir = parameter_dir or ROOT / "external/wofost_crop_parameters"

    def simulate(self, season):
        from pcse.base import ParameterProvider
        from pcse.input import WOFOST72SiteDataProvider, YAMLCropDataProvider
        from pcse.models import Wofost72_PP

        crop = YAMLCropDataProvider(model=Wofost72_PP, fpath=str(self.parameter_dir))
        site = WOFOST72SiteDataProvider(WAV=20.0)
        params = ParameterProvider(cropdata=crop, soildata=season.soil, sitedata=site)
        end = season.start + timedelta(days=season.max_duration)
        agro = [{season.start: {
            "CropCalendar": {"crop_name": "rice", "variety_name": season.variety,
                             "crop_start_date": season.start, "crop_start_type": "emergence",
                             "crop_end_date": end, "crop_end_type": "earliest",
                             "max_duration": season.max_duration},
            "TimedEvents": None, "StateEvents": None,
        }}]
        model = Wofost72_PP(params, pcse_provider(season.weather, season.site), agro)
        model.run_till_terminate()
        frame = pd.DataFrame(model.get_output()).rename(columns={
            "day": "date", "LAI": "lai_m2_m2", "TAGP": "biomass_aboveground_kg_ha",
            "TWSO": "storage_organ_dry_kg_ha", "DVS": "dvs", "SM": "soil_water_m3_m3",
        })
        frame["season_id"] = season.season_id
        frame["site_id"] = season.site["id"]
        frame["year"] = season.start.year
        frame["variety"] = season.variety
        frame["source"] = "mechanistic_simulation"
        frame["engine"] = "pcse_wofost72_pp"
        frame["weather_source"] = "synthetic_demo"
        frame["management_regime"] = "potential_production"
        validate_trajectory(frame)
        return frame
