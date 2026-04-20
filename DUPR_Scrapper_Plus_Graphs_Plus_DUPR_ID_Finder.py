import requests
import json
import pandas as pd
import matplotlib.pyplot as plt

# --- CONFIGURATION ---
TOKEN = "eyJhbGciOiJSUzUxMiJ9.eyJpc3MiOiJodHRwczovL2R1cHIuZ2ciLCJpYXQiOjE3NTMxMTI0NTQsImp0aSI6IjcyNDQwODgwNTMiLCJzdWIiOiJZM1V1Yldsc1pYTXVOVFZBWjIxaGFXd3VZMjl0IiwidG9rZW5fdHlwZSI6IkFDQ0VTUyIsImV4cCI6MTc3NzY2Mjc3MX0.Nx__u9D92UudXrrzgqJylh9noxnpLoh0ple8RUHvfdlqLGCgR_65CZl0gd6eQbYTg9R_CioyYRhXtGm5yVzsKMgiL1DW3VuWTSawbFcTnt67mGLww5bNXTaSn8PFjr5i1l0a3-Ja1aMRMhixtdPasoKXrnYbfYmfoXLyHR12z0FwM-YGK7N6VgdRgM-LNzcID_fLHB3O5OwzNJBHjFI7lo4ozHJzgA8sCflismGZvPErBO_ckapU-6v5jLm5gBzk6iDvDWIh92qSganh-Nq6ZuIBcFc1zp3FnXsqTtTMcFBXWEas350-ZKatEQqzXGdxZo3QqTCuPf-Cspp9rAcWIw"
PLAYER_SEARCH_ID = "NRRGJZ"

def get_numeric_id_from_dupr_id(dupr_id):
    """Fail-safe lookup for numeric ID."""
    url = "https://api.dupr.gg/player/v1.0/search"
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {
        "limit": 10000, "offset": 0, "query": dupr_id, "exclude": [],
        "includeUnclaimedPlayers": True,
        "filter": {"lat": 33.7, "lng": -84.7, "rating": {"maxRating": None, "minRating": None}, "locationText": ""}
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        # Fail safe: Check if the request was successful
        if response.status_code != 200:
            print(f"❌ API Error: Received {response.status_code}")
            return None, None
            
        data = response.json()
        hits = data.get("result", {}).get("hits", [])
        
        # Fail safe: Check if any hits came back
        if not hits:
            print(f"⚠️ No hits found for ID {dupr_id}")
            return None, None

        for player in hits:
            if player.get("duprId", "").upper() == dupr_id.upper():
                return str(player.get("id")), player.get("fullName")
        
        return None, None
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return None, None

def plot_rating_history(json_data, title, is_daily=False):
    """
    Consolidated plotting function with double fail-safes.
    is_daily=True will trigger the 'Final Value per Day' logic.
    """
    # Fail Safe 1: Check if json_data exists or contains an error
    if not json_data or "result" not in json_data:
        print(f"⚠️ Skipping {title}: No result found in JSON.")
        return

    history = json_data['result'].get('ratingHistory', [])
    
    # Fail Safe 2: Check if history list is empty
    if not history:
        print(f"⚠️ Skipping {title}: History list is empty.")
        return

    df = pd.DataFrame(history)
    df['matchDate'] = pd.to_datetime(df['matchDate'])
    df = df.sort_values('matchDate')

    # Logic for Daily Final Rating
    if is_daily:
        df = df.groupby('matchDate').tail(1).copy()
        chart_label = "Daily Final"
    else:
        chart_label = "Full History"

    # Fail Safe 3: Check if filtering/grouping left any rows
    if df.empty:
        print(f"⚠️ Skipping {title}: No data points to plot after processing.")
        return

    # Apply Delta Filter (removes phantom recalls)
    df['delta'] = df['rating'].diff()
    df_plot = df[(df['delta'] != 0) | (df['delta'].isna())].copy()

    # Fail Safe 4: Final check before drawing
    if df_plot.empty:
        print(f"⚠️ Skipping {title}: No changes detected in rating.")
        return

    # Create Plot
    plt.figure(figsize=(12, 6))
    plt.plot(df_plot['matchDate'], df_plot['rating'], 
             marker='o', markersize=5, markerfacecolor='red', 
             linestyle='--', linewidth=1, color='#000000')
    
    plt.title(f"{title} ({chart_label})", fontsize=14)
    plt.xlabel("Date")
    plt.ylabel("Rating")
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# --- EXECUTION ---
numeric_id, full_name = get_numeric_id_from_dupr_id(PLAYER_SEARCH_ID)

if numeric_id:
    # Fetch data
    headers = {"Authorization": f"Bearer {TOKEN}"}
    
    # Process Doubles
    d_res = requests.post(f"https://api.dupr.gg/player/v1.0/{numeric_id}/rating-history", 
                          headers=headers, json={"limit":10000,"type":"DOUBLES"}).json()
    plot_rating_history(d_res, "Full Doubles Rating History", is_daily=False)
    plot_rating_history(d_res, "Final Doubles Rating History", is_daily=True)
    
    # Process Singles
    s_res = requests.post(f"https://api.dupr.gg/player/v1.0/{numeric_id}/rating-history", 
                          headers=headers, json={"limit":1000,"type":"SINGLES"}).json()
    plot_rating_history(s_res, "Full Singles Rating History", is_daily=False)
    plot_rating_history(s_res, "Final Singles Rating History", is_daily=True)