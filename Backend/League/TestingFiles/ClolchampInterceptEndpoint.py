
import json
import time
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
 
BASE_SITE  = "https://universityesportsna.riotgames.com"
TOURN_PATH = "/competition/tournament/2025-clol-championship"
TOURN_URL  = BASE_SITE + TOURN_PATH
 
TARGET_API = "api-ggtech.leagueoflegends.com"
 
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
 
all_calls: list[dict] = []   # accumulates every intercepted call
 
 
def attach_listener(page, label: str):
    """Register a response listener that logs every ggtech API call."""
    def on_response(response):
        url = response.url
        if TARGET_API not in url:
            return
        entry = {"page": label, "url": url, "status": response.status, "body": None}
        try:
            ct = response.headers.get("content-type", "")
            if "json" in ct and response.status == 200:
                entry["body"] = response.json()
        except Exception:
            pass
        all_calls.append(entry)
        print(f"  [{response.status}] {url}")
    page.on("response", on_response)
 
 
def wait_idle(page, timeout=15_000):
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
    except PWTimeout:
        pass
 
 
def main():
    print("=" * 70)
    print("ggtech API endpoint interceptor")
    print("=" * 70)
 
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="en-US",
        )
 
        # ── 1. Load the tournament page ───────────────────────────────────────
        print(f"\n[1] Loading tournament page: {TOURN_URL}")
        page = context.new_page()
        attach_listener(page, "tournament")
 
        try:
            page.goto(TOURN_URL, wait_until="networkidle", timeout=40_000)
        except PWTimeout:
            print("  (networkidle timed out — continuing)")
 
        # Extra wait for lazy-loaded content
        time.sleep(3)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
 
        # ── 2. Find team links ────────────────────────────────────────────────
        print(f"\n[2] Looking for team links …")
        team_links = []
 
        # Try multiple selector patterns
        for sel in ["a[href*='/team/']", "a[href*='team']", "[class*='team'] a", "[class*='Team'] a"]:
            anchors = page.query_selector_all(sel)
            if anchors:
                for a in anchors:
                    href = a.get_attribute("href") or ""
                    text = a.inner_text().strip()
                    if href and href not in [l[1] for l in team_links]:
                        team_links.append((text or href, href))
                if team_links:
                    print(f"  Found {len(team_links)} link(s) via '{sel}'")
                    break
 
        if not team_links:
            print("  No team links found via DOM — dumping all <a> hrefs:")
            for a in page.query_selector_all("a"):
                href = a.get_attribute("href") or ""
                if href and href != "#":
                    print(f"    {href}")
 
        # ── 3. Visit each team page (first 3 to keep it fast) ────────────────
        for i, (name, href) in enumerate(team_links[:3]):
            full = href if href.startswith("http") else BASE_SITE + href
            print(f"\n[3.{i+1}] Visiting team: {name}  ({full})")
            tpage = context.new_page()
            attach_listener(tpage, f"team:{name}")
            try:
                tpage.goto(full, wait_until="networkidle", timeout=30_000)
                time.sleep(2)
            except PWTimeout:
                print("  (timed out)")
            tpage.close()
 
        browser.close()
 
    # ── 4. Print summary ──────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"INTERCEPTED {len(all_calls)} ggtech API call(s)")
    print(f"{'='*70}")
 
    for call in all_calls:
        print(f"\n  Page   : {call['page']}")
        print(f"  URL    : {call['url']}")
        print(f"  Status : {call['status']}")
        if call["body"] is not None:
            preview = json.dumps(call["body"], indent=2, default=str)[:600]
            print(f"  Body   : {preview}")
 
    # Save full bodies for inspection
    with open("intercepted_calls.json", "w") as f:
        json.dump(all_calls, f, indent=2, default=str)
    print(f"\n  Full data saved to intercepted_calls.json")
    print("\nLook for endpoints that contain team names, gameName, tagLine, or")
    print("summonerName — those are the ones to add to the scraper.")
 
 
if __name__ == "__main__":
    main()