import os
from google.maps.routing_v2.services.routes import RoutesClient
from google.maps.routing_v2.types import (
    ComputeRoutesRequest,
    RouteTravelMode,
    RoutingPreference,
    Waypoint,
)
from google.protobuf.json_format import MessageToDict

# =========================
# Google Maps Routes API gRPC Congestion Status Test
# =========================
# Usage:
#   1. Install dependencies:
#        pip install google-maps-routing
#   2. Set your Google API key in the GOOGLE_MAPS_API_KEY environment variable,
#      or replace the API_KEY value below.
#   3. Run: python gRPC_test.py
#   4. Optionally, pass origin/destination lat/lng as arguments:
#      python gRPC_test.py <origin_lat> <origin_lng> <dest_lat> <dest_lng>
#
# Example coordinates:
#   Taipei Main Station: 25.0478, 121.5170
#   Taipei 101:         25.0336, 121.5646

API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "YOUR_API_KEY")  # <-- Replace with your actual API key or set env var

DEFAULT_ORIGIN = (25.0478, 121.5170)
DEFAULT_DESTINATION = (25.0336, 121.5646)

def build_waypoint(lat, lng):
    return Waypoint(location={"lat_lng": {"latitude": lat, "longitude": lng}})

def main():
    import sys

    if len(sys.argv) == 5:
        try:
            origin_lat = float(sys.argv[1])
            origin_lng = float(sys.argv[2])
            dest_lat = float(sys.argv[3])
            dest_lng = float(sys.argv[4])
            origin = build_waypoint(origin_lat, origin_lng)
            destination = build_waypoint(dest_lat, dest_lng)
        except Exception as e:
            print("Invalid coordinates:", e)
            return
    else:
        origin = build_waypoint(*DEFAULT_ORIGIN)
        destination = build_waypoint(*DEFAULT_DESTINATION)

    if not API_KEY or API_KEY == "YOUR_API_KEY":
        print("You need to set your Google Maps API key. Example:")
        print("  export GOOGLE_MAPS_API_KEY=YOUR_ACTUAL_API_KEY")
        return

    client = RoutesClient()
    request = ComputeRoutesRequest(
        origin=origin,
        destination=destination,
        travel_mode=RouteTravelMode.DRIVE,
        routing_preference=RoutingPreference.TRAFFIC_AWARE,
        compute_alternative_routes=False,
        language_code="zh-TW",
        units="METRIC"
    )
    metadata = [
        ("x-goog-api-key", API_KEY),
        ("x-goog-fieldmask", "*"),  # Request all fields for testing
    ]

    try:
        response = client.compute_routes(request=request, metadata=metadata)
    except Exception as e:
        print("API error:", e)
        return

    if not response.routes:
        print("No routes found in response.")
        return

    route = response.routes[0]
    leg = route.legs[0]
    advisory = leg.travel_advisory

    print("=== Google Maps Routes API gRPC Congestion Status Test ===")
    print(f"From: {MessageToDict(leg.start_location.lat_lng)}")
    print(f"To:   {MessageToDict(leg.end_location.lat_lng)}")
    print(f"Distance: {route.distance_meters/1000:.2f} km")
    print(f"Duration (with traffic): {route.duration.seconds} seconds ({route.duration.seconds/60:.2f} minutes)")
    print(f"Route labels: {list(route.route_labels)}")

    # Congestion status field (may require Premium Plan)
    congestion = getattr(advisory, "traffic_congestion", None)
    if congestion:
        print(f"Traffic congestion status: {congestion}")
        print("Possible values: UNKNOWN_CONGESTION, LOW_CONGESTION, MEDIUM_CONGESTION, HIGH_CONGESTION, SEVERE_CONGESTION")
    else:
        print("Traffic congestion status not available in response.")
        print("This field may require Google Maps Platform Premium Plan or be region restricted.")

    # For debugging, print the full advisory object
    # print("TravelAdvisory:", MessageToDict(advisory))

if __name__ == "__main__":
    main()
