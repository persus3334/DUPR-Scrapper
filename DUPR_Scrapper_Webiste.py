import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# --- PAGE CONFIG ---
st.set_page_config(page_title="DUPR Analytics Dashboard", layout="wide")

st.title("DUPR Dashboard")
st.markdown("Enter a DUPR ID below to generate rating history graphs and top teammates.")

# --- SIDEBAR / INPUTS ---
with st.sidebar:
    st.header("Settings")
    # Use the token you provided as default, but allow users to update it
    DEFAULT_TOKEN = "eyJhbGciOiJSUzUxMiJ9.eyJpc3MiOiJodHRwczovL2R1cHIuZ2ciLCJpYXQiOjE3NTMxMTI0NTQsImp0aSI6IjcyNDQwODgwNTMiLCJzdWIiOiJZM1V1Yldsc1pYTXVOVFZBWjIxaGFXd3VZMjl0IiwidG9rZW5fdHlwZSI6IkFDQ0VTUyIsImV4cCI6MTc3NzY2Mjc3MX0.Nx__u9D92UudXrrzgqJylh9noxnpLoh0ple8RUHvfdlqLGCgR_65CZl0gd6eQbYTg9R_CioyYRhXtGm5yVzsKMgiL1DW3VuWTSawbFcTnt67mGLww5bNXTaSn8PFjr5i1l0a3-Ja1aMRMhixtdPasoKXrnYbfYmfoXLyHR12z0FwM-YGK7N6VgdRgM-LNzcID_fLHB3O5OwzNJBHjFI7lo4ozHJzgA8sCflismGZvPErBO_ckapU-6v5jLm5gBzk6iDvDWIh92qSganh-Nq6ZuIBcFc1zp3FnXsqTtTMcFBXWEas350-ZKatEQqzXGdxZo3QqTCuPf-Cspp9rAcWIw"
    token = DEFAULT_TOKEN
    player_id = st.text_input("DUPR ID (e.g. XXXXXX)", value="")
    submit_button = st.button("Generate Plots")

# --- CORE FUNCTIONS ---

