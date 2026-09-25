"""Skin weather: UV, humidity, temperature and air quality for the user's city, turned into skincare tips.

Uses Open-Meteo (free, no API key). Only the city name you type and its coordinates are sent; nothing
else about you leaves the server. Results are cached for 30 minutes.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("foxtale.weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
CACHE_S = 30 * 60
_cache: Dict[str, Any] = {}


class WeatherError(Exception):
    pass


def geocode(city: str) -> Dict[str, Any]:
    city = (city or "").strip()
    if len(city) < 2:
        raise WeatherError("Type the name of your city.")
    try:
        res = httpx.get(GEOCODE_URL, params={"name": city, "count": 1, "language": "en"}, timeout=10.0)
        res.raise_for_status()
        results = res.json().get("results") or []
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherError("Could not look up that city. Check the internet connection and try again.") from exc
    if not results:
        raise WeatherError(f"Could not find a city called \"{city}\".")
    r = results[0]
    label = ", ".join(x for x in (r.get("name"), r.get("admin1"), r.get("country")) if x)
    return {"name": label, "lat": round(float(r["latitude"]), 3), "lon": round(float(r["longitude"]), 3)}


def uv_label(uv: float) -> str:
    return "Low" if uv < 3 else "Moderate" if uv < 6 else "High" if uv < 8 else "Very high" if uv < 11 else "Extreme"


def aqi_label(aqi: float) -> str:
    return "Good" if aqi <= 50 else "Moderate" if aqi <= 100 else "Unhealthy for sensitive skin" if aqi <= 150 else "Unhealthy" if aqi <= 200 else "Very unhealthy"


def fetch(lat: float, lon: float) -> Dict[str, Any]:
    key = f"{lat:.2f},{lon:.2f}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_S:
        return hit[1]
    try:
        w = httpx.get(FORECAST_URL, params={
            "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 1,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature",
            "daily": "uv_index_max,temperature_2m_max",
        }, timeout=10.0)
        w.raise_for_status()
        wj = w.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherError("Could not get the weather right now.") from exc
    aqi: Optional[float] = None
    try:
        a = httpx.get(AIR_URL, params={"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5"}, timeout=10.0)
        a.raise_for_status()
        aqi = a.json().get("current", {}).get("us_aqi")
    except (httpx.HTTPError, ValueError):
        logger.info("Air quality unavailable")
    cur, daily = wj.get("current", {}), wj.get("daily", {})
    data = {
        "temp": cur.get("temperature_2m"), "feelsLike": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "uv": (daily.get("uv_index_max") or [None])[0], "tempMax": (daily.get("temperature_2m_max") or [None])[0],
        "aqi": aqi,
    }
    _cache[key] = (time.time(), data)
    return data


def tips(w: Dict[str, Any], skin_type: str) -> List[Dict[str, Any]]:
    """Rule-based tips for today's conditions and the user's skin type. Product ids refer to the Foxtale catalog."""
    out: List[Dict[str, Any]] = []
    uv, hum, temp, aqi = w.get("uv"), w.get("humidity"), w.get("temp"), w.get("aqi")
    spf = "dewy-sunscreen" if skin_type == "dry" else "matte-sunscreen"

    if uv is not None:
        if uv >= 8:
            out.append({"icon": "sun", "tone": "warn", "title": f"UV is {uv_label(uv).lower()} ({uv:.0f})",
                        "text": "Apply SPF 50 as the last morning step, reapply every 2 hours outdoors, and wear a hat or seek shade around midday. Sun also darkens acne marks and spots.", "products": [spf]})
        elif uv >= 3:
            out.append({"icon": "sun", "tone": "ok", "title": f"UV is {uv_label(uv).lower()} ({uv:.0f})",
                        "text": "Sunscreen every morning, even if it is cloudy. Use enough: about two finger-lengths for face and neck.", "products": [spf]})
        else:
            out.append({"icon": "sun", "tone": "good", "title": f"UV is low ({uv:.0f})",
                        "text": "Low UV today, but keep sunscreen as a daily habit, especially if you use retinol or exfoliating acids.", "products": []})
    if hum is not None:
        if hum <= 35:
            out.append({"icon": "wind", "tone": "warn", "title": f"Dry air ({hum:.0f}% humidity)",
                        "text": "Dry air pulls water from the skin. Add a hydrating serum on damp skin and seal it with a moisturizer; skip hot water and harsh cleansers.", "products": ["hyaluronic-serum", "ceramide-moisturizer"]})
        elif hum >= 75:
            heavy = skin_type in ("oily", "combination")
            out.append({"icon": "droplets", "tone": "ok", "title": f"Humid ({hum:.0f}% humidity)",
                        "text": "Humidity plus sweat can make skin shiny and pores feel clogged. Keep layers light and cleanse gently in the evening." + (" A gel moisturizer and matte sunscreen suit today." if heavy else ""),
                        "products": ["oil-balancing-moisturizer"] if heavy else []})
    if temp is not None:
        if temp >= 34:
            out.append({"icon": "thermometer", "tone": "warn", "title": f"Hot day ({temp:.0f}°C)",
                        "text": "Sweat and heat can trigger breakouts and irritation. Wash your face after sweating, avoid heavy creams, and drink water.", "products": ["salicylic-face-wash"] if skin_type in ("oily", "combination") else []})
        elif temp <= 10:
            out.append({"icon": "thermometer", "tone": "warn", "title": f"Cold day ({temp:.0f}°C)",
                        "text": "Cold weather weakens the skin barrier. Use a richer moisturizer at night and go easy on exfoliating acids.", "products": ["ceramide-moisturizer"]})
    if aqi is not None:
        if aqi > 100:
            out.append({"icon": "cloud", "tone": "warn", "title": f"Air quality: {aqi_label(aqi).lower()} (AQI {aqi:.0f})",
                        "text": "Pollution can dull skin and clog pores. Cleanse thoroughly tonight, use an antioxidant such as vitamin C in the morning, and avoid touching your face.", "products": ["hydrating-face-wash", "vitamin-c-serum"]})
        elif aqi > 50:
            out.append({"icon": "cloud", "tone": "ok", "title": f"Air quality is moderate (AQI {aqi:.0f})", "text": "Fine for most people. A proper evening cleanse removes the day's dust and sunscreen.", "products": []})
    return out
