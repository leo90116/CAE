import argparse
import os
import re
import subprocess
import time
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# CONFIGURATION
SCRIPT_PATH = "Program/routes_congestion_v2_grpc.py"  # Path to your congestion script
EXCEL_PATH = f"Data/route_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
LOG_PATH = f"Log/log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
# Scheduled run window and interval
# These will be set by command-line arguments
START_TIME = None
END_TIME = None
INTERVAL_MINUTES = None
INTERVAL_SECONDS = None


def run_script():
    """Run the congestion script and capture its output."""
    result = subprocess.run(
        ["python", SCRIPT_PATH], capture_output=True, text=True, check=True
    )
    return result.stdout + "\n" + result.stderr + "\n"


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
    """
    Parse the output of the congestion script to extract useful data.

    Expected output lines (example format):
    From: {'latitude': 25.048055599999998, 'longitude': 121.516261}
    To: {'latitude': 25.0479086, 'longitude': 121.517048}
    Distance: 0.015 km
    Duration (with traffic): 123 seconds
    Duration (no traffic): 100 seconds
    Traffic condition (estimated): Heavy
    """
    lines = output.splitlines()
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_point": None,
        "end_point": None,
        "distance": None,
        "duration_with_traffic": None,
        "duration_no_traffic": None,
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
        elif "Distance:" in line:
            data["distance"] = line.split(":", 1)[1].strip()
        elif "Traffic condition (estimated):" in line:
            data["congestion_status"] = line.split(":", 1)[1].strip()

    # Calculate difference in duration and percentage difference
    min_with = data["duration_with_traffic"]
    min_no = data["duration_no_traffic"]
    if isinstance(min_with, (int, float)) and isinstance(min_no, (int, float)):
        diff_min = min_with - min_no
        data["difference_seconds"] = int(round(diff_min * 60))
        if min_no != 0:
            data["difference_percent"] = round((diff_min / min_no) * 100, 2)
        else:
            data["difference_percent"] = None

    return data


def log_to_excel(data):
    """Log the parsed data to an Excel file."""
    try:
        df = pd.read_excel(EXCEL_PATH)
    except FileNotFoundError:
        df = pd.DataFrame(columns=data.keys())

    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_excel(EXCEL_PATH, index=False)


def parse_duration(text: str) -> timedelta:
    """
    Parse total run duration.

    Supported formats:
      "90"      -> 90 minutes
      "90m"     -> 90 minutes
      "30s"     -> 30 seconds
      "1h"      -> 1 hour
      "2h30m"   -> 2 hours 30 minutes
      "1h20m15s"
      "45m10s"
      "10s"
    """
    text = text.strip().lower()

    # 純數字 → 視為「分鐘」(保持你原本邏輯)
    if text.isdigit():
        return timedelta(minutes=int(text))

    pattern = r"^(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?$"
    match = re.match(pattern, text)

    if not match:
        raise ValueError(
            f"Invalid duration format: '{text}'. "
            "Use formats like 90, 1h30m, 45m10s, 30s, 1h20m15s."
        )

    h = int(match.group(1)) if match.group(1) else 0
    m = int(match.group(2)) if match.group(2) else 0
    s = int(match.group(3)) if match.group(3) else 0

    if h == 0 and m == 0 and s == 0:
        raise ValueError("Duration cannot be 0.")

    return timedelta(hours=h, minutes=m, seconds=s)