def get_numeric_id(dupr_id, bearer_token):
    url = "https://api.dupr.gg/player/v1.0/search"
    headers = {
        "Authorization": f"Bearer {bearer_token}",
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

def get_rating_history(numeric_id, match_type, bearer_token):
    url = f"https://api.dupr.gg/player/v1.0/{numeric_id}/rating-history"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    payload = {"limit": 10000, "type": match_type}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None

def render_plot(json_data, title, is_daily=False):
    # 1. Check if the JSON actually has results
    if not json_data or "result" not in json_data:
        st.warning(f"No data found for {title}")
        return

    history = json_data['result'].get('ratingHistory', [])
    if not history or len(history) == 0:
        st.warning(f"No match history recorded for {title}")
        return

    # 2. Convert to DataFrame
    df = pd.DataFrame(history)
    
    if df.empty or 'rating' not in df.columns:
        st.warning(f"No rating data available for {title}")
        return

    # 3. Clean and Sort
    df['matchDate'] = pd.to_datetime(df['matchDate'])
    df = df.sort_values('matchDate')

    # 4. Handle Daily Logic
    if is_daily:
        df = df.groupby('matchDate').tail(1).copy()
    
    # 5. Safety Math (The Fix)
    # If there's only 1 match, we can't calculate a 'delta' (change)
    if len(df) > 1:
        try:
            df['delta'] = df['rating'].diff()
            df_plot = df[(df['delta'] != 0) | (df['delta'].isna())].copy()
        except Exception:
            # If the math fails for any reason, just use the original data
            df_plot = df.copy()
    else:
        df_plot = df.copy()

    # 6. Create Plot
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

def get_detailed_match_history(numeric_id, token):
    url = "https://api.dupr.gg/match/v1.0/player/history"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # Using the exact payload structure from your F12
    payload = {
        "limit": 10000,
        "offset": 0,
        "playerId": int(numeric_id),
        "filter": {"matchType": "DOUBLES"} 
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            return {}, {}
        
        data = response.json()
        # FIX: Your F12 showed 'hits' inside 'result'
        matches = data.get("result", {}).get("hits", [])
        
        partner_stats = {}
        opponent_stats = {}

        for m in matches:
            teams = m.get("teams", [])
            if len(teams) < 2: continue

            user_won = False
            user_team_idx = -1
            
            # Find which team you were on
            for i, team in enumerate(teams):
                p1_id = team.get("player1", {}).get("id")
                p2_id = team.get("player2", {}).get("id")
                
                if p1_id == int(numeric_id) or p2_id == int(numeric_id):
                    user_team_idx = i
                    if team.get("winner") is True:
                        user_won = True
                    break
            
            if user_team_idx == -1: continue 

            # Partner Logic (The other person on your team)
            my_team = teams[user_team_idx]
            for p_key in ["player1", "player2"]:
                p = my_team.get(p_key, {})
                if p and p.get("id") != int(numeric_id):
                    name = p.get("fullName")
                    if name:
                        stats = partner_stats.get(name, {"wins": 0, "losses": 0, "total": 0})
                        stats["total"] += 1
                        if user_won: stats["wins"] += 1
                        else: stats["losses"] += 1
                        partner_stats[name] = stats

            # Opponent Logic (Everyone on the opposite team)
            other_team_idx = 1 if user_team_idx == 0 else 0
            other_team = teams[other_team_idx]
            for o_key in ["player1", "player2"]:
                o = other_team.get(o_key, {})
                if o:
                    name = o.get("fullName")
                    if name:
                        stats = opponent_stats.get(name, {"wins": 0, "losses": 0, "total": 0})
                        stats["total"] += 1
                        if user_won: stats["wins"] += 1
                        else: stats["losses"] += 1
                        opponent_stats[name] = stats
                    
        return partner_stats, opponent_stats
    except Exception as e:
        return {}, {}

# --- APP FLOW ---

if submit_button:
    with st.spinner("Finding player and fetching data..."):
        numeric_id, full_name = get_numeric_id(player_id, token)

        if numeric_id:
            st.success(f"Dashboard for: **{full_name}**")
            
            # 1. RATINGS SECTION
            doubles_json = get_rating_history(numeric_id, "DOUBLES", token)
            singles_json = get_rating_history(numeric_id, "SINGLES", token)

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Doubles Metrics")
                render_plot(doubles_json, "Full Doubles History", is_daily=False)
                render_plot(doubles_json, "Final Doubles Daily", is_daily=True)
            with col2:
                st.subheader("Singles Metrics")
                render_plot(singles_json, "Full Singles History", is_daily=False)
                render_plot(singles_json, "Final Singles Daily", is_daily=True)

            # 2. MATCH HISTORY / INSIGHTS SECTION
            st.divider()
            st.header("Partner Insights")
            
            with st.spinner("Analyzing match history..."):
                p_stats, o_stats = get_detailed_match_history(numeric_id, token)

            # --- INDENTATION FIXED BELOW ---
            if p_stats or o_stats:
                col_p, col_o = st.columns(2)
    
                with col_p:
                    st.subheader("Top Partners")
                    if p_stats:
                        pdf = pd.DataFrame.from_dict(p_stats, orient='index').sort_values("total", ascending=False).head(10)
                        st.dataframe(pdf) 
                    else:
                        st.write("No partner data found.")

                with col_o:
                    st.subheader("Frequent Opponents")
                    if o_stats:
                        odf = pd.DataFrame.from_dict(o_stats, orient='index').sort_values("total", ascending=False).head(10)
                        st.dataframe(odf)
                    else:
                        st.write("No opponent data found.")
            else:
                st.info("No detailed match history available to analyze.")
                
        else:
            st.error("Could not find player. Please check the DUPR ID or Token.")
