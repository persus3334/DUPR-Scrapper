import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# --- PAGE CONFIG ---
st.set_page_config(page_title="DUPR Analytics Dashboard", layout="wide")

st.title("🎾 DUPR Performance Dashboard")
st.markdown("Enter a DUPR ID below to generate rating history graphs.")

# --- SIDEBAR / INPUTS ---
with st.sidebar:
    st.header("Settings")
    # Use the token you provided as default, but allow users to update it
    DEFAULT_TOKEN = "eyJhbGciOiJSUzUxMiJ9.eyJpc3MiOiJodHRwczovL2R1cHIuZ2ciLCJpYXQiOjE3NTMxMTI0NTQsImp0aSI6IjcyNDQwODgwNTMiLCJzdWIiOiJZM1V1Yldsc1pYTXVOVFZBWjIxaGFXd3VZMjl0IiwidG9rZW5fdHlwZSI6IkFDQ0VTUyIsImV4cCI6MTc3NzY2Mjc3MX0.Nx__u9D92UudXrrzgqJylh9noxnpLoh0ple8RUHvfdlqLGCgR_65CZl0gd6eQbYTg9R_CioyYRhXtGm5yVzsKMgiL1DW3VuWTSawbFcTnt67mGLww5bNXTaSn8PFjr5i1l0a3-Ja1aMRMhixtdPasoKXrnYbfYmfoXLyHR12z0FwM-YGK7N6VgdRgM-LNzcID_fLHB3O5OwzNJBHjFI7lo4ozHJzgA8sCflismGZvPErBO_ckapU-6v5jLm5gBzk6iDvDWIh92qSganh-Nq6ZuIBcFc1zp3FnXsqTtTMcFBXWEas350-ZKatEQqzXGdxZo3QqTCuPf-Cspp9rAcWIw"
    token = st.text_input("Bearer Token", value=DEFAULT_TOKEN, type="password")
    player_id = st.text_input("DUPR ID (e.g. NRRGJZ)", value="NRRGJZ")
    submit_button = st.button("Generate Dashboard")

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
    if not json_data or "result" not in json_data:
        st.warning(f"No data found for {title}")
        return

    history = json_data['result'].get('ratingHistory', [])
    if not history:
        st.warning(f"History is empty for {title}")
        return

    df = pd.DataFrame(history)
    df['matchDate'] = pd.to_datetime(df['matchDate'])
    df = df.sort_values('matchDate')

    if is_daily:
        df = df.groupby('matchDate').tail(1).copy()
    
    df['delta'] = df['rating'].diff()
    df_plot = df[(df['delta'] != 0) | (df['delta'].isna())].copy()

    if df_plot.empty:
        st.warning(f"No rating changes detected for {title}")
        return

    # Using Matplotlib inside Streamlit
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(df_plot['matchDate'], df_plot['rating'], 
             marker='o', markersize=4, markerfacecolor='red', 
             linestyle='--', linewidth=1, color='#000000')
    
    ax.set_title(title, fontsize=12)
    ax.set_xlabel("Date")
    ax.set_ylabel("Rating")
    ax.grid(True, alpha=0.2)
    plt.xticks(rotation=45)
    
    st.pyplot(fig)

# --- APP FLOW ---

if submit_button:
    with st.spinner("Finding player and fetching data..."):
        numeric_id, full_name = get_numeric_id(player_id, token)

        if numeric_id:
            st.success(f"Dashboard for: **{full_name}**")
            
            # Fetch data once per type
            doubles_json = get_rating_history(numeric_id, "DOUBLES", token)
            singles_json = get_rating_history(numeric_id, "SINGLES", token)

            # Layout: 2 Columns
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("Doubles Metrics")
                render_plot(doubles_json, "Full Doubles History", is_daily=False)
                render_plot(doubles_json, "Final Doubles Daily", is_daily=True)

            with col2:
                st.subheader("Singles Metrics")
                render_plot(singles_json, "Full Singles History", is_daily=False)
                render_plot(singles_json, "Final Singles Daily", is_daily=True)
        else:
            st.error("Could not find player. Please check the DUPR ID or Token.")