"""
temperature.py — Auto-selects master or slave mode based on config.
If MASTER_TRACKER = "" this Pi calls Tomorrow.io directly.
If MASTER_TRACKER = "hostname" this Pi polls the master's /weather/json endpoint.
"""

from datetime import datetime
import time
import logging
import os
import socket
import json

# ─── Master/slave routing ─────────────────────────────────────────────────────
try:
    from config import MASTER_TRACKER
except (ImportError, ModuleNotFoundError, NameError):
    MASTER_TRACKER = ""

# ─── Shared config (both modes need these) ───────────────────────────────────
try:
    from config import TEMPERATURE_UNITS
except (ModuleNotFoundError, NameError, ImportError):
    TEMPERATURE_UNITS = "imperial"

try:
    from config import FORECAST_DAYS
except (ModuleNotFoundError, NameError, ImportError):
    FORECAST_DAYS = 3

if TEMPERATURE_UNITS not in ("metric", "imperial"):
    TEMPERATURE_UNITS = "imperial"

# ─── Persistent File Cache (shared — both master and slave use this) ─────────
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_TEMP_CACHE_FILE     = os.path.join(_CACHE_DIR, "temperature.json")
_FORECAST_CACHE_FILE = os.path.join(_CACHE_DIR, "forecast.json")
_CACHE_TTL           = 7200  # 2 hours — use file cache if API fails within this window

# ─── Invalidate caches if units have changed ──────────────────────────────────
def _invalidate_on_units_change():
    for path in (_TEMP_CACHE_FILE, _FORECAST_CACHE_FILE):
        try:
            with open(path, "r") as f:
                obj = json.load(f)
            if obj.get("units") != TEMPERATURE_UNITS:
                logging.info(f"[Weather] Units changed, deleting stale cache: {path}")
                os.remove(path)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

_invalidate_on_units_change()

def _load_file_cache(path, units=None):
    """Load cached data from file. Returns (data, timestamp) or (None, 0).
    If `units` is provided and doesn't match what's stored, treats cache as a miss
    so a units change (metric <-> imperial) always triggers a fresh API call."""
    try:
        with open(path, "r") as f:
            obj = json.load(f)
        if units is not None and obj.get("units") != units:
            logging.info(f"Cache units mismatch ({obj.get('units')!r} -> {units!r}), invalidating {path}")
            return None, 0
        return obj.get("data"), obj.get("ts", 0)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None, 0

