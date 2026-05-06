import requests
import os

API_KEY = os.getenv("API_KEY")
HEADERS = {"X-Riot-Token": API_KEY}
PUUID = "JW45zulwekXne4bWjbnDtEfPrmOG11zsyT0KN6g9Vdj2Xw7xFbXmxN0beCU13U8RMVkRSj0DldlG0Q"

match_ids = requests.get(
    f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{PUUID}/ids",
    headers=HEADERS,
    params={"queue": 420, "count": 5}
).json()

print(match_ids)

match = requests.get(
    f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_ids[0]}",
    headers=HEADERS
).json()

def match_to_spectator_format(match):
    participants = []
    for p in match["info"]["participants"]:
        participants.append({
            "teamId": p["teamId"],
            "championId": p["championId"],
            "teamPosition": p["teamPosition"] if p["teamPosition"] != "UTILITY" else "SUPPORT",
            "puuid": p["puuid"]
        })
    return {"gameId": match["metadata"]["matchId"], "participants": participants}

mock_game = match_to_spectator_format(match)

print(mock_game)