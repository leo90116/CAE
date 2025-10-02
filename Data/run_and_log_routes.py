import subprocess
import time
import pandas as pd
from datetime import datetime

# CONFIGURATION
SCRIPT_PATH = "routes_congestion_v2_grpc.py"  # Path to your congestion script
FREQUENCY_MINUTES = 5   # How often to run (minutes)
FREQUENCY_SECONDS = 0  # How often to run (seconds)
NUM_RUNS = 25            # How many times to run
EXCEL_PATH = "route_log_2.xlsx"

def run_script():
    """Run the congestion script and capture its output."""
    result = subprocess.run(
        ["python", SCRIPT_PATH],
        capture_output=True,
        text=True
    )
    return result.stdout

import re

def extract_point(line):
    # Extract coordinates from a line like: From: {'latitude': 25.048055599999998, 'longitude': 121.516261}
    match = re.search(r"\{.*latitude.*\}", line)
    return match.group(0) if match else None

def extract_seconds(duration_str):
    match = re.search(r"(\d+) seconds", duration_str)
    return int(match.group(1)) if match else None

def parse_output(output):
    """Parse relevant data from the congestion script's output."""
    lines = output.splitlines()
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "start_point": None,
        "end_point": None,
        "duration_with_traffic": None,
        "duration_no_traffic": None,
        "congestion_status": None,
        "difference_seconds": None,
        "difference_percent": None
    }
    for line in lines:
        if line.startswith("From:"):
            data["start_point"] = extract_point(line)
        elif line.startswith("To:"):
            data["end_point"] = extract_point(line)
        elif "Duration (with traffic):" in line:
            data["duration_with_traffic"] = line.split(":")[1].strip()
        elif "Duration (no traffic):" in line:
            data["duration_no_traffic"] = line.split(":")[1].strip()
        elif "Traffic condition (estimated):" in line:
            data["congestion_status"] = line.split(":")[1].strip()
    sec_with = extract_seconds(data["duration_with_traffic"]) if data["duration_with_traffic"] else None
    sec_no = extract_seconds(data["duration_no_traffic"]) if data["duration_no_traffic"] else None
    if sec_with is not None and sec_no is not None and sec_no > 0:
        diff = sec_with - sec_no
        percent = (diff / sec_no) * 100
        data["difference_seconds"] = str(diff)
        data["difference_percent"] = str(round(percent, 2))
    return data

def log_to_excel(data):
    """Append the parsed data to the Excel file."""
    try:
        df = pd.read_excel(EXCEL_PATH)
    except FileNotFoundError:
        df = pd.DataFrame(columns=data.keys())
    df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
    df.to_excel(EXCEL_PATH, index=False)

def main():
    interval = FREQUENCY_MINUTES * 60 + FREQUENCY_SECONDS
    for i in range(NUM_RUNS):
        output = run_script()
        data = parse_output(output)
        log_to_excel(data)
        print(f"Logged at {data['timestamp']}: {data}")
        if i < NUM_RUNS - 1:
            time.sleep(interval)

if __name__ == "__main__":
    main()
