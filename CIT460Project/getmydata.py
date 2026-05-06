# James Fuerlinger
# 5/3/26
# This program collects data from Riot API and puts it in a local database file so that it can be used for data analysis.
# PUUID is essentially just the player's ID

# Made in sprint 3, just fetches Diamond rank player matches



import requests
import sqlite3
import time
import random
import threading
import os


API_KEY = os.getenv("API_KEY")
REGION = "americas"
HEADERS = {"X-Riot-Token": API_KEY}

def get_current_patch():
    versions = requests.get("https://ddragon.leagueoflegends.com/api/versions.json").json()
    v = versions[0]
    parts = v.split(".")
    return parts[0] + "." + parts[1]
    
CURRENT_PATCH = get_current_patch()

def safe_request(url, params=None):
    while True:
        r = requests.get(url, headers=HEADERS, params=params)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", 5))
            print(f"  Rate limited, sleeping {retry_after}s")
            time.sleep(retry_after)
            continue
        if r.status_code != 200:
            print(f"  Failed with {r.status_code}, returning None")
            return None
        return r.json()

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

db_lock = threading.Lock()
api_lock = threading.Lock()
api_calls = 0
api_reset_time = time.time() + 120

def rate_limit_sleep_api():
    global api_calls, api_reset_time
    with api_lock:
        now = time.time()
        
        if now >= api_reset_time:
            api_calls = 0
            api_reset_time = now + 120

        api_calls += 1

        if api_calls >= 95:  
            sleep_time = api_reset_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            api_calls = 0
            api_reset_time = time.time() + 120

    
    time.sleep(random.uniform(0.3, 0.5))

def process_puuid(puuid):
    conn = sqlite3.connect(r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db")
    cursor = conn.cursor()

    match_count = 10

    matchlist_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
    params = {"queue": 420, "start": 0, "count": match_count}
    cached_matches = safe_request(matchlist_url, params)
    if not cached_matches:
        conn.close()
        return
        
    rate_limit_sleep_api()

    

    cursor.execute(
        "SELECT match_id FROM matches_diamond WHERE match_id IN ({})".format(
            ",".join(["?"] * len(cached_matches))
        ),
        cached_matches
    )
    existing_matches = set(row[0] for row in cursor.fetchall())

    for match_id in cached_matches:
        if match_id in existing_matches:
            continue

        match_url = f"https://{REGION}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        match_data = safe_request(match_url)
        if not match_data or "info" not in match_data:
            continue

        info = match_data["info"]

        if CURRENT_PATCH not in info["gameVersion"]:
            continue

        participant_rows = []
        valid_match = True

        for participant in info["participants"]:
            position = participant.get("teamPosition")
            team_id = participant.get("teamId")

            if position == "UTILITY":
                position = "SUPPORT"

            if not position:
                role = participant.get("role")
                lane = participant.get("lane")
                if role == "DUO_CARRY":
                    position = "BOTTOM"
                elif role == "DUO_SUPPORT":
                    position = "SUPPORT"
                elif lane == "JUNGLE":
                    position = "JUNGLE"
                elif lane == "TOP":
                    position = "TOP"
                elif lane == "MID":
                    position = "MIDDLE"
                else:
                    position = None

            if position is None:
                valid_match = False
                break

            champ = participant["championName"]

            spell1 = spells.get(participant["summoner1Id"], "UNKNOWN")
            spell2 = spells.get(participant["summoner2Id"], "UNKNOWN")

            participant_rows.append((
                match_id,
                participant["puuid"],
                champ,
                position,
                team_id,
                1 if participant["win"] else 0,
                spell1,
                spell2
            ))

        if not valid_match:
            continue
        if len(participant_rows) != 10:
            continue

        try:
            with db_lock:
                cursor.execute("""
                    INSERT OR IGNORE INTO matches_diamond (match_id, game_version)
                    VALUES (?, ?)
                """, (match_id, info["gameVersion"]))

                cursor.executemany("""
                    INSERT OR IGNORE INTO diamond_participants (
                        match_id, puuid, champion, position, teamId, win, spell1, spell2
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, participant_rows)

                conn.commit()
                
                
                
        except Exception as e:
            print(f"  DB error on {match_id}: {e}")
            conn.rollback()

        rate_limit_sleep_api()

    conn.close()

def threaded_main(puuids, max_threads=2):
    def worker(puuid_list):
        for puuid in puuid_list:
            process_puuid(puuid)

    chunks = [puuids[i::max_threads] for i in range(max_threads)]
    threads = []

    for chunk in chunks:
        t = threading.Thread(target=worker, args=(chunk,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

def get_rank_puuids(queue="RANKED_SOLO_5x5", tier="", division=""):
    puuids = []
    page = 1
    while page <= 8:
        url = f"https://na1.api.riotgames.com/lol/league/v4/entries/{queue}/{tier}/{division}"
        players = safe_request(url, params={"page": page})
        if not players:
            break
        puuids.extend(player["puuid"] for player in players if "puuid" in player)
        page += 1
        time.sleep(0.5)
    return puuids
    

def get_diamond_puuids():
    divisions = ["I", "II", "III", "IV"]
    puuids = []

    for div in divisions:
        players = get_rank_puuids(tier="DIAMOND", division=div)

        if players:
            puuids.extend(players)

        time.sleep(0.5) 
        print("PUUID COUNT:", len(puuids))
        print(div, len(players))
    return list(set(puuids))

def main():
    try:
        hours = float(input("How many hours should the program run? "))
    except ValueError:
        return

    end_time = time.time() + hours * 3600

    puuids = get_diamond_puuids()
    random.shuffle(puuids)

    batch_size = 30

    while time.time() < end_time:
        batch = random.sample(puuids, k=min(batch_size, len(puuids)))
        threaded_main(batch, max_threads=2)

if __name__ == "__main__":
    main()