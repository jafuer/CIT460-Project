# This file creates the initial database with tables in the project folder. It only needs to be run once, unless the database file is deleted or corrupted.

import sqlite3

conn = sqlite3.connect(r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS matches (
    match_id TEXT PRIMARY KEY,
    game_duration INTEGER,
    game_version TEXT
)

""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS matches_synced (
    match_id TEXT PRIMARY KEY,
    game_duration INTEGER,
    game_version TEXT
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    puuid TEXT,
    champion TEXT,
    position TEXT,
    win INTEGER,
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    gold_earned INTEGER,
    cs INTEGER,
    FOREIGN KEY(match_id) REFERENCES matches(match_id)
)
""")

cursor.execute("""
CREATE TABLE match_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    team_id INTEGER,             
    win INTEGER,
    first_blood INTEGER,
    first_tower INTEGER,
    first_inhibitor INTEGER,
    first_baron INTEGER,
    first_dragon INTEGER,
    tower_kills INTEGER,
    inhibitor_kills INTEGER,
    baron_kills INTEGER,
    dragon_kills INTEGER,
    rift_herald_kills INTEGER,
    FOREIGN KEY(match_id) REFERENCES matches_synced(match_id)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS participant_perks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id TEXT,
    puuid TEXT,
    perks_json TEXT
)
""")


conn.commit()
conn.close()