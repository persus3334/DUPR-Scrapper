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
    
    # We'll pull the last 100 matches to keep it fast
    payload = {
        "limit": 10000,
        "offset": 0,
        "playerId": int(numeric_id),
        "filter": {"matchType": "DOUBLES"} 
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code != 200:
            return None
        
        matches = response.json().get("result", {}).get("matches", [])
        
        partner_stats = {}
        opponent_stats = {}

        for m in matches:
            # Determine if you won
            # DUPR marks the winning team; we check if the user was on it
            user_won = False
            teams = m.get("teams", [])
            
            # Find which team the user was on and who their partner was
            user_team = None
            other_team = None
            
            for team in teams:
                player_ids = [p.get("id") for p in team.get("players", [])]
                if int(numeric_id) in player_ids:
                    user_team = team
                    if team.get("gameVictories", 0) > 0: # Simplification for "Won"
                         user_won = True
                else:
                    other_team = team
            
            # Record Partner Stats
            if user_team:
                for p in user_team.get("players", []):
                    if p.get("id") != int(numeric_id):
                        name = p.get("fullName")
                        stats = partner_stats.get(name, {"wins": 0, "losses": 0, "total": 0})
                        stats["total"] += 1
                        if user_won: stats["wins"] += 1
                        else: stats["losses"] += 1
                        partner_stats[name] = stats

            # Record Opponent Stats
            if other_team:
                for o in other_team.get("players", []):
                    name = o.get("fullName")
                    stats = opponent_stats.get(name, {"wins": 0, "losses": 0, "total": 0})
                    stats["total"] += 1
                    if user_won: stats["wins"] += 1
                    else: stats["losses"] += 1
                    opponent_stats[name] = stats
                    
        return partner_stats, opponent_stats
    except:
        return None, None

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

            if p_stats and o_stats:
                col_p, col_o = st.columns(2)
                
                with col_p:
                    st.subheader("Top Partners")
                    pdf = pd.DataFrame.from_dict(p_stats, orient='index')
                    if not pdf.empty:
                        # Sort by most games played together
                        pdf = pdf.sort_values("total", ascending=False).head(10)
                        # Optional: calculate win %
                        pdf['win_rate'] = (pdf['wins'] / pdf['total'] * 100).round(1).astype(str) + '%'
                        st.table(pdf[['wins', 'losses', 'total', 'win_rate']])
                    else:
                        st.write("No partner data found.")

                with col_o:
                    st.subheader("Frequent Opponents")
                    odf = pd.DataFrame.from_dict(o_stats, orient='index')
                    if not odf.empty:
                        odf = odf.sort_values("total", ascending=False).head(10)
                        odf['win_rate'] = (odf['wins'] / odf['total'] * 100).round(1).astype(str) + '%'
                        # Renaming 'wins' to 'your_wins' to be clear
                        odf = odf.rename(columns={"wins": "won_vs", "losses": "lost_vs"})
                        st.table(odf[['won_vs', 'lost_vs', 'total', 'win_rate']])
                    else:
                        st.write("No opponent data found.")
            else:
                st.info("No detailed match history available to analyze.")
                
        else:
            st.error("Could not find player. Please check the DUPR ID or Token.")
