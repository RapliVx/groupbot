import time
import asyncio
import aiohttp

from telegram import Update
from telegram.ext import ContextTypes
from utils.http import get_http_session


def _wmo_desc(code: int) -> str:
    m = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Freezing drizzle",
        61: "Slight rain",
        63: "Rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Freezing rain",
        71: "Slight snow fall",
        73: "Snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail",
    }
    return m.get(int(code), "N/A")


async def _geocode_city(session: aiohttp.ClientSession, city: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city, "count": 1, "language": "en", "format": "json"}
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
        if resp.status != 200:
            return None
        data = await resp.json()
    results = (data or {}).get("results") or []
    if not results:
        return None
    r = results[0]
    return {
        "name": r.get("name") or city,
        "country": r.get("country") or "",
        "admin1": r.get("admin1") or "",
        "lat": r.get("latitude"),
        "lon": r.get("longitude"),
        "tz": r.get("timezone") or "auto",
    }


async def _fetch_weather_open_meteo(session: aiohttp.ClientSession, lat: float, lon: float, tz: str):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,wind_direction_10m,cloud_cover,weather_code",
        "daily": "sunrise,sunset",
        "timezone": tz,
    }
    async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=12)) as resp:
        if resp.status != 200:
            return None
        return await resp.json()


async def weather_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    if not context.args:
        return await msg.reply_text("Example: <code>/weather jakarta</code>", parse_mode="HTML")

    city = " ".join(context.args).strip()
    if not city:
        return await msg.reply_text("Example: <code>/weather jakarta</code>", parse_mode="HTML")

    status_msg = await msg.reply_text(
        f"Fetching weather for <b>{city.title()}</b>...",
        parse_mode="HTML"
    )

    session = await get_http_session()

    try:
        geo = await _geocode_city(session, city)
        if not geo:
            return await status_msg.edit_text("City not found. Try a more specific name (e.g., <code>Jakarta, ID</code>).", parse_mode="HTML")

        data = await _fetch_weather_open_meteo(session, float(geo["lat"]), float(geo["lon"]), geo["tz"])
        if not data:
            return await status_msg.edit_text("Failed to fetch weather data. Try again later.")

        cur = (data.get("current") or {})
        daily = (data.get("daily") or {})

        place = geo["name"]
        extra = ", ".join([x for x in [geo.get("admin1"), geo.get("country")] if x])
        if extra:
            place = f"{place}, {extra}"

        temp = cur.get("temperature_2m", "N/A")
        feels = cur.get("apparent_temperature", "N/A")
        humidity = cur.get("relative_humidity_2m", "N/A")
        wind_spd = cur.get("wind_speed_10m", "N/A")
        wind_dir = cur.get("wind_direction_10m", "N/A")
        cloud = cur.get("cloud_cover", "N/A")
        wcode = cur.get("weather_code", None)
        desc = _wmo_desc(int(wcode)) if wcode is not None else "N/A"

        sunrise = (daily.get("sunrise") or ["N/A"])[0]
        sunset = (daily.get("sunset") or ["N/A"])[0]

        report = (
            f"<b>Weather — {html.escape(place)}</b>\n\n"
            f"Condition : {html.escape(str(desc))}\n"
            f"Temperature : {temp}°C (Feels like {feels}°C)\n"
            f"Humidity : {humidity}%\n"
            f"Wind : {wind_spd} km/h (dir {wind_dir}°)\n"
            f"Cloud cover : {cloud}%\n\n"
            f"Sunrise : {html.escape(str(sunrise))}\n"
            f"Sunset  : {html.escape(str(sunset))}\n\n"
            f"Updated : {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return await status_msg.edit_text(report, parse_mode="HTML", disable_web_page_preview=True)

    except asyncio.TimeoutError:
        return await status_msg.edit_text("Request timed out. Please try again later.")
    except Exception:
        return await status_msg.edit_text("Failed to reach the weather server.")
    