# James Fuerlinger
# 2/16/26
# This program collects data from Riot API and puts it in a local database file so that it can be used for data analysis.
# PUUID is essentially just the players ID


import requests
import sqlite3
import time
import random
import os

API_KEY = os.getenv("RIOT_API")
REGION = "americas"
HEADERS = {"X-Riot-Token": API_KEY}

conn = sqlite3.connect(r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db")
cursor = conn.cursor()
# https://www.sqlitetutorial.net/ is referenced for syntax and use cases of sqlite3.

# Function for avoiding 429 errors and rate limits by adding some timegates between requests with some randomness.
# API will detect patterns and assume bot-like behavior.
def rate_limit_sleep():
    sleep_time = random.uniform(1.4, 1.8)
    time.sleep(sleep_time)
def get_match_data(match_id, api_key):
    import requests

    url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": api_key}

    response = requests.get(url, headers=headers)
    return response.json()

def safe_request(url, params=None):
    while True:
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 5))
            time.sleep(retry_after)
            continue
        if r.status_code != 200:
            return None
        return r.json()

def process_puuid(puuid):
    match_count = random.randint(1, 5) # grabs a random amount of matches per player to get a bit more value out of each person without skewing data
    matchlist_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"queue": 420, "start": 0, "count": match_count}

    match_ids = safe_request(matchlist_url, params)
    if not match_ids:
        return

    rate_limit_sleep()

    inserted_any = False

    for match_id in match_ids:
        cursor.execute("SELECT 1 FROM matches_synced WHERE match_id = ?", (match_id,))
        if cursor.fetchone():
            continue

        match_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        match_data = safe_request(match_url)
        if not match_data:
            continue

        info = match_data["info"]

        # Match entries
        cursor.execute("""
            INSERT INTO matches_synced (match_id, game_duration, game_version)
            VALUES (?, ?, ?)
        """, (match_id, info["gameDuration"], info["gameVersion"]))

        # Player statistic entries
        for participant in info["participants"]:
            # Riot API does not supply position, but I want it for my analysis so I derive it from other data
            position = participant.get("teamPosition")
            if position == "UTILITY":
                position = "SUPPORT"
            if not position:
                # teamPosition is newer, and seems like there are some inconsistencies with it so this is a backup method
                role = participant.get("role")
                lane = participant.get("lane")
                if role == "DUO_CARRY":
                    position = "BOT"
                elif role == "DUO_SUPPORT":
                    position = "SUPPORT"
                elif lane == "JUNGLE":
                    position = "JUNGLE"
                elif lane == "TOP":
                    position = "TOP"
                elif lane == "MID":
                    position = "MID"
                else:
                    position = "null"
            if participant["championName"] == "MonkeyKing":
                participant["championName"] = "Wukong"
            
            cursor.execute("""
                INSERT OR IGNORE INTO participants (
                    match_id, puuid, champion, position, win, kills, deaths, assists, gold_earned, cs
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                match_id,
                participant["puuid"],
                participant["championName"],
                position, 
                1 if participant["win"] else 0,
                participant["kills"],
                participant["deaths"],
                participant["assists"],
                participant["goldEarned"],
                participant["totalMinionsKilled"]
            ))

        inserted_any = True
        rate_limit_sleep()  # sleep once per match

    # Saves overhead by commiting outside of loop when data was actually entered
    if inserted_any:
        conn.commit()

def get_rank_puuids(queue="RANKED_SOLO_5x5", tier="", division=""):
    puuids = []

    if tier.upper() == "MASTER":
        url = f"https://na1.api.riotgames.com/lol/league/v4/masterleagues/by-queue/{queue}"
        data = safe_request(url)
        if not data:
            return []

        entries = data.get("entries", [])

        for entry in entries:
            summoner_id = entry.get("summonerId")
            if not summoner_id:
                continue

            # this portion is for an edge case where master rank gives summonerID instead of puuid, so it converts the summonerID to puuid
            summoner_url = f"https://na1.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
            summoner_data = safe_request(summoner_url)
            if not summoner_data:
                continue

            puuid = summoner_data.get("puuid")
            if puuid:
                puuids.append(puuid)

            rate_limit_sleep()

        return puuids

    else:
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/{queue}/{tier}/{division}"
        players = safe_request(url)
        if not players:
            return []

        return [player["puuid"] for player in players if "puuid" in player]

# Sampling strategy with handpicked rank distribution that I believe represents the total playerbase pretty well.
# Master rank does not have divisions, so it is handled a bit differently.
rankDivisions = [
    ("SILVER", "III"), # 73rd percentile
    ("GOLD", "II"), # 40th percentile
    ("EMERALD", "IV"), # 13.6th percentile
    ("DIAMOND", "III"), # 2.86th percentile
    ("MASTER", "") # 1.15th percentile
    # from https://www.leagueofgraphs.com/rankings/rank-distribution
]


def main():
    try:
        hours = float(input("How many hours should the program run? "))
    except ValueError:
        return

    endTime = time.time() + (hours * 60 * 60)
    rankIndex = 0

    while time.time() < endTime:
        tier, division = rankDivisions[rankIndex]
        puuids = get_rank_puuids(tier=tier, division=division)
        for puuid in puuids:
            if time.time() >= endTime:
                break
            process_puuid(puuid)

        rankIndex = (rankIndex + 1) % len(rankDivisions)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()