import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# --- PAGE CONFIG ---
st.set_page_config(page_title="DUPR Analytics Dashboard", layout="wide")

st.title("DUPR Dashboard")
st.markdown("Generate rating history graphs and comprehensive teammate insights.")

# --- SIDEBAR / INPUTS ---
with st.sidebar:
    st.header("Settings")
    DEFAULT_TOKEN = "eyJhbGciOiJSUzUxMiJ9.eyJpc3MiOiJodHRwczovL2R1cHIuZ2ciLCJpYXQiOjE3NTMxMTI0NTQsImp0aSI6IjcyNDQwODgwNTMiLCJzdWIiOiJZM1V1Yldsc1pYTXVOVFZBWjIxaGFXd3VZMjl0IiwidG9rZW5fdHlwZSI6IkFDQ0VTUyIsImV4cCI6MTc3NzY2Mjc3MX0.Nx__u9D92UudXrrzgqJylh9noxnpLoh0ple8RUHvfdlqLGCgR_65CZl0gd6eQbYTg9R_CioyYRhXtGm5yVzsKMgiL1DW3VuWTSawbFcTnt67mGLww5bNXTaSn8PFjr5i1l0a3-Ja1aMRMhixtdPasoKXrnYbfYmfoXLyHR12z0FwM-YGK7N6VgdRgM-LNzcID_fLHB3O5OwzNJBHjFI7lo4ozHJzgA8sCflismGZvPErBO_ckapU-6v5jLm5gBzk6iDvDWIh92qSganh-Nq6ZuIBcFc1zp3FnXsqTtTMcFBXWEas350-ZKatEQqzXGdxZo3QqTCuPf-Cspp9rAcWIw"
    token = DEFAULT_TOKEN
    player_id = st.text_input("DUPR ID (e.g. XXXXXX)", value="")
    submit_button = st.button("Generate Dashboard")

# --- CORE FUNCTIONS ---

def get_numeric_id(dupr_id, bearer_token):
    url = "https://api.dupr.gg/player/v1.0/search"
    headers = {"Authorization": f"Bearer {bearer_token}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    payload = {"limit": 10, "offset": 0, "query": dupr_id, "includeUnclaimedPlayers": True}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            hits = response.json().get("result", {}).get("hits", [])
            for player in hits:
                if player.get("duprId", "").upper() == dupr_id.upper():
                    return str(player.get("id")), player.get("fullName")
    except: pass
    return None, None

def get_rating_history(numeric_id, match_type, bearer_token):
    url = f"https://api.dupr.gg/player/v1.0/{numeric_id}/rating-history"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    payload = {"limit": 10000, "type": match_type}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        return response.json() if response.status_code == 200 else None
    except: return None

def render_plot(json_data, title, is_daily=False):
    if not json_data or "result" not in json_data:
        st.warning(f"No data for {title}")
        return
    history = json_data['result'].get('ratingHistory', [])
    if not history: return
    
    df = pd.DataFrame(history)
    df['matchDate'] = pd.to_datetime(df['matchDate'])
    df = df.sort_values('matchDate')
    if is_daily:
        df = df.groupby('matchDate').tail(1).copy()
    
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df['matchDate'], df['rating'], marker='o', markersize=3, linestyle='--', linewidth=1, color='#007BFF')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    st.pyplot(fig)

def get_detailed_match_history(numeric_id, token):
    url = f"https://api.dupr.gg/player/v1.0/{numeric_id}/history"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}

    partner_stats, opponent_stats = {}, {}
    offset, limit = 0, 25

    while True:
        payload = {
            "filters": {"eventFormat": None},
            "limit": limit, "offset": offset,
            "sort": {"order": "DESC", "parameter": "MATCH_DATE"}
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code != 200: break

            result = response.json().get("result", {})
            matches = result.get("hits", [])
            
            for m in matches:
                teams = m.get("teams", [])
                if len(teams) < 2: continue

                user_team_idx, user_won = -1, False
                for i, team in enumerate(teams):
                    p1, p2 = team.get("player1") or {}, team.get("player2") or {}
                    if str(p1.get("id")) == str(numeric_id) or str(p2.get("id")) == str(numeric_id):
                        user_team_idx, user_won = i, team.get("winner") is True
                        break

                if user_team_idx == -1: continue

                # Partners
                my_team = teams[user_team_idx]
                for p_key in ["player1", "player2"]:
                    p = my_team.get(p_key) or {}
                    if p.get("id") and str(p.get("id")) != str(numeric_id):
                        name = p.get("fullName", "Unknown")
                        s = partner_stats.get(name, {"wins": 0, "losses": 0, "total": 0})
                        s["total"] += 1
                        if user_won: s["wins"] += 1
                        else: s["losses"] += 1
                        partner_stats[name] = s

                # Opponents
                other_team = teams[1 if user_team_idx == 0 else 0]
                for o_key in ["player1", "player2"]:
                    o = other_team.get(o_key) or {}
                    if o.get("fullName"):
                        name = o.get("fullName")
                        s = opponent_stats.get(name, {"wins": 0, "losses": 0, "total": 0})
                        s["total"] += 1
                        if user_won: s["wins"] += 1
                        else: s["losses"] += 1
                        opponent_stats[name] = s

            if not result.get("hasMore") or len(matches) == 0 or offset > 500: break # Safety cap
            offset += limit
        except: break

    return partner_stats, opponent_stats

# --- APP FLOW ---

if submit_button and player_id:
    with st.spinner("Analyzing Player Data..."):
        numeric_id, full_name = get_numeric_id(player_id, token)

        if numeric_id:
            st.header(f"Insights for {full_name}")
            
            # 1. Rating History
            col1, col2 = st.columns(2)
            with col1:
                render_plot(get_rating_history(numeric_id, "DOUBLES", token), "Doubles Progression")
            with col2:
                render_plot(get_rating_history(numeric_id, "SINGLES", token), "Singles Progression")

            # 2. Partner Analysis
            st.divider()
            p_stats, o_stats = get_detailed_match_history(numeric_id, token)

            if p_stats:
                st.subheader("Partner Performance (Min 5 Games)")
                # Processing for Table
                data = []
                for name, s in p_stats.items():
                    if s["total"] >= 5:
                        win_p = (s["wins"] / s["total"]) * 100
                        data.append({"Partner": name, "W": s["wins"], "L": s["losses"], "Total": s["total"], "Win %": round(win_p, 1)})
                
                df_partners = pd.DataFrame(data).sort_values("Win %", ascending=False)
                st.dataframe(df_partners, use_container_width=True, hide_index=True)
            else:
                st.info("No detailed partner history found.")
        else:
            st.error("Player not found. Check DUPR ID.")
