# James Fuerlinger
# 2/16/26
# This program collects data from Riot API and puts it in a local database file so that it can be used for data analysis.
# PUUID is essentially just the player's ID


import requests
import sqlite3
import time
import random
import os
import threading

API_KEY = os.get_env("API_KEY")
REGION = "americas"
HEADERS = {"X-Riot-Token": API_KEY}

# https://www.sqlitetutorial.net/ is referenced for syntax and use cases of sqlite3.

# Function for avoiding 429 errors and rate limits by adding some timegates between requests with some randomness.
# API will detect patterns and assume bot-like behavior.
def rate_limit_sleep():
    sleep_time = random.uniform(0.8, 1.2)
    time.sleep(sleep_time)

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

match_holder = {}
# used riot dragon https://ddragon.leagueoflegends.com/cdn/<patch>/data/en_US/runesReforged.json to translate this
spells = {
    1: "Cleanse",
    3: "Exhaust",
    4: "Flash",
    6: "Ghost",
    7: "Heal",
    11: "Smite",
    12: "Teleport",
    14: "Ignite",
    21: "Barrier"
}
def process_puuid(puuid):
    conn = sqlite3.connect(r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db")      # moved connection and cursor inside of function to support multithreading
    cursor = conn.cursor()
    match_count = random.randint(1, 5)
    if puuid in match_holder:
        cached_matches = match_holder[puuid]
    else:
        matchlist_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        params = {"queue": 420, "start": 0, "count": match_count}
        cached_matches = safe_request(matchlist_url, params)
        if not cached_matches:
            conn.close()
            return
        match_holder[puuid] = cached_matches
        rate_limit_sleep()

    cursor.execute("SELECT match_id FROM matches_synced WHERE match_id IN ({seq})".format(
        seq=','.join(['?']*len(cached_matches))
    ), cached_matches)
    existing_matches = set(row[0] for row in cursor.fetchall()) # converted previous logic to set for faster lookup

    inserted_any = False
    participant_rows_all = []
    matches_to_insert = []

    for match_id in cached_matches:
        if match_id in existing_matches:
            continue

        match_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        match_data = safe_request(match_url)
        if not match_data or "info" not in match_data:
            continue

        info = match_data["info"]
        matches_to_insert.append((match_id, info["gameDuration"], info["gameVersion"]))

        for participant in info["participants"]:
            position = participant.get("teamPosition")
            if position == "UTILITY":
                position = "SUPPORT"
            if not position:
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
                    position = None

            champ = participant["championName"]
            if champ == "MonkeyKing":
                champ = "Wukong"

            spell1 = spells.get(participant["summoner1Id"], "UNKNOWN")
            spell2 = spells.get(participant["summoner2Id"], "UNKNOWN")

            participant_rows_all.append((
                match_id,
                participant["puuid"],
                champ,
                position,
                1 if participant["win"] else 0,
                participant["kills"],
                participant["deaths"],
                participant["assists"],
                participant["goldEarned"],
                participant["totalMinionsKilled"],
                1 if participant["firstBloodKill"] else 0,
                spell1,
                spell2
            ))

        inserted_any = True
        rate_limit_sleep()

    if inserted_any:
        cursor.executemany("""
            INSERT OR IGNORE INTO matches_synced (match_id, game_duration, game_version)
            VALUES (?, ?, ?)
        """, matches_to_insert)
        cursor.executemany("""
            INSERT OR IGNORE INTO participants (
                match_id, puuid, champion, position, win, kills, deaths, assists, gold_earned, cs, firstBloodKill, spell1, spell2
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, participant_rows_all)
        conn.commit()
    conn.close()

def threaded_main(puuids, max_threads=3): # added threading, as one thread can wait on the API request while others are processing puuids or match data
    def worker(puuid_list):
        for puuid in puuid_list:
            process_puuid(puuid)

    chunks = [puuids[i::max_threads] for i in range(max_threads)] # just round robin seperation 
    threads = []
    for chunk in chunks:
        t = threading.Thread(target=worker, args=(chunk,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

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
        if puuids:
            threaded_main(puuids, max_threads=3)
        rankIndex = (rankIndex + 1) % len(rankDivisions)


if __name__ == "__main__":
    main()