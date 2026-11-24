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


def nasa_power_at(archive, point, kickoff_at):
    """NASA POWER hourly reanalysis on its regional model grid."""
    kickoff = utc(kickoff_at)
    day = kickoff.strftime("%Y%m%d")
    hour = kickoff.strftime("%Y%m%d%H")
    parameters = {"temperature_2m": ("T2M", "C"), "precipitation": ("PRECTOTCORR", "mm/hour"),
                  "wind_speed_10m": ("WS10M", "m/s")}
    query = urlencode({"latitude": point[0], "longitude": point[1], "start": day, "end": day,
                       "parameters": ",".join(code for code, _ in parameters.values()),
                       "community": "RE", "time-standard": "UTC", "format": "JSON"})

    def parse(raw, _):
        payload = json.loads(raw)
        lon, lat, *_ = payload["geometry"]["coordinates"]
        grid = lat, lon
        header = payload["header"]
        if header["time_standard"] != "UTC" or separation_km(point, grid) > 100:
            raise ValueError("NASA POWER grid or time zone mismatch")
        values = {}
        for name, (code, units) in parameters.items():
            if payload["parameters"][code]["units"] != units:
                raise ValueError(f"NASA POWER unexpected units for {code}")
            value = payload["properties"]["parameter"][code][hour]
            if type(value) not in (float, int) or not math.isfinite(value) or value == header["fill_value"]:
                raise ValueError(f"NASA POWER missing observation for {code}")
            if name != "temperature_2m" and value < 0:
                raise ValueError(f"NASA POWER invalid observation for {code}")
            values[name] = round(value * 3.6, 4) if name == "wind_speed_10m" else value
        return grid, values

    (grid, values), meta = archive.get("https://power.larc.nasa.gov/api/temporal/hourly/point?" + query, parse)
    return {"kind": "RETROSPECTIVE_REANALYSIS", "provider": "NASA POWER", "grid": grid,
            "grid_distance_km": separation_km(point, grid), "hour_utc": kickoff.strftime("%Y-%m-%dT%H:00Z"),
            "values": values, "units": {"temperature_2m": "°C", "precipitation": "mm/hour",
                                      "wind_speed_10m": "km/h"}, "source": meta}


def reviewed_environment(plan, registry, evidence):
    """Link reviewed club publications to archive identities for retrospective research."""
    from datetime import date
    from urllib.parse import urlsplit

    club_domains = {"364": "www.liverpoolfc.com", "86": "www.realmadrid.com"}
    events = {row["event_id"]: row for row in plan["pending_events"]}

    def owned_url(row, host):
        parsed = urlsplit(row["source"])
        return parsed.scheme == "https" and parsed.netloc == host and bool(parsed.path)

    travel = []
    for row in evidence["travel"]:
        fixture = events.get(row["event_id"])
        if fixture is None:
            continue
        kickoff = utc(fixture["kickoff_at"]).date()
        published = date.fromisoformat(row["published_date"])
        if (fixture["competition"] != "uefa.champions" or fixture["teams"]["away"] != row["team_id"]
                or date.fromisoformat(row["kickoff_date"]) != kickoff or published >= kickoff
                or not owned_url(row, club_domains[row["team_id"]])):
            raise ValueError("Reviewed travel fixture or publication mismatch")
        travel.append({**row, "availability": "RETROSPECTIVE_SOURCE_REVIEW"})
    grounds = []
    for row in evidence["grounds"]:
        if (registry[row["venue_id"]]["name"] != row["venue_name"]
                or not owned_url(row, "www.arsenal.com")):
            raise ValueError("Reviewed pitch venue or publication mismatch")
        grounds.append({**row, "availability": "RETROSPECTIVE_SOURCE_REVIEW"})
    return travel, grounds
