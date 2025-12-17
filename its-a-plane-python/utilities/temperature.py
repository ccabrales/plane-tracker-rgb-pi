from datetime import datetime
import requests as r
import pytz
import time
import json 
import logging

# Attempt to load config data
try:
    from config import TEMPEST_ACCESS_TOKEN
    from config import TEMPEST_STATION_ID
    from config import TEMPERATURE_UNITS
    from config import FORECAST_DAYS
    from config import PRECIP_UNITS
    from config import FORECAST_DISTANCE_UNITS

except (ModuleNotFoundError, NameError, ImportError):
    # If there's no config data
    TEMPEST_ACCESS_TOKEN = None
    TEMPEST_STATION_ID = None
    TEMPERATURE_UNITS = "f"
    FORECAST_DAYS = 3
    PRECIP_UNITS = "in"
    FORECAST_DISTANCE_UNITS = "mi"

if TEMPERATURE_UNITS != "c" and TEMPERATURE_UNITS != "f":
    TEMPERATURE_UNITS = "f"

from config import TEMPERATURE_LOCATION

# Weather API
TEMPEST_API_URL = "https://swd.weatherflow.com/swd/rest"

def grab_temperature_and_humidity():
    try:
        request = r.get(
            f"{TEMPEST_API_URL}/better_forecast",
            params={
                "token": TEMPEST_ACCESS_TOKEN,
                "station_id": TEMPEST_STATION_ID,
                "units_temp":TEMPERATURE_UNITS,
                "units_precip": PRECIP_UNITS,
                "units_distance": FORECAST_DISTANCE_UNITS,
            },
            timeout=10  # Add timeout for the request
        )

        if request.status_code == 429:
            logging.error("Rate limit reached, returning error state")
            return None, None

        request.raise_for_status()

        # Safely extract data
        data = request.json().get("current_conditions", {})
        temperature = data.get("air_temperature")
        humidity = data.get("relative_humidity")

        if temperature is None or humidity is None:
            logging.error("Incomplete data from API")
            return None, None

        #print(f"[Temp] {datetime.now()}: {temperature}{TEMPERATURE_UNITS}, {humidity}% RH")
        return temperature, humidity

    except (r.exceptions.RequestException, ValueError) as e:
        logging.error(f"Temperature request failed: {e}")
        return None, None
        
        
def grab_forecast(tag="unknown"):
    try:
        resp = r.get(
            f"{TEMPEST_API_URL}/better_forecast",
            headers={
                "Accept-Encoding": "gzip",
                "accept": "application/json",
                "content-type": "application/json"
            },
            params={
                "token": TEMPEST_ACCESS_TOKEN,
                "station_id": TEMPEST_STATION_ID,
                "units_temp":TEMPERATURE_UNITS,
                "units_precip": PRECIP_UNITS,
                "units_distance": FORECAST_DISTANCE_UNITS,
            },
        )
        resp.raise_for_status()  # Raise an exception for 4xx or 5xx status codes

        # Safely access the JSON response to avoid KeyError
        data = resp.json()
        forecasts = data.get("forecast", {})

        if not forecasts:
            raise KeyError("Forecasts not found in response.")

        daily = forecasts.get("daily", [])

        if not daily:
            raise KeyError("Daily forecasts not found in response.")

        for day in daily:
            day["startTime"] = convert_unix_timestamp(day["day_start_local"])
            day["weatherCodeFullDay"] = convert_forecast_icon(day["icon"])
            day["sunriseTime"] = convert_unix_timestamp(day["sunrise"])
            day["sunsetTime"] = convert_unix_timestamp(day["sunset"])

        # Missing fields from Tomorrow:
        # - moonPhase
        return daily

    except r.exceptions.RequestException as e:
        logging.error(f"[Forecast:{tag}] API request failed: {e}")
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
