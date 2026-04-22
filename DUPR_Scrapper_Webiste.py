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
player_id = st.text_input("DUPR ID (e.g. XXXXXX)", value="")
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

# 2. ADD THIS: Cached login to prevent "brute force" flagging
@st.cache_data(ttl=43200) 
def get_system_token():
    # It pulls from your Streamlit Secrets (Settings > Secrets on the cloud)
    try:
        email = st.secrets["dupr_auth"]["email"]
        password = st.secrets["dupr_auth"]["password"]
    
        url = "https://api.dupr.gg/auth/v1.0/login"
        payload = {"email": email, "password": password}
        
        # Add a tiny "human" delay
        time.sleep(random.uniform(0.5, 1.5))
        
        response = requests.post(url, json=payload, headers=headers_template, timeout=10)
        if response.status_code == 200:
            return response.json().get("result", {}).get("accessToken")
    except Exception as e:
        st.error(f"Authentication Error: {e}")
    return None

def get_numeric_id(dupr_id, current_token):
    url = "https://api.dupr.gg/player/v1.0/search"
    headers = {
        "Authorization": f"Bearer {current_token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "limit": 10, "offset": 0, "query": dupr_id, "exclude": [],
        "includeUnclaimedPlayers": True,
        "filter": {"lat": 33.7, "lng": -84.7, "rating": {"maxRating": None, "minRating": None}, "locationText": ""}
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            hits = response.json().get("result", {}).get("hits", [])
            for player in hits:
                if player.get("duprId", "").upper() == dupr_id.upper():
                    return str(player.get("id")), player.get("fullName")
        return None, None
    except Exception:
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
    # 3. ADD THIS: Get the fresh token first
    current_token = get_system_token()
    
    if not current_token:
        st.error("Website is currently under maintenance (Auth Error).")
        st.stop()
    
    with st.spinner("Finding player and fetching data..."):
        numeric_id, full_name = get_numeric_id(player_id, current_token)

        if numeric_id:
            st.success(f"Dashboard for: **{full_name}**")

            doubles_json = get_rating_history(numeric_id, "DOUBLES", current_token)
            singles_json = get_rating_history(numeric_id, "SINGLES", current_token)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Doubles Metrics")
                render_plot(doubles_json, "Full Doubles History", is_daily=False)
                render_plot(doubles_json, "Final Doubles Daily", is_daily=True)
            with col2:
                st.subheader("Singles Metrics")
                render_plot(singles_json, "Full Singles History", is_daily=False)
                render_plot(singles_json, "Final Singles Daily", is_daily=True)

            st.divider()
            st.header("Partner Insights")

            with st.spinner("Analyzing match history..."):
                p_stats, o_stats = get_detailed_match_history(numeric_id, current_token)

            if p_stats or o_stats:
                col_p, col_o = st.columns(2)

                with col_p:
                    st.subheader(f"Top Partners (min {min_matches} matches)")
                    pdf = build_stats_df(p_stats, min_matches)
                    if not pdf.empty:
                        st.dataframe(pdf, use_container_width=True)
                    else:
                        st.write(f"No partners with {min_matches}+ matches found.")

                with col_o:
                    st.subheader(f"Frequent Opponents (min {min_matches} matches)")
                    odf = build_stats_df(o_stats, min_matches)
                    if not odf.empty:
                        st.dataframe(odf, use_container_width=True)
                    else:
                        st.write(f"No opponents with {min_matches}+ matches found.")
            else:
                st.info("No detailed match history available to analyze.")

        else:
            st.error("Could not find player. Please check the DUPR ID!")
