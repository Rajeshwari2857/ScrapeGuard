"""
Sample Moneycontrol scraper using SDK.
Never hits live Moneycontrol — uses mock_site /markets/v1 or v2.
"""
from scrapeguard.sdk import monitor
import requests
from bs4 import BeautifulSoup

MOCK = "http://localhost:5001"

@monitor(project="moneycontrol-gainers")
def scrape(ctx, variant="v1"):
    url = f"{MOCK}/markets/{variant}"
    # allow overriding html for demo
    resp = requests.get(url, timeout=5)
    soup = BeautifulSoup(resp.text, "lxml")
    # rebind ctx soup to fetched page
    ctx.soup = soup
    rows = ctx.select("gainer_rows", "table.gainers > tbody > tr.row")
    # mimic extraction
    data = []
    for r in rows:
        cols = r.select("td")
        if len(cols)>=3:
            data.append({"symbol": cols[0].get_text(strip=True), "price": cols[1].get_text(strip=True), "change_pct": cols[2].get_text(strip=True)})
    return data

if __name__ == "__main__":
    print("v1 (should succeed):", scrape(variant="v1"))
    print("v2 rename (should fail):", scrape(variant="v2?mut=rename"))
