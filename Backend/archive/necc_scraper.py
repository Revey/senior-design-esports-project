import json
import glob

files = sorted(glob.glob("Backend/valorant/valorant_teams_*.json"))
files.append("Backend/valorant/missed_retry_results.json")

all_data = []

for file in files:
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
        all_data.extend(data)

with open("Backend/valorant/necc_scraped_valorant_team_data.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, indent=4)

print("Combined total rows:", len(all_data))
print("Saved to Backend/valorant/necc_scraped_valorant_team_data.json")
print("Files used:")
for file in files:
    print(file)


#scrapper for necc reusable if needed
"""
import requests
import json
import time

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "origin": "https://necc.leagueos.gg",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "x-leagueos-aid": "los-league",
    "x-leagueos-did": "1652185412",
    "x-leagueos-lid": "b1q6j3ea75j6zgk1s4i79dlw7",
    "x-leagueos-rid": "-1408404481"
}

COOKIES = {
    "los.sid": "bb68szh31g8txtntpjiby1d77"
}


MISSED_SCHOOLS = [
    {"schoolName": "University of Dayton", "schoolId": "4z88gk6n5tyquqy38jbe6t6ei"},
    {"schoolName": "University of Delaware", "schoolId": "57yp98tm46jlbv6sjert6min7"},
    {"schoolName": "University of Denver", "schoolId": "8og2f93ykoyrhcckj2x1yxuy7"},
    {"schoolName": "University of Detroit Mercy", "schoolId": "9dd5jstbpdvsapsgjenvegmh4"},
    {"schoolName": "University of Evansville", "schoolId": "72n9srqpitvg451ly4oeo802n"},
    {"schoolName": "University of Florida", "schoolId": "eyf7mt2s3scxam8e549vqgu2t"},
    {"schoolName": "University of Georgia", "schoolId": "5y2prrn5arevsbjh5r7xx8b1r"},
    {"schoolName": "University of Guelph", "schoolId": "04f5kmgwft5ibuyt8hr9ldrhj"},
    {"schoolName": "University of Hartford", "schoolId": "4yvxosw4ybjvore6lnrq188t1"},
    {"schoolName": "University of Hawai'i - West O'ahu", "schoolId": "4ku41i4vq7a94ouw3cubj6yzv"},
    {"schoolName": "University of Hawai'i at Manoa", "schoolId": "e2828pqg66flwwn98sw32xtbl"},
    {"schoolName": "Warner University", "schoolId": "8hwt6qfqsok1k8idzhb73fxod"},
    {"schoolName": "Wartburg College", "schoolId": "41tz5x10tp7fwh8rzk6fx6r7y"}
]


def build_logo_url(icon_id):
    if not icon_id:
        return None
    return f"https://images.leagueos.gg/{icon_id}"


def get_school_extended(school_id):
    url = f"https://api.leagueos.gg/league/groups/{school_id}/extended?hidden=0"
    response = requests.get(url, headers=HEADERS, cookies=COOKIES, timeout=20)
    response.raise_for_status()
    return response.json()


def clean_team_name(school_name, team_name):
    if not team_name:
        return None

    cleaned = team_name.strip()

    if school_name and cleaned.lower() == school_name.lower():
        return None

    return cleaned


def extract_team_rows(extended_json, school):
    rows = []
    data = extended_json.get("data", {})
    teams = data.get("teams", [])
    logo_url = build_logo_url(data.get("avatar"))

    for team in teams:
        if team.get("stdAct") != "valorant":
            continue

        rows.append({
            "schoolName": school["schoolName"],
            "logoUrl": logo_url,
            "teamName": clean_team_name(school["schoolName"], team.get("name"))
        })

    return rows


def main():
    recovered = []
    still_failed = []

    for school in MISSED_SCHOOLS:
        try:
            print("Retrying:", school["schoolName"])
            extended_json = get_school_extended(school["schoolId"])
            rows = extract_team_rows(extended_json, school)
            recovered.extend(rows)
        except Exception as e:
            print("Still failed:", school["schoolName"], e)
            still_failed.append({
                "schoolName": school["schoolName"],
                "schoolId": school["schoolId"],
                "error": str(e)
            })

        time.sleep(1)

    with open("Backend/valorant/missed_retry_results.json", "w", encoding="utf-8") as f:
        json.dump(recovered, f, indent=4)

    with open("Backend/valorant/still_failed.json", "w", encoding="utf-8") as f:
        json.dump(still_failed, f, indent=4)

    print("\nDone.")
    print("Recovered rows:", len(recovered))
    print("Still failed:", len(still_failed))


if __name__ == "__main__":
    main()

    """