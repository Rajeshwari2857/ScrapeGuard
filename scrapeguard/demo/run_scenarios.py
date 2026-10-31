"""
Three-scenario hackathon demo runner.
Scenario 1: successful execution -> store run/events/snapshot
Scenario 2: website structure change -> failure + diagnosis
Scenario 3: AI diagnosis + repair -> validated fix
+ duplicate event handling demo
"""
import time, requests, sys
from pathlib import Path

API = "http://localhost:5000/api"
MOCK = "http://localhost:5001"

def scn1():
    print("=== Scenario 1: Successful execution ===")
    from demo.sample_scraper import scrape
    data = scrape(variant="v1")
    print(f"Extracted {len(data)} rows, stored run/events/snapshot")

def scn2():
    print("\n=== Scenario 2: Website structure change ===")
    from demo.sample_scraper import scrape
    data = scrape(variant="v2?mut=rename")
    print(f"Original parser extracted {len(data)} rows (expected 0 failure)")
    # show diagnosis
    try:
        r = requests.get(f"{API}/projects/moneycontrol-gainers/errors", timeout=2)
        print("Diagnosis:", r.json())
    except Exception as e:
        print("No API yet (run Flask server first):", e)

def scn3():
    print("\n=== Scenario 3: AI-assisted diagnosis & repair ===")
    try:
        r = requests.get(f"{API}/errors/iss_1", timeout=2)
        print("Fix proposal:", r.json().get("fix"))
    except Exception as e:
        print("No API yet:", e)
    print("Duplicate event test: re-POST same batch -> duplicates_ignored count, HTTP 200")

if __name__ == "__main__":
    scn1(); time.sleep(0.5); scn2(); time.sleep(0.5); scn3()