def parse_time_interval(text: str) -> timedelta:
    """
    Parse interval between runs.

    Supported formats:
      10m, 30s, 1h, 1h30m, 1m30s, 2h15m20s, 90m, 120s
      Pure digits -> seconds.
    """
    text = text.strip().lower()

    # Pure digits -> seconds
    if text.isdigit():
        return timedelta(seconds=int(text))

    pattern = r"^(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:(\d+)s)?$"
    match = re.match(pattern, text)
    if not match:
        raise ValueError(
            f"Invalid interval format: '{text}'. "
            "Use formats like 10m, 30s, 1h, 1h30m, 1m30s, 2h15m20s."
        )

    h = int(match.group(1)) if match.group(1) else 0
    m = int(match.group(2)) if match.group(2) else 0
    s = int(match.group(3)) if match.group(3) else 0

    if h == 0 and m == 0 and s == 0:
        raise ValueError("Interval cannot be 0.")

    return timedelta(hours=h, minutes=m, seconds=s)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run congestion script repeatedly for a given duration and interval."
    )
    parser.add_argument(
        "--duration",
        type=str,
        required=True,
        help="Total duration to run (e.g. 90, 1h30m, 2h, 45m).",
    )
    parser.add_argument(
        "--interval",
        type=str,
        required=True,
        help="Interval between runs (e.g. 10m, 30s, 1h, 1h30m, 1m30s).",
    )
    parser.add_argument("--test", action="store_true", help="Run without API key")
    return parser.parse_args()


def move_Data_to_PC():
    cmd = "rsync -avz --rsync-path=' C:\\MSYS64\\usr\\bin\\rsync.exe' ~/CAE/Data/ leo90@192.168.1.105:/d/臺大/CAE/Data"
    status = subprocess.run(cmd, shell=True)
    if status.returncode == 0:
        line = "\n==Datas have moved to PC=="
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
    else:
        line = "\n!! rsync failed CHECK YOUR PC !!"
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
        exit()


def move_Log_to_PC():
    cmd = "rsync -avz --rsync-path=' C:\\MSYS64\\usr\\bin\\rsync.exe' ~/CAE/Log/ leo90@192.168.1.105:/d/臺大/CAE/Log"
    status = subprocess.run(cmd, shell=True)
    if status.returncode == 0:
        line = "\n==Logs have moved to PC=="
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
    else:
        line = "\n!! rsync failed CHECK YOUR PC !!"
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
        exit()


def check_api_key():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("!!API key not found!!\n")
        print("Please create a .env file with:")
        print("GOOGLE_MAPS_API_KEY=your_key_here")
        exit()


def main():
    check_api_key()
    args = parse_args()

    if not args.test:
        load_dotenv()
        check_api_key()
        print("==API key loaded successfully==")
    else:
        print("==TEST MODE==")

    # Determine total duration and interval
    try:
        total_duration = parse_duration(args.duration)
    except Exception as e:
        line = f"Error parsing duration '{args.duration}': {e}"
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
        return

    try:
        interval = parse_time_interval(args.interval)
    except Exception as e:
        line = f"Error parsing interval '{args.interval}': {e}"
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
        return

    if interval.total_seconds() <= 0:
        line = "Error: Interval must be greater than 0 seconds."
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")
        return

    start_dt = datetime.now()
    end_dt = start_dt + total_duration

    # Compute how many rounds to run (mirror original inclusive behavior)
    total_rounds = int(total_duration.total_seconds() // interval.total_seconds()) + 1
    line = (
        f"=={total_rounds} rounds over duration |{total_duration}| "
        f"with interval |{interval}| (start at |{start_dt.strftime('%H:%M:%S')}|)==\n"
    )
    print(line)
    with open(LOG_PATH, "a") as log_file:
        log_file.write(line + "\n")

    next_run = start_dt
    t = 1
    while t <= total_rounds:
        now = datetime.now()
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        output = run_script()
        data = parse_output(output)
        log_to_excel(data)
        line = f"Round {t}: Logged at {data['timestamp']} (interval {interval}): \n    {data}"
        print(line)
        with open(LOG_PATH, "a") as log_file:
            log_file.write(line + "\n")

        next_run += interval
        t += 1

    line = "\n==Completed all scheduled runs==\n"
    print(line)
    with open(LOG_PATH, "a") as log_file:
        log_file.write(line + "\n")
    move_Data_to_PC()
    move_Log_to_PC()


if __name__ == "__main__":
    main()
