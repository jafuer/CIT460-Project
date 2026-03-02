# DO NOT RUN THIS BY ACCIDENT
# DO NOT RUN THIS BY ACCIDENT
# DO NOT RUN THIS BY ACCIDENT

# File to delete certain tables in the database so they can be re-initialized


import sqlite3

conn = sqlite3.connect(r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db")
cursor = conn.cursor()

# Drop only the problematic tables
cursor.execute("DROP TABLE IF EXISTS matches_synced")
cursor.execute("DROP TABLE IF EXISTS participants")
cursor.execute("DROP TABLE IF EXISTS match_teams")
cursor.execute("DROP TABLE IF EXISTS participant_perks")

conn.commit()
conn.close()