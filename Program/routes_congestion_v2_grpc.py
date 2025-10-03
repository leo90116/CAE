import os
import sys
import datetime

from google.protobuf.json_format import MessageToDict

# --- Google Maps Routing gRPC imports ---
from google.maps.routing_v2.services.routes import RoutesClient
from google.maps.routing_v2.types import (
    ComputeRoutesRequest,
    RouteTravelMode,
    RoutingPreference,
    Waypoint,
)
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials

API_KEY = os.getenv(
    "GOOGLE_MAPS_API_KEY", "YOUR_API_KEY"
)  # <-- Replace with your actual API key or set env var

DEFAULT_ORIGIN = (25.080835, 121.565052)
DEFAULT_DESTINATION = (25.068781, 121.584323)


def build_waypoint(lat, lng):
    return Waypoint(location={"lat_lng": {"latitude": lat, "longitude": lng}})


def parse_duration(duration_pb):
    """Parse google.protobuf.duration_pb2.Duration to seconds."""
    return getattr(duration_pb, "seconds", 0)


def main():
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
        print(
            "U need export GOOGLE_MAPS_API_KEY= BALABALA "
        )
        return

    # gRPC client
    client = RoutesClient(
    client_options=ClientOptions(api_key=API_KEY)
)


    # Request trafficCondition and other relevant fields
    metadata = [
        ("x-goog-api-key", API_KEY),
        (
            "x-goog-fieldmask",
            "routes.duration,routes.staticDuration,routes.distanceMeters,routes.routeLabels,routes.legs.startLocation,routes.legs.endLocation",
        ),
    ]

    request = ComputeRoutesRequest(
        origin=origin,
        destination=destination,
        travel_mode=RouteTravelMode.DRIVE,
        routing_preference=RoutingPreference.TRAFFIC_AWARE,
        compute_alternative_routes=False,
        language_code="zh-TW",
        units="METRIC",
    )

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

    now = datetime.datetime.now()
    start = MessageToDict(leg.start_location.lat_lng)
    end = MessageToDict(leg.end_location.lat_lng)
    distance_km = (
        route.distance_meters / 1000 if hasattr(route, "distance_meters") else None
    )
    duration_seconds = parse_duration(route.duration)
    duration_minutes = duration_seconds / 60 if duration_seconds else None
    duration_unaware_seconds = None
    duration_unaware_minutes = None

    print("=== Google Maps Routes API Congestion Quantifier (gRPC version) ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"From: {start}")
    print(f"To:   {end}")
    if distance_km is not None:
        print(f"Distance: {distance_km:.2f} km")
    if duration_seconds:
        print(
            f"Duration (with traffic): {duration_seconds} seconds ({duration_minutes:.2f} minutes)"
        )
    print(f"Route labels: {[str(label) for label in route.route_labels]}")

    # Show and compare with traffic and no traffic durations only
    request_unaware = ComputeRoutesRequest(
        origin=origin,
        destination=destination,
        travel_mode=RouteTravelMode.DRIVE,
        routing_preference=RoutingPreference.TRAFFIC_UNAWARE,
        compute_alternative_routes=False,
        language_code="zh-TW",
        units="METRIC",
    )
    try:
        response_unaware = client.compute_routes(
            request=request_unaware, metadata=metadata
        )
        if response_unaware.routes:
            route_unaware = response_unaware.routes[0]
            duration_unaware_seconds = parse_duration(route_unaware.duration)
            duration_unaware_minutes = (
                duration_unaware_seconds / 60 if duration_unaware_seconds else None
            )
            if duration_unaware_seconds:
                print(
                    f"Duration (no traffic): {duration_unaware_seconds} seconds ({duration_unaware_minutes:.2f} minutes)"
                )
            if duration_seconds and duration_unaware_seconds:
                diff_aware_unaware = duration_seconds - duration_unaware_seconds
                percent_aware_unaware = (
                    diff_aware_unaware / duration_unaware_seconds
                ) * 100

                if percent_aware_unaware < 10:
                    congestion_status = f"SMOOTH ({percent_aware_unaware:.1f}%)"
                elif percent_aware_unaware < 30:
                    congestion_status = f"MODERATE ({percent_aware_unaware:.1f}%)"
                elif percent_aware_unaware < 60:
                    congestion_status = f"SLOW ({percent_aware_unaware:.1f}%)"
                else:
                    congestion_status = f"SEVERE ({percent_aware_unaware:.1f}%)"
                print(f"Traffic condition: {congestion_status}")
        else:
            print(
                "Could not estimate traffic condition (no route for traffic-unaware)."
            )
    except Exception as e:
        print("Error estimating traffic condition:", e)

    # For debugging, print the full advisory object
    # print("TravelAdvisory:", MessageToDict(advisory))


if __name__ == "__main__":
    main()
