"""Collect source-timestamped numerical forecasts for known stadiums."""

import json
import math
from urllib.parse import urlencode

from ex_history_archive import utc
from ex_history_environment import separation_km


def forecast(archive, point, kickoff, analysis_at):
    stamp = utc(kickoff)
    day = stamp.date().isoformat()
    hour = stamp.strftime("%Y-%m-%dT%H:00")
    fields = {"temperature_2m": "°C", "precipitation_probability": "%", "wind_speed_10m": "km/h"}
    query = urlencode({"latitude": point[0], "longitude": point[1], "timezone": "GMT",
                       "start_date": day, "end_date": day, "hourly": ",".join(fields)})

    def parse(raw, captured):
        data = json.loads(raw)
        if captured >= stamp or separation_km(point, (data["latitude"], data["longitude"])) > 35:
            raise ValueError("Forecast outside fixture time or location")
        if data["utc_offset_seconds"] != 0 or any(data["hourly_units"][f] != u for f, u in fields.items()):
            raise ValueError("Forecast units differ")
        index = data["hourly"]["time"].index(hour)
        values = {field: data["hourly"][field][index] for field in fields}
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in values.values()):
            raise ValueError("Forecast hourly value missing")
        if not 0 <= values["precipitation_probability"] <= 100 or values["wind_speed_10m"] < 0:
            raise ValueError("Impossible forecast values")
        return values

    values, source = archive.get("https://api.open-meteo.com/v1/forecast?" + query, parse)
    if not utc(source["retrieved_at"]) < utc(analysis_at()) < stamp:
        raise ValueError("Forecast unavailable at analysis cutoff")
    return {"kind": "PREMATCH_NUMERICAL_FORECAST", "forecast_hour_utc": hour + ":00Z",
            "source": source, "values": values}
