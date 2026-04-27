import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import time
import random

# --- PAGE CONFIG ---
st.set_page_config(page_title="DUPR Dashboard", layout="wide")

# --- MAIN INPUT AREA ---
st.title("DUPR Dashboard")
st.markdown("Enter a DUPR ID below to generate rating history graphs and teammate history.")
# Replace this in the sidebar/main input area
player_id = st.text_input("Numeric Player ID (from DUPR URL)", value="")
min_matches = st.number_input("Min matches for partner/opponent table", min_value=1, value=10, step=1)
submit_button = st.button("Generate Results")

DEFAULT_TOKEN = ""
token = DEFAULT_TOKEN
# --- CORE FUNCTIONS ---

# 1. ADD THIS: Human-like headers to avoid bot detection
headers_template = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def get_numeric_id(dupr_id, current_token):
    url = "https://api.dupr.gg/player/v1.0/search"
    headers = {
        "Authorization": f"Bearer {current_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Origin": "https://dashboard.dupr.com",
        "Referer": "https://dashboard.dupr.com/"
    }
    payload = {
        "limit": 10, "offset": 0, "query": dupr_id.strip(), "exclude": [],
        "includeUnclaimedPlayers": True,
        "filter": {"lat": 33.8126059, "lng": -84.6343783, "rating": {"maxRating": None, "minRating": None}, "locationText": ""}
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        st.write(f"DEBUG status: {response.status_code}")
        st.write(f"DEBUG response: {response.text[:500]}")

        if response.status_code == 200:
            hits = response.json().get("result", {}).get("hits", [])
            st.write(f"DEBUG hits: {[p.get('duprId') for p in hits]}")
            for player in hits:
                if player.get("duprId", "").upper() == dupr_id.strip().upper():
                    return str(player.get("id")), player.get("fullName")
        return None, None
    except Exception as e:
        st.write(f"DEBUG exception: {e}")
        return None, None

def get_rating_history(numeric_id, match_type, current_token):
    url = f"https://api.dupr.gg/player/v1.0/{numeric_id}/rating-history"
    headers = {"Authorization": f"Bearer {current_token}"}
    payload = {"limit": 10000, "type": match_type}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def render_plot(json_data, title, is_daily=False):
    if not json_data or "result" not in json_data:
        st.warning(f"No data found for {title}")
        return

    history = json_data['result'].get('ratingHistory', [])
    if not history or len(history) == 0:
        st.warning(f"No match history recorded for {title}")
        return

    df = pd.DataFrame(history)
    if df.empty or 'rating' not in df.columns:
        st.warning(f"No rating data available for {title}")
        return

    df['matchDate'] = pd.to_datetime(df['matchDate'])
    df = df.sort_values('matchDate')

    if is_daily:
        df = df.groupby('matchDate').tail(1).copy()

    if len(df) > 1:
        try:
            df['delta'] = df['rating'].diff()
            df_plot = df[(df['delta'] != 0) | (df['delta'].isna())].copy()
        except Exception:
            df_plot = df.copy()
    else:
        df_plot = df.copy()

    if df_plot.empty:
        st.warning(f"No plottable data for {title}")
        return

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(df_plot['matchDate'], df_plot['rating'],
            marker='o', markersize=4, markerfacecolor='red',
            linestyle='--', linewidth=1, color='#000000')
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Rating")
    ax.grid(True, alpha=0.2)
    plt.xticks(rotation=45)
    st.pyplot(fig)

def get_detailed_match_history(numeric_id, current_token):
    url = f"https://api.dupr.gg/player/v1.0/{numeric_id}/history"
    headers = {
        "Authorization": f"Bearer {current_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    partner_stats = {}
    opponent_stats = {}
    offset = 0
    limit = 25
    total_fetched = 0

    while True:
        payload = {
            "filters": {"eventFormat": None},
            "limit": limit,
            "offset": offset,
            "sort": {"order": "DESC", "parameter": "MATCH_DATE"}
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code != 200:
                break

            data = response.json()
            result = data.get("result", {})
            matches = result.get("hits", [])
            has_more = result.get("hasMore", False)
            total_fetched += len(matches)

            for m in matches:
                teams = m.get("teams", [])
                if len(teams) < 2:
                    continue

                user_team_idx = -1
                user_won = False
                for i, team in enumerate(teams):
                    p1 = team.get("player1") or {}
                    p2 = team.get("player2") or {}
                    if str(p1.get("id")) == str(numeric_id) or str(p2.get("id")) == str(numeric_id):
                        user_team_idx = i
                        user_won = team.get("winner") is True
                        break

                if user_team_idx == -1:
                    continue

                # Determine user's slot by matching id field directly
                my_team = teams[user_team_idx]
                pre = my_team.get("preMatchRatingAndImpact") or {}

                if str((my_team.get("player1") or {}).get("id")) == str(numeric_id):
                    dupr_delta = pre.get("matchDoubleRatingImpactPlayer1")
                elif str((my_team.get("player2") or {}).get("id")) == str(numeric_id):
                    dupr_delta = pre.get("matchDoubleRatingImpactPlayer2")
                else:
                    dupr_delta = None

                # Partner logic
                for p_key in ["player1", "player2"]:
                    p = my_team.get(p_key) or {}
                    p_id = p.get("id")
                    if p_id and str(p_id) != str(numeric_id):
                        name = p.get("fullName", "Unknown")
                        stats = partner_stats.get(name, {
                            "wins": 0, "losses": 0, "total": 0, "dupr_delta": 0.0
                        })
                        stats["total"] += 1
                        if user_won:
                            stats["wins"] += 1
                        else:
                            stats["losses"] += 1
                        if dupr_delta is not None:
                            stats["dupr_delta"] += dupr_delta
                        partner_stats[name] = stats

                # Opponent logic
                other_team = teams[1 if user_team_idx == 0 else 0]
                for o_key in ["player1", "player2"]:
                    o = other_team.get(o_key) or {}
                    name = o.get("fullName")
                    if name:
                        stats = opponent_stats.get(name, {
                            "wins": 0, "losses": 0, "total": 0, "dupr_delta": 0.0
                        })
                        stats["total"] += 1
                        if user_won:
                            stats["wins"] += 1
                        else:
                            stats["losses"] += 1
                        if dupr_delta is not None:
                            stats["dupr_delta"] += dupr_delta
                        opponent_stats[name] = stats

            if not has_more or len(matches) == 0:
                break

            offset += limit

        except Exception as e:
            st.warning(f"Error fetching at offset {offset}: {e}")
            break

    return partner_stats, opponent_stats

def build_stats_df(stats_dict, min_matches):
    filtered = {k: v for k, v in stats_dict.items() if v["total"] >= min_matches}
    if not filtered:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(filtered, orient="index")
    df.index.name = "Name"
    
    df["win_pct"] = (df["wins"] / df["total"] * 100).round(1)
    df["dupr_delta"] = df["dupr_delta"].round(3)
    df["dupr_delta_per"] = ((df["dupr_delta"].round(3)) / (df["total"]))
    df = df.sort_values("dupr_delta_per", ascending=False)
    df = df.rename(columns={
        "wins": "W",
        "losses": "L",
        "total": "Total",
        "win_pct": "Win %",
        "dupr_delta": "DUPR +/-",
        "dupr_delta_per": "DUPR +/- per match"
    })
    
    return df[["W", "L", "Total", "Win %", "DUPR +/-", "DUPR +/- per match"]]

# --- APP FLOW ---

if submit_button:
    current_token = "eyJhbGciOiJSUzUxMiJ9.eyJpc3MiOiJodHRwczovL2R1cHIuZ2ciLCJpYXQiOjE3NzcyOTc3MTcsImp0aSI6IjYyNzAwMTMzNjciLCJzdWIiOiJjR1Z5YzNWek16TXpNekZBWjIxaGFXd3VZMjl0IiwidG9rZW5fdHlwZSI6IkFDQ0VTUyIsImV4cCI6MTc3OTg4OTcxN30.FXgKGRxgciEFHYjdNS74lJycGq3SaRAIghPHn2LJFtIAlwSbybfGvni-87ecC6mTKw8Jyh4O0G9P4NYx6KmssNr8BRl_JlK3N5Fd5iD__5RxnzCegmvYfm-YZg4-Ua18jUhN64SS2j5RjcgKJmv5BatY1yardVpcGYUeSQfrvay44HmCEofvnzMyUSGyOYkNIJiTvJyir6z1SNgFjlIdXlTw0sJNtclC3aZt0UFcJfW_LpLh7urqGYcZJlabQW5cW7_iI1VovNthbCN46bYya0ZW-Was5p-os4F5XVNgNzOyqEXuK5Rr-tODBiF_ZBtux00vBNfsoGBuTx0IQSOFuw"
    
    if not current_token:
        st.error("Website is currently under maintenance (Auth Error).")
        st.stop()

    if not player_id.strip():
        st.error("Please enter a Player ID.")
        st.stop()

    numeric_id = player_id.strip()

    with st.spinner("Fetching data..."):
        # Get name from the first match result instead of search
        doubles_json = get_rating_history(numeric_id, "DOUBLES", current_token)
        singles_json = get_rating_history(numeric_id, "SINGLES", current_token)

        # Try to extract name from rating history result
        full_name = None
        if doubles_json:
            full_name = doubles_json.get("result", {}).get("fullName")
        if not full_name and singles_json:
            full_name = singles_json.get("result", {}).get("fullName")
        if not full_name:
            full_name = f"Player {numeric_id}"

        st.success(f"Dashboard for: **{full_name}**")
        # ... rest of app flow unchanged
