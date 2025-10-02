import subprocess
import time
import pandas as pd
from datetime import datetime

# CONFIGURATION
SCRIPT_PATH = "routes_congestion_v2_grpc.py"  # Path to your congestion script
EXCEL_PATH = f"route_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

# Scheduled run window and interval
# These will be set by command-line arguments
START_TIME = None
END_TIME = None
INTERVAL_MINUTES = None
INTERVAL_SECONDS = None


def run_script():
    """Run the congestion script and capture its output."""
    result = subprocess.run(["python", SCRIPT_PATH], capture_output=True, text=True)
    return result.stdout


import re


def extract_point(line):
    # Extract coordinates from a line like: From: {'latitude': 25.048055599999998, 'longitude': 121.516261}
    match = re.search(r"\{.*latitude.*\}", line)
    return match.group(0) if match else None


def extract_seconds(duration_str):
    match = re.search(r"(\d+) seconds", duration_str)
    return int(match.group(1)) if match else None


def seconds_to_minutes_str(duration_str):
    sec = extract_seconds(duration_str)
    if sec is None:
        return None
    return round(sec / 60, 2)


def parse_output(output):
    lines = output.splitlines()
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_point": None,
        "end_point": None,
        "duration_with_traffic": None,
        "duration_no_traffic": None,
        "congestion_status": None,
        "difference_seconds": None,
        "difference_percent": None,
    }

    for line in lines:
        if line.startswith("From:"):
            data["start_point"] = extract_point(line)
        elif line.startswith("To:"):
            data["end_point"] = extract_point(line)
        elif "Duration (with traffic):" in line:
            duration_str = line.split(":", 1)[1].strip()
            data["duration_with_traffic"] = seconds_to_minutes_str(duration_str)
        elif "Duration (no traffic):" in line:
            duration_str = line.split(":", 1)[1].strip()
            data["duration_no_traffic"] = seconds_to_minutes_str(duration_str)
        elif "Traffic condition (estimated):" in line:
            data["congestion_status"] = line.split(":", 1)[1].strip()

    min_with = data["duration_with_traffic"]
    min_no = data["duration_no_traffic"]

    if (
        isinstance(min_with, (int, float))
        and isinstance(min_no, (int, float))
        and min_no > 0
    ):
        diff_min = min_with - min_no
        data["difference_seconds"] = int(round(diff_min * 60))
        data["difference_percent"] = round((diff_min / min_no) * 100, 2)

    return data


def log_to_excel(data):
    """Append the parsed data to the Excel file."""
    try:
        df = pd.read_excel(EXCEL_PATH)
    except FileNotFoundError:
        df = pd.DataFrame(columns=data.keys())
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_excel(EXCEL_PATH, index=False)


import argparse
from datetime import datetime, timedelta


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run congestion script at scheduled intervals within a time window."
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start time in HH:MM format (e.g., 17:00)",
    )
    parser.add_argument(
        "--end", type=str, required=True, help="End time in HH:MM format (e.g., 20:00)"
    )
    parser.add_argument(
        "--interval-minutes",
        type=int,
        required=True,
        help="Interval in minutes (e.g., 10)",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        required=True,
        help="Additional interval seconds (e.g., 0)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    today = datetime.now().date()
    start_dt = datetime.strptime(f"{today} {args.start}", "%Y-%m-%d %H:%M")
    end_dt = datetime.strptime(f"{today} {args.end}", "%Y-%m-%d %H:%M")
    interval = timedelta(minutes=args.interval_minutes, seconds=args.interval_seconds)

    if end_dt <= start_dt:
        print("Error: End time must be after start time.")
        return
    else:
        print(f"Waiting until {args.start}")

    total_rounds = (
        int((end_dt - start_dt).total_seconds() // interval.total_seconds()) + 1
    )
    print(
        f"{total_rounds} rounds in {args.start} to {args.end} / per {args.interval_minutes} minutes {args.interval_seconds} seconds"
    )

    now = datetime.now()
    if now > end_dt:
        print("Current time is past the scheduled window. Exiting.")
        return

    if now < start_dt:
        sleep_seconds = (start_dt - now).total_seconds()
        time.sleep(sleep_seconds)

    next_run = start_dt
    now = datetime.now()
    if now > start_dt:
        # Align to the next interval after now
        missed = int(((now - start_dt).total_seconds() // interval.total_seconds()) + 1)
        next_run = start_dt + timedelta(seconds=missed * interval.total_seconds())

    t = 1
    while next_run <= end_dt:
        now = datetime.now()
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
        output = run_script()
        data = parse_output(output)
        log_to_excel(data)
        print(
            f"Round {t}: Logged at {data['timestamp']} ({args.start} to {args.end} / per {args.interval_minutes} minutes {args.interval_seconds} seconds): {data}"
        )
        next_run += interval
        t += 1


if __name__ == "__main__":
    main()
