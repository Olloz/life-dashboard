"""London weather from Open-Meteo (no key)."""
from . import get_json

URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&timezone={tz}&forecast_days=7"
       "&hourly=temperature_2m,apparent_temperature,precipitation_probability,wind_speed_10m,weather_code"
       "&daily=temperature_2m_min,temperature_2m_max,sunrise,sunset,precipitation_probability_max")


def parse(raw):
    h, d = raw["hourly"], raw["daily"]
    hourly = [{"time": t, "temp": a, "feels": b, "rain": c, "wind": w, "code": k} for t, a, b, c, w, k in zip(
        h["time"], h["temperature_2m"], h["apparent_temperature"], h["precipitation_probability"],
        h["wind_speed_10m"], h["weather_code"])]
    daily = [{"date": t, "min": a, "max": b, "sunrise": c, "sunset": s, "rain": r} for t, a, b, c, s, r in zip(
        d["time"], d["temperature_2m_min"], d["temperature_2m_max"], d["sunrise"], d["sunset"],
        d["precipitation_probability_max"])]
    return {"hourly": hourly, "daily": daily}


def fetch(cfg):
    loc = cfg["location"]
    return parse(get_json(URL.format(lat=loc["lat"], lon=loc["lon"], tz=cfg["timezone"].replace("/", "%2F"))))
