# This program creates a json file so I can preview what comes with a full match call

import json
import os
import requests

API_KEY = os.getenv("API_KEY")
REGION = "americas"
match_id = "NA1_5522616279"

url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
r = requests.get(url, headers={"X-Riot-Token": API_KEY})

if r.status_code == 200:
    match_data = r.json()
    with open("match_data.json", "w", encoding="utf-8") as f:
        json.dump(match_data, f, indent=2)
    print("Match JSON saved to match_data.json")
else:
    print("Error:", r.status_code)