def _save_file_cache(path, data, units=None):
    """Save data + timestamp (+ units) to file cache (atomic via rename)."""
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"data": data, "ts": time.time(), "units": units}, f)
        os.replace(tmp, path)  # atomic on POSIX
    except (PermissionError, OSError) as e:
        logging.warning(f"Cannot write cache {path}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SLAVE MODE — poll weather data from the master Pi
# ─────────────────────────────────────────────────────────────────────────────
if MASTER_TRACKER:
    import requests
    from requests.exceptions import RequestException

    def _url(path):
        host = MASTER_TRACKER.strip().rstrip("/")
        if not host.startswith("http"):
            if ":" not in host:
                host = f"http://{host}.local:8080"
            else:
                host = f"http://{host}"
        return f"{host}{path}"

    def grab_temperature_and_humidity():
        """Fetch current temperature and humidity from the master's /weather/json endpoint."""
        try:
            r = requests.get(_url("/weather/json"), timeout=10)
            r.raise_for_status()
            data = r.json()
            temperature = data.get("temperature")
            humidity    = data.get("humidity")
            if temperature is None or humidity is None:
                logging.warning("[Slave/Weather] Master returned incomplete temp/humidity data")
                return None, None
            _save_file_cache(_TEMP_CACHE_FILE, [temperature, humidity], units=TEMPERATURE_UNITS)
            return temperature, humidity
        except RequestException as e:
            logging.error(f"[Slave/Weather] Cannot reach master for weather: {e}")
            cached, ts = _load_file_cache(_TEMP_CACHE_FILE, units=TEMPERATURE_UNITS)
            if cached and (time.time() - ts) < _CACHE_TTL:
                logging.info("[Slave/Weather] Using cached temperature data")
                return tuple(cached) if isinstance(cached, list) else cached
            return None, None

    def grab_forecast(tag="unknown"):
        """Fetch forecast intervals from the master's /weather/json endpoint."""
        try:
            r = requests.get(_url("/weather/json"), timeout=10)
            r.raise_for_status()
            data = r.json()
            forecast = data.get("forecast", [])
            if not isinstance(forecast, list):
                logging.warning(f"[Slave/Weather:{tag}] Master returned non-list forecast")
                return []
            _save_file_cache(_FORECAST_CACHE_FILE, forecast, units=TEMPERATURE_UNITS)
            return forecast
        except RequestException as e:
            logging.error(f"[Slave/Weather:{tag}] Cannot reach master for forecast: {e}")
            cached, ts = _load_file_cache(_FORECAST_CACHE_FILE, units=TEMPERATURE_UNITS)
            if cached and (time.time() - ts) < _CACHE_TTL:
                logging.info(f"[Slave/Weather:{tag}] Using cached forecast data")
                return cached
            return []

    print(f"[Weather] Slave mode — polling master at {_url('')}")


# ─────────────────────────────────────────────────────────────────────────────
# MASTER MODE — full Tomorrow.io stack with persistent file cache
# ─────────────────────────────────────────────────────────────────────────────
else:
    print("[Weather] Master mode — calling Tomorrow.io directly")

    from requests import Session
    from requests.adapters import HTTPAdapter
    from requests.exceptions import RequestException
    from urllib3.util.retry import Retry

    try:
        from config import TEMPEST_ACCESS_TOKEN
    except (ModuleNotFoundError, NameError, ImportError):
        TEMPEST_ACCESS_TOKEN = None

    try:
        from config import TEMPEST_STATION_ID
    except (ModuleNotFoundError, NameError, ImportError):
        TEMPEST_STATION_ID = None

    try:
        from config import PRECIP_UNITS
    except (ModuleNotFoundError, NameError, ImportError):
        PRECIP_UNITS = "in"

    if PRECIP_UNITS not in ("in", "mm", "cm"):
        PRECIP_UNITS = "in"

    try:
        from config import FORECAST_DISTANCE_UNITS
    except (ModuleNotFoundError, NameError, ImportError):
        FORECAST_DISTANCE_UNITS = "mi"

    if FORECAST_DISTANCE_UNITS not in ("mi", "km"):
        FORECAST_DISTANCE_UNITS = "mi"

    try:
        from config import TEMPERATURE_LOCATION
    except (ImportError, NameError):
        TEMPERATURE_LOCATION = ""

    def is_dns_error(exc: Exception) -> bool:
        cause = exc
        while cause:
            if isinstance(cause, socket.gaierror):
                return True
            cause = cause.__cause__
        return False

    _session = None

    def get_session() -> Session:
        global _session
        if _session is None:
            _session = Session()
            retries = Retry(
                total=3,
                connect=3,
                read=3,
                backoff_factor=2,
                allowed_methods=["GET", "POST"],
                status_forcelist=[429, 500, 502, 503, 504],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(
                max_retries=retries,
                pool_connections=2,
                pool_maxsize=2,
            )
            _session.mount("https://", adapter)
            _session.mount("http://", adapter)
        return _session

    # Weather API
    TEMPEST_API_URL = "https://swd.weatherflow.com/swd/rest"

    def grab_temperature_and_humidity():
        try:
            s = get_session()
            request = s.get(
                f"{TEMPEST_API_URL}/better_forecast",
                params={
                    "token": TEMPEST_ACCESS_TOKEN,
                    "station_id": TEMPEST_STATION_ID,
                    "units_temp":TEMPERATURE_UNITS,
                    "units_precip": PRECIP_UNITS,
                    "units_distance": FORECAST_DISTANCE_UNITS,
                },
                timeout=(5, 20)
            )

            if request.status_code == 429:
                logging.error("Rate limit reached, trying file cache")
                cached, ts = _load_file_cache(_TEMP_CACHE_FILE, units=TEMPERATURE_UNITS)
                if cached and (time.time() - ts) < _CACHE_TTL:
                    return tuple(cached) if isinstance(cached, list) else cached
                return None, None

            request.raise_for_status()

            data        = request.json().get("current_conditions", {})
            temperature = data.get("air_temperature")
            humidity    = data.get("relative_humidity")

            if temperature is None or humidity is None:
                logging.error("Incomplete data from API")
                return None, None

            _save_file_cache(_TEMP_CACHE_FILE, [temperature, humidity], units=TEMPERATURE_UNITS)
            return temperature, humidity

        except (RequestException, ValueError) as e:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            if is_dns_error(e):
                logging.error(f"[{timestamp}] DNS failure resolving api.tomorrow.io - will retry")
            else:
                logging.error(f"[{timestamp}] Temperature request failed: {e}")

            cached, ts = _load_file_cache(_TEMP_CACHE_FILE, units=TEMPERATURE_UNITS)
            if cached and (time.time() - ts) < _CACHE_TTL:
                return tuple(cached) if isinstance(cached, list) else cached
            return None, None


    def grab_forecast(tag="unknown"):
        try:
            s = get_session()
            resp = s.get(
                f"{TEMPEST_API_URL}/better_forecast",
                headers={
                    "Accept-Encoding": "gzip",
                    "accept":          "application/json",
                    "content-type":    "application/json"
                },
                params={
                    "token": TEMPEST_ACCESS_TOKEN,
                    "station_id": TEMPEST_STATION_ID,
                    "units_temp":TEMPERATURE_UNITS,
                    "units_precip": PRECIP_UNITS,
                    "units_distance": FORECAST_DISTANCE_UNITS,
                },
                timeout=(5, 20)
            )

            if resp.status_code == 429:
                logging.error(f"[Forecast:{tag}] Rate limit reached, trying file cache")
                cached, ts = _load_file_cache(_FORECAST_CACHE_FILE, units=TEMPERATURE_UNITS)
                if cached and (time.time() - ts) < _CACHE_TTL:
                    return cached
                return []

            resp.raise_for_status()

            data      = resp.json()
            forecasts = data.get("forecast", {})
            if not forecasts:
                logging.error(f"[Forecast:{tag}] No timelines returned from API")
                raise KeyError("Forecasts not found in response.")

            daily = forecasts.get("daily", [])
            if not daily:
                logging.error(f"[Forecast:{tag}] Timelines returned but no intervals")
                raise KeyError("Daily forecasts not found in response.")

            for day in daily:
                day["startTime"] = convert_unix_timestamp(day["day_start_local"])
                day["weatherCodeFullDay"] = convert_forecast_icon(day["icon"])
                day["sunriseTime"] = convert_unix_timestamp(day["sunrise"])
                day["sunsetTime"] = convert_unix_timestamp(day["sunset"])

            _save_file_cache(_FORECAST_CACHE_FILE, daily, units=TEMPERATURE_UNITS)
            # Missing fields from Tomorrow:
            # - moonPhase
            return daily

        except RequestException as e:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            if is_dns_error(e):
                logging.error(f"[{timestamp}] [Forecast:{tag}] DNS failure resolving api.tomorrow.io - will retry")
            else:
                logging.error(f"[{timestamp}] [Forecast:{tag}] API request failed: {e}")

            cached, ts = _load_file_cache(_FORECAST_CACHE_FILE, units=TEMPERATURE_UNITS)
            if cached and (time.time() - ts) < _CACHE_TTL:
                return cached
            return []

        except KeyError as e:
            logging.error(f"[Forecast:{tag}] Unexpected data format: {e}")
            return []

# Convert Tempest forecast "icon" to Tomorrow API "weatherCodeFullDay"
def convert_forecast_icon(name):
    match name:
        case "clear-day":
            return 1000
        case "clear-night":
            return 10001
        case "cloudy":
            return 1001
        case "foggy":
            return 2000
        case "partly-cloudy-day":
            return 1101
        case "partly-cloudy-night":
            return 11011
        case "possibly-rainy-day":
            return 4210
        case "possibly-rainy-night":
            return 42101
        case "possibly-sleet-day":
            return 5114
        case "possibly-sleet-night":
            return 51141
        case "possibly-snow-day":
            return 5100
        case "possibly-snow-night":
            return 51001
        case "possibly-thunderstorm-day":
            return 8003
        case "possibly-thunderstorm-night":
            return 80031
        case "rainy":
            return 4001
        case "sleet":
            return 5114
        case "snow":
            return 5000
        case "thunderstorm":
            return 8000
        case "windy":
            return 2100 # No matching icon...
        case _:
            return 1000

def convert_unix_timestamp(timestamp):
    return datetime.fromtimestamp(timestamp).isoformat() + "Z"

# forecast_data = grab_forecast()
# if forecast_data is not None:
#    print("Weather forecast:")
#    for interval in forecast_data:
#        temperature_min = interval["air_temp_low"]
#        temperature_max = interval["air_temp_high"]
#        weather_code_day = convert_forecast_icon(interval["icon"])
#        sunrise = interval["sunrise"]
#        sunset = interval["sunset"]
#        moon_phase = None # interval["values"]["moonPhase"]
#        startTime = convert_unix_timestamp(interval["day_start_local"])
#        print(f"Date: {startTime[:10]}, Min Temp: {temperature_min}, Max Temp: {temperature_max}, Weather Code: {weather_code_day}, Sunrise: {convert_unix_timestamp(sunrise)}, Sunset: {convert_unix_timestamp(sunset)}, Moon Phase: {moon_phase}")
# else:
#    print("Failed to retrieve forecast.")