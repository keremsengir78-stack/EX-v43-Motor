"""Historical weather reanalysis and geodesic venue separation."""

import json
import math
from urllib.parse import urlencode

from ex_history_archive import utc


WEATHER = ("temperature_2m", "precipitation", "wind_speed_10m")


def coordinates(venue, registry):
    if not isinstance(venue, dict):
        return None
    item = registry.get(str(venue.get("id")))
    if not item or item["name"] != venue.get("fullName") or not item.get("source"):
        return None
    lat, lon = item["latitude"], item["longitude"]
    if any(type(x) not in (int, float) for x in (lat, lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid registered venue coordinates")
    return lat, lon


def separation_km(first, second):
    lat1, lon1 = map(math.radians, first)
    lat2, lon2 = map(math.radians, second)
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return round(2 * 6371.0088 * math.asin(math.sqrt(max(0, min(1, a)))), 2)


def weather_at(archive, point, kickoff_at):
    kickoff = utc(kickoff_at)
    day = kickoff.date().isoformat()
    hour = kickoff.strftime("%Y-%m-%dT%H:00")
    query = urlencode({"latitude": point[0], "longitude": point[1], "start_date": day,
                       "end_date": day, "hourly": ",".join(WEATHER), "timezone": "GMT",
                       "wind_speed_unit": "kmh", "temperature_unit": "celsius", "precipitation_unit": "mm"})

    def parse(raw, _):
        payload = json.loads(raw)
        grid = payload["latitude"], payload["longitude"]
        if separation_km(point, grid) > 35 or payload["utc_offset_seconds"] != 0:
            raise ValueError("Weather grid or time zone mismatch")
        expected = {"temperature_2m": "°C", "precipitation": "mm", "wind_speed_10m": "km/h"}
        hourly = payload["hourly"]
        values = {}
        for key in WEATHER:
            if payload["hourly_units"][key] != expected[key] or len(hourly[key]) != len(hourly["time"]):
                raise ValueError("Weather units or time series mismatch")
            values[key] = dict(zip(hourly["time"], hourly[key], strict=True))
        return {"grid": grid, "values": values, "units": expected}

    result, meta = archive.get("https://archive-api.open-meteo.com/v1/archive?" + query, parse)
    values = {key: result["values"][key][hour] for key in WEATHER}
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in values.values()):
        raise ValueError("Missing or invalid hourly weather observation")
    return {"kind": "RETROSPECTIVE_REANALYSIS", "hour_utc": hour + "Z",
            "values": values, "grid": result["grid"], "units": result["units"], "source": meta}
