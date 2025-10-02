import requests
import sys
import os
import datetime
import re

# =========================
# Google Maps Routes API Congestion Quantifier (v2)
# =========================
# Usage:
#   1. Set your Google API key in the GOOGLE_MAPS_API_KEY environment variable,
#      or replace the API_KEY value below.
#   2. Run: python routes_congestion_v2.py
#   3. Optionally, pass origin/destination lat/lng as arguments:
#      python routes_congestion_v2.py <origin_lat> <origin_lng> <dest_lat> <dest_lng>
#
# Example coordinates:
#   Taipei Main Station: 25.0478, 121.5170
#   Taipei 101:         25.0336, 121.5646

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY")  # <-- Replace with your actual API key or set env var

DEFAULT_ORIGIN = (25.0478, 121.5170)
DEFAULT_DESTINATION = (25.0336, 121.5646)

def build_location(lat, lng):
    return {"location": {"latLng": {"latitude": lat, "longitude": lng}}}

def parse_duration(duration):
    """
    Parses duration string from Google Maps API.
    Supports formats like '123s' and ISO 8601 'PT2M30S'.
    Returns duration in seconds.
    """
    if duration.endswith('s') and duration[:-1].isdigit():
        return int(duration.rstrip('s'))
    elif duration.startswith('PT'):
        # ISO 8601 duration
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if match:
            h = int(match.group(1) or 0)
            m = int(match.group(2) or 0)
            s = int(match.group(3) or 0)
            return h * 3600 + m * 60 + s
    return 0

def get_route_with_traffic(origin, destination, api_key):
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "routes.duration,"
            "routes.distanceMeters,"
            "routes.routeLabels,"
            "routes.legs.startLocation,"
            "routes.legs.endLocation"
        )
    }

    def get_duration(routing_preference):
        payload = {
            "origin": origin,
            "destination": destination,
            "travelMode": "DRIVE",
            "routingPreference": routing_preference,
            "computeAlternativeRoutes": False,
            "routeModifiers": {
                "avoidTolls": False,
                "avoidHighways": False,
                "avoidFerries": False
            },
            "languageCode": "zh-TW",
            "units": "METRIC"
        }
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except Exception as e:
            print(f"HTTP error: {e}")
            print("Response:", getattr(response, 'text', 'No response'))
            return None, None, None, None, None, None
        data = response.json()
        try:
            route = data['routes'][0]
            duration = route['duration']
            distance = route['distanceMeters']
            labels = route.get('routeLabels', [])
            leg = route['legs'][0]
            start = leg.get('startLocation', {})
            end = leg.get('endLocation', {})
            return duration, distance, labels, start, end, data
        except Exception as e:
            print("Error parsing response:", e)
            print("Raw response:", data)
            return None, None, None, None, None, data

    # Get traffic-aware duration
    duration_aware, distance, labels, start, end, data_aware = get_duration("TRAFFIC_AWARE")
    # Get traffic-unaware duration
    duration_unaware, _, _, _, _, data_unaware = get_duration("TRAFFIC_UNAWARE")

    if duration_aware is None or duration_unaware is None:
        print("Could not retrieve route information.")
        return

    duration_aware_seconds = parse_duration(duration_aware)
    duration_unaware_seconds = parse_duration(duration_unaware)
    now = datetime.datetime.now()

    print("=== Google Maps Routes API Congestion Quantifier (v2) ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"From: {start.get('latLng', {})}")
    print(f"To:   {end.get('latLng', {})}")
    print(f"Distance: {distance/1000:.2f} km")
    print(f"Duration (no traffic): {duration_unaware} ({duration_unaware_seconds/60:.2f} minutes)")
    print(f"Duration (with traffic): {duration_aware} ({duration_aware_seconds/60:.2f} minutes)")
    print(f"Route labels: {labels}")

    # Estimate congestion
    if duration_unaware_seconds > 0:
        diff = duration_aware_seconds - duration_unaware_seconds
        percent = (diff / duration_unaware_seconds) * 100
        if percent < 10:
            congestion_status = "Low congestion"
        elif percent < 30:
            congestion_status = "Medium congestion"
        else:
            congestion_status = "High congestion"
        print(f"Estimated traffic congestion: {congestion_status} (+{percent:.1f}% travel time)")
    else:
        print("Could not estimate congestion (invalid baseline duration).")

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
