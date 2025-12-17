ZONE_HOME = {
    "tl_y": xx.xxxxxx, # Top-Left Latitude (deg) https://www.latlong.net/ or google maps. The bigger the zone, the more planes you'll get. My zone is ~3.5 miles in each direction or 10mi corner to corner. 
    "tl_x": xx.xxxxxx, # Top-Left Longitude (deg)
    "br_y": xx.xxxxxx, # Bottom-Right Latitude (deg)
    "br_x": xx.xxxxxx # Bottom-Right Longitude (deg)
}
LOCATION_HOME = [
    xx.xxxxxx, # Latitude (deg)
    xx.xxxxxx # Longitude (deg)
]
TEMPERATURE_LOCATION = "xx.xxxxxx,xx.xxxxxx" #same as location home
TEMPEST_ACCESS_TOKEN = "xxxxxx" # Get access token from WeatherFlow Tempest API -- tempestxw.com > Settings > Data Authorizations > Create Token
TEMPEST_STATION_ID = "xxx" # Get station id from https://swd.weatherflow.com/swd/rest/stations stations.station_id
TEMPERATURE_UNITS = "f" #can use "c" or "f" if you want
PRECIP_UNITS = "in" # can use in, mm, cm
FORECAST_DISTANCE_UNITS = "mi" # can use "mi" or "km"
DISTANCE_UNITS = "imperial"
CLOCK_FORMAT = "12hr" #use 12hr or 24hr
MIN_ALTITUDE = 2000 #feet above sea level. If you live at 1000ft then you'd want to make yours ~3000 etc. I use 2000 to weed out some of the smaller general aviation traffic. 
BRIGHTNESS = 100
BRIGHTNESS_NIGHT = 50
NIGHT_BRIGHTNESS = False #True for on False for off
NIGHT_START = "22:00" #dims screen between these hours
NIGHT_END = "06:00"
GPIO_SLOWDOWN = 2 #depends what Pi you have I use 2 for Pi 3 and 1 for Pi Zero
JOURNEY_CODE_SELECTED = "xxx" #your home airport code
JOURNEY_BLANK_FILLER = " ? " #what to display if theres no airport code
HAT_PWM_ENABLED = False #only if you haven't soldered the PWM bridge use True if you did
FORECAST_DAYS = 3 #today plus the next two days
EMAIL = "" #insert your email address between the " ie "example@example.com" to receive emails when there is a new closest flight on the tracker. Leave "" to receive no emails. It will log/local webpage regardless
MAX_FARTHEST = 3 #the amount of furthest flights you want in your log
MAX_CLOSEST = 3 #the amount of closest flights to your house you want in your log
