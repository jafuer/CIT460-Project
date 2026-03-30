# This file creates the initial database with tables in the project folder. It only needs to be run once, unless the database file is deleted or corrupted.

import sqlite3

conn = sqlite3.connect(r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db")
cursor = conn.cursor()


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
    firstBloodKill INTEGER,
    spell1 TEXT,
    spell2 TEXT,
    FOREIGN KEY(match_id) REFERENCES matches(match_id)
)
""")



cursor.execute("CREATE INDEX IF NOT EXISTS idx_matchesync_match_id ON matches_synced(match_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_match_id ON participants(match_id);")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants(puuid);")

conn.commit()
conn.close()