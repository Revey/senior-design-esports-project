"""
Scrapes role play percentages for a player from op.gg.
Uses Playwright for JS rendering since op.gg is a dynamic SPA.

Install dependencies:
    pip install playwright
    playwright install chromium
"""

from playwright.sync_api import sync_playwright

ROLES = ["Top", "Jungle", "Mid", "Bot", "Support"]

URL = "https://op.gg/lol/summoners/na/Shimmer-NA1?queue_type=SOLORANKED"


def extract_role_percentages(page):
    """
    The role bars are rendered as divs with inline style="height: X%".
    Each role has a filled bar inside a container bar.
    We look for the inner 'filled' bars (bg-main-500) and read their height %.
    """
    # Wait for the role bars to appear
    page.wait_for_selector("ul.hidden.flex-row", timeout=15000)

    # Select all li.flex.flex-col.items-center.gap-\[8px\] inside the ul
    # Each <li> corresponds to one role bar group
    bars = page.query_selector_all("ul.hidden.flex-row li.flex.flex-col.items-center")

    percentages = []
    for bar in bars:
        # The filled inner div has class bg-main-500
        filled = bar.query_selector("div.bg-main-500")
        if filled:
            style = filled.get_attribute("style") or ""
            # Extract height value, e.g. "width: 100%; height: 95%;"
            for part in style.split(";"):
                part = part.strip()
                if part.startswith("height:"):
                    val = part.split(":")[1].strip().replace("%", "")
                    try:
                        percentages.append(float(val))
                    except ValueError:
                        percentages.append(0.0)
                    break

    return percentages


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        print(f"Loading: {URL}")
        page.goto(URL, wait_until="networkidle", timeout=30000)

        percentages = extract_role_percentages(page)
        browser.close()

    if not percentages:
        print("No role bars found. The page structure may have changed.")
        return

    # Pad or trim to 5 roles
    while len(percentages) < 5:
        percentages.append(0.0)

    print("\n=== Shimmer#NA1 — Role Play Percentages (Solo Ranked) ===\n")
    for role, pct in zip(ROLES, percentages[:5]):
        bar = "█" * int(pct / 5)  # simple ASCII bar (max 20 chars)
        print(f"  {role:<8}  {bar:<20}  {pct:.0f}%")
    print()


if __name__ == "__main__":
    main()