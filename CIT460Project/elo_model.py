# James Fuerlinger
# 5/3/26
# This program prints a link which opens a local browser tab with a live game prediction
# of which team will win based on the model





import sqlite3
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, log_loss
import joblib
from sklearn.calibration import CalibratedClassifierCV

DB_PATH = r"C:\Users\james\OneDrive\Desktop\CIT460Project\league.db"

role_order = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]

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


ratings_mu = {}
ratings_sigma = {}

INIT_MU = 25.0
INIT_SIGMA = 8.333


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

    for c, r in winner_team:
        mu, sigma = get(c, r)
        ratings_mu[(c, r)] = mu + lr * err * sigma

    for c, r in loser_team:
        mu, sigma = get(c, r)
        ratings_mu[(c, r)] = mu - lr * err * sigma


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


def build_features(df):
    rows = []

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

        f = {}
        diff_sum = 0

        for role in role_order:
            c1 = t1_map[role]
            c2 = t2_map[role]

            r1_mu = ratings_mu.get((c1, role), 25.0)
            r2_mu = ratings_mu.get((c2, role), 25.0)

            r1_sig = ratings_sigma.get((c1, role), 8.333)
            r2_sig = ratings_sigma.get((c2, role), 8.333)

            d = r1_mu - r2_mu

            f[f"{role.lower()}_mu_diff"] = d
            f[f"{role.lower()}_uncertainty"] = r1_sig + r2_sig

            diff_sum += d

        f["mu_total_diff"] = diff_sum
        f["target"] = int(t1["win"].iloc[0])

        rows.append(f)

    return pd.DataFrame(rows)


df = load_data()

match_ids = df["match_id"].unique().tolist()
train_ids, test_ids = train_test_split(match_ids, test_size=0.2, random_state=42)

train_df = df[df["match_id"].isin(train_ids)].copy()
test_df = df[df["match_id"].isin(test_ids)].copy()

train_trueskill(train_df)

train_data = build_features(train_df)
test_data = build_features(test_df)

X_train = train_data.drop(columns=["target"])
y_train = train_data["target"]

X_test = test_data.drop(columns=["target"])
y_test = test_data["target"]

model = XGBClassifier(
    n_estimators=400,
    max_depth=3,
    learning_rate=0.04,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=5,
    min_child_weight=12,
    eval_metric="logloss",
    tree_method="hist"
)

model = CalibratedClassifierCV(model, method="isotonic", cv=3)
model.fit(X_train, y_train)

joblib.dump(model, "trueskill_model.pkl")

preds = model.predict(X_test)
probs = model.predict_proba(X_test)[:, 1]

print("\nAccuracy:", accuracy_score(y_test, preds))
print("Log Loss:", log_loss(y_test, probs))
print("Train acc:", model.score(X_train, y_train))
print("Test acc:", model.score(X_test, y_test))
print("Prob range:", probs.min(), "-", probs.max())