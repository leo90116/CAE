
import requests
import sys
import os
import datetime

# =========================
# Google Maps Routes API Congestion Quantifier
# =========================
# Usage:
#   1. Set your Google API key in the GOOGLE_MAPS_API_KEY environment variable,
#      or replace the API_KEY value below.
#   2. Run: python routes_congestion.py
#   3. Optionally, pass origin/destination lat/lng as arguments:
#      python routes_congestion.py <origin_lat> <origin_lng> <dest_lat> <dest_lng>
#
# Example coordinates:
#   Taipei Main Station: 25.0478, 121.5170
#   Taipei 101:         25.0336, 121.5646

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY")  # <-- Replace with your actual API key or set env var


# Default: Taipei Main Station to Taipei 101
DEFAULT_ORIGIN = (25.0478, 121.5170)
DEFAULT_DESTINATION = (25.0336, 121.5646)

def build_location(lat, lng):
    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}

def get_route_with_traffic(origin, destination, api_key):
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,"
            "routes.distanceMeters,"
            "routes.routeLabels,"
            "routes.legs.travelAdvisory,"
            "routes.legs.startLocation,"
            "routes.legs.endLocation"
        )
    }
    payload = {
        "origin": origin,
        "destination": destination,
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "computeAlternativeRoutes": False,
        "routeModifiers": {
            "avoidTolls": False,
            "avoidHighways": False,
            "avoidFerries": False
        },
        "languageCode": "zh-TW",
        "units": "METRIC"
    }
    response = requests.post(url, headers=headers, json=payload)
    try:
        response.raise_for_status()
    except Exception as e:
        print(f"HTTP error: {e}")
        print("Response:", response.text)
        return None

    data = response.json()
    try:
        route = data['routes'][0]
        duration = route['duration']
        distance = route['distanceMeters']
        labels = route.get('routeLabels', [])
        leg = route['legs'][0]
        advisory = leg.get('travelAdvisory', {})
        congestion = advisory.get('trafficRestriction', 'N/A')
        start = leg.get('startLocation', {})
        end = leg.get('endLocation', {})
        now = datetime.datetime.now()
        duration_seconds = int(duration.rstrip('s'))
        print("=== Google Maps Routes API Congestion Quantifier ===")
        print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"From: {start.get('latLng', {})}")
        print(f"To:   {end.get('latLng', {})}")
        print(f"Distance: {distance/1000:.2f} km")
        print(f"Duration (with traffic): {duration} ({duration_seconds/60:.2f} minutes)")
        print(f"Route labels: {labels}")
        print(f"Congestion info: {congestion}")
    except Exception as e:
        print("Error parsing response:", e)
        print("Raw response:", data)

def main():
    if len(sys.argv) == 5:
        try:
            origin_lat = float(sys.argv[1])
            origin_lng = float(sys.argv[2])
            dest_lat = float(sys.argv[3])
            dest_lng = float(sys.argv[4])
            origin = build_location(origin_lat, origin_lng)
            destination = build_location(dest_lat, dest_lng)
        except Exception as e:
            print("Invalid coordinates:", e)
            sys.exit(1)
    else:
        origin = build_location(*DEFAULT_ORIGIN)
        destination = build_location(*DEFAULT_DESTINATION)

    if not API_KEY or API_KEY == "YOUR_API_KEY":
        print("U need: export GOOGLE_MAPS_API_KEY= BALABALA ")
        sys.exit(1)

    get_route_with_traffic(origin, destination, API_KEY)

if __name__ == "__main__":
    main()
