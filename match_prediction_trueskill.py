import sqlite3
import pandas as pd
import numpy as np
import requests
import joblib
import os
import gradio as gr
from sklearn.model_selection import train_test_split
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, log_loss

API_KEY = os.getenv("API_KEY")
PUUID = "JW45zulwekXne4bWjbnDtEfPrmOG11zsyT0KN6g9Vdj2Xw7xFbXmxN0beCU13U8RMVkRSj0DldlG0Q"
DB_PATH = r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db"

role_order = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]

ratings_mu = {}
ratings_sigma = {}

INIT_MU = 25.0
INIT_SIGMA = 8.333

def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT match_id, puuid, teamId, champion, position, win
        FROM diamond_participants
    """, conn)
    conn.close()
    df["position"] = df["position"].str.upper().str.strip()
    return df

def order_team(team):
    if team["position"].duplicated().any():
        return None
    team = team.set_index("position").reindex(role_order)
    if team.isnull().any().any():
        return None
    return team.reset_index()

def get(champ, role):
    key = (champ, role)
    if key not in ratings_mu:
        ratings_mu[key] = INIT_MU
        ratings_sigma[key] = INIT_SIGMA
    return ratings_mu[key], ratings_sigma[key]

def update(winner_team, loser_team, lr=0.05, beta=4.0):
    win_mu = sum(get(c, r)[0] for c, r in winner_team)
    lose_mu = sum(get(c, r)[0] for c, r in loser_team)
    win_var = sum(get(c, r)[1] ** 2 for c, r in winner_team)
    lose_var = sum(get(c, r)[1] ** 2 for c, r in loser_team)
    c = np.sqrt(win_var + lose_var + 2 * beta ** 2)
    p_win = 1 / (1 + np.exp(-(win_mu - lose_mu) / c))
    err = 1 - p_win
    for c0, r0 in winner_team:
        mu, sigma = get(c0, r0)
        ratings_mu[(c0, r0)] = mu + lr * err * sigma
    for c0, r0 in loser_team:
        mu, sigma = get(c0, r0)
        ratings_mu[(c0, r0)] = mu - lr * err * sigma

def train_trueskill(df):
    for match_id, group in df.groupby("match_id"):
        t1 = group[group["teamId"] == 100]
        t2 = group[group["teamId"] == 200]
        if len(t1) != 5 or len(t2) != 5:
            continue
        t1 = order_team(t1)
        t2 = order_team(t2)
        if t1 is None or t2 is None:
            continue
        t1_map = {row["position"]: row["champion"] for _, row in t1.iterrows()}
        t2_map = {row["position"]: row["champion"] for _, row in t2.iterrows()}
        win = int(t1["win"].iloc[0])
        team1 = [(t1_map[r], r) for r in role_order]
        team2 = [(t2_map[r], r) for r in role_order]
        if win == 1:
            update(team1, team2)
        else:
            update(team2, team1)

def get_champion_map():
    r = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
    version = r.json()[0]
    data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json").json()["data"]
    return {int(v["key"]): v["name"] for v in data.values()}

CHAMP_MAP = get_champion_map()

def build_features(game):
    participants = game["participants"]
    t1 = [p for p in participants if p["teamId"] == 100]
    t2 = [p for p in participants if p["teamId"] == 200]

    def map_team(team):
        m = {}
        for p in team:
            m[p["teamPosition"].upper()] = CHAMP_MAP.get(p["championId"], str(p["championId"]))
        return m

    t1 = map_team(t1)
    t2 = map_team(t2)

    f = {}
    total = 0

    for r in role_order:
        c1 = t1.get(r)
        c2 = t2.get(r)
        r1_mu = ratings_mu.get((c1, r), 25.0)
        r2_mu = ratings_mu.get((c2, r), 25.0)
        r1_sig = ratings_sigma.get((c1, r), 8.333)
        r2_sig = ratings_sigma.get((c2, r), 8.333)
        d = r1_mu - r2_mu
        f[f"{r.lower()}_mu_diff"] = d
        f[f"{r.lower()}_uncertainty"] = r1_sig + r2_sig
        total += d

    f["mu_total_diff"] = total
    return pd.DataFrame([f])

def normalize_role(r):
    if r == "UTILITY":
        return "SUPPORT"
    return r

def get_live_game():
    url = f"https://na1.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{PUUID}"
    headers = {"X-Riot-Token": API_KEY}
    r = requests.get(url, headers=headers)
    return r.json() if r.status_code == 200 else None

def validate_game(game):
    if not game or "participants" not in game:
        return False
    t1 = [p for p in game["participants"] if p.get("teamId") == 100]
    t2 = [p for p in game["participants"] if p.get("teamId") == 200]
    return len(t1) == 5 and len(t2) == 5

def mock_game():
    return {
        "participants": [
            {"teamId": 100, "championId": 14, "teamPosition": "TOP"},
            {"teamId": 100, "championId": 59, "teamPosition": "JUNGLE"},
            {"teamId": 100, "championId": 39, "teamPosition": "MIDDLE"},
            {"teamId": 100, "championId": 202, "teamPosition": "BOTTOM"},
            {"teamId": 100, "championId": 57, "teamPosition": "SUPPORT"},
            {"teamId": 200, "championId": 86, "teamPosition": "TOP"},
            {"teamId": 200, "championId": 107, "teamPosition": "JUNGLE"},
            {"teamId": 200, "championId": 134, "teamPosition": "MIDDLE"},
            {"teamId": 200, "championId": 498, "teamPosition": "BOTTOM"},
            {"teamId": 200, "championId": 53, "teamPosition": "SUPPORT"}
        ]
    }

def mock_game2():
    return {
        "participants": [
            {"teamId": 100, "championId": 8, "teamPosition": "TOP"},
            {"teamId": 100, "championId": 111, "teamPosition": "JUNGLE"},
            {"teamId": 100, "championId": 39, "teamPosition": "MIDDLE"},
            {"teamId": 100, "championId": 81, "teamPosition": "BOTTOM"},
            {"teamId": 100, "championId": 43, "teamPosition": "SUPPORT"},
            {"teamId": 200, "championId": 157, "teamPosition": "TOP"},
            {"teamId": 200, "championId": 104, "teamPosition": "JUNGLE"},
            {"teamId": 200, "championId": 34, "teamPosition": "MIDDLE"},
            {"teamId": 200, "championId": 222, "teamPosition": "BOTTOM"},
            {"teamId": 200, "championId": 40, "teamPosition": "SUPPORT"}
        ]
    }

model = joblib.load("trueskill_model.pkl")

def predict():
    game = mock_game()
 #   game = mock_game2()
    if not validate_game(game):
        return "<div>INVALID GAME</div>"

    X = build_features(game)
    p1 = model.predict_proba(X)[0][1]
    p2 = 1 - p1

    t1 = [p for p in game["participants"] if p["teamId"] == 100]
    t2 = [p for p in game["participants"] if p["teamId"] == 200]

    def fmt(team):
        return "".join(f"<div>{p['teamPosition']}: {CHAMP_MAP.get(p['championId'])}</div>" for p in team)

    return f"""
    <div style="display:flex;justify-content:space-between;">
        <div>
            <h2>Team 1</h2>
            {fmt(t1)}
            <h3>{p1:.1%}</h3>
        </div>
        <div>VS</div>
        <div>
            <h2>Team 2</h2>
            {fmt(t2)}
            <h3>{p2:.1%}</h3>
        </div>
    </div>
    """

df = load_data()
match_ids = df["match_id"].drop_duplicates().to_numpy()
train_ids, test_ids = train_test_split(match_ids, test_size=0.2, random_state=42)
train_df = df[df["match_id"].isin(train_ids)]
test_df = df[df["match_id"].isin(test_ids)]
train_trueskill(train_df)

with gr.Blocks() as app:
    gr.Markdown("# Live Match Predictor")
    out = gr.HTML()
    timer = gr.Timer(3)
    timer.tick(fn=predict, outputs=out)

app.launch()