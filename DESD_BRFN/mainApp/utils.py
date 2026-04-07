from geopy.geocoders import Nominatim
from geopy.distance import geodesic

# Bristol city centre coordinates (reference point for food miles)
BRISTOL_LAT = 51.4545
BRISTOL_LON = -2.5879
BRISTOL_COORDS = (BRISTOL_LAT, BRISTOL_LON)


def haversine_miles(lat1, lon1, lat2, lon2):
    """
    Return the distance in miles between two (lat, lon) points.
    Uses geopy's geodesic calculation.
    """
    return geodesic((float(lat1), float(lon1)), (float(lat2), float(lon2))).miles


def geocode_postcode(postcode):
    """
    Look up latitude and longitude for a UK postcode using Nominatim (OpenStreetMap).
    No API key required.

    Returns (latitude, longitude) as floats, or (None, None) on failure.
    """
    if not postcode:
        return None, None

    geolocator = Nominatim(user_agent="bristol_food_network")
    try:
        location = geolocator.geocode(f"{postcode.strip()}, UK")
        if location:
            return location.latitude, location.longitude
    except Exception:
        pass

    return None, None
