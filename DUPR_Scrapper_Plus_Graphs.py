import requests
import json
import pandas as pd
import matplotlib.pyplot as plt

# Your constants
TOKEN = "eyJhbGciOiJSUzUxMiJ9.eyJpc3MiOiJodHRwczovL2R1cHIuZ2ciLCJpYXQiOjE3NTMxMTI0NTQsImp0aSI6IjcyNDQwODgwNTMiLCJzdWIiOiJZM1V1Yldsc1pYTXVOVFZBWjIxaGFXd3VZMjl0IiwidG9rZW5fdHlwZSI6IkFDQ0VTUyIsImV4cCI6MTc3NzY2Mjc3MX0.Nx__u9D92UudXrrzgqJylh9noxnpLoh0ple8RUHvfdlqLGCgR_65CZl0gd6eQbYTg9R_CioyYRhXtGm5yVzsKMgiL1DW3VuWTSawbFcTnt67mGLww5bNXTaSn8PFjr5i1l0a3-Ja1aMRMhixtdPasoKXrnYbfYmfoXLyHR12z0FwM-YGK7N6VgdRgM-LNzcID_fLHB3O5OwzNJBHjFI7lo4ozHJzgA8sCflismGZvPErBO_ckapU-6v5jLm5gBzk6iDvDWIh92qSganh-Nq6ZuIBcFc1zp3FnXsqTtTMcFBXWEas350-ZKatEQqzXGdxZo3QqTCuPf-Cspp9rAcWIw"

def get_numeric_id_from_dupr_id(dupr_id):
    """
    Using the verified endpoint: https://api.dupr.gg/player/v1.0/search
    """
    # The URL from your F12 logs
    url = "https://api.dupr.gg/player/v1.0/search"
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Origin": "https://dashboard.dupr.com",
        "Referer": "https://dashboard.dupr.com/"
    }

    # Standard search payload
    payload = {
        "limit": 10,
        "offset": 0,
        "query": dupr_id,
        "exclude": [],
        "includeUnclaimedPlayers": True,
        "filter": {
            "lat": 33.7514966,
            "lng": -84.7477136,
            "rating": {"maxRating": None, "minRating": None},
            "locationText": ""
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            hits = data.get("result", {}).get("hits", [])
            
            for player in hits:
                # Compare the DUPR ID (e.g., NRRGJZ) to find the right person
                if player.get("duprId", "").upper() == dupr_id.upper():
                    numeric_id = player.get("id")
                    print(f"🎯 Found: {player.get('fullName')} | ID: {numeric_id}")
                    return str(numeric_id)
            
            print(f"⚠️ Search succeeded but ID '{dupr_id}' not found in results.")
            return None
        else:
            print(f"❌ API Error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Request Error: {e}")
        return None

def get_dupr_rating(dupr_id, match_type="DOUBLES"):
    url = f"https://api.dupr.gg/player/v1.0/{dupr_id}/rating-history"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Authorization": f"Bearer {TOKEN}",
        "Origin": "https://dashboard.dupr.com",
        "Referer": "https://dashboard.dupr.com/",
        "Content-Type": "application/json",
    }
    payload = {"limit": 10000, "offset": 0, "sortBy": "desc", "type": match_type}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "detail": response.text}
        data = response.json()
        res_obj = data.get("result", {})
        history = res_obj.get("ratingHistory", [])
        if not history:
            return {"error": "No data found"}
        return data
    except Exception as e:
        return {"error": str(e)}

def plot_rating_history(json_data, title="Rating History"):
    # --- SAFETY CHECK ---
    if not json_data or "error" in json_data:
        print(f"⚠️ Skipping {title}: No valid data available.")
        return

    try:
        history = json_data['result']['ratingHistory']
        df = pd.DataFrame(history)
        if df.empty:
            print(f"⚠️ Skipping {title}: Dataframe is empty.")
            return

        df['matchDate'] = pd.to_datetime(df['matchDate'])
        df = df.sort_values('matchDate')

        # Filter out 0 delta (phantom recalls)
        df['delta'] = df['rating'].diff()
        df = df[(df['delta'] != 0) | (df['delta'].isna())]

        plt.figure(figsize=(12, 6))
        plt.plot(df['matchDate'], df['rating'], marker='o', markersize=5, 
                 markerfacecolor='red', linestyle='--', linewidth=1, color='#000000')
        
        plt.title(title, fontsize=14)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"❌ Error plotting {title}: {e}")

def plot_daily_final_rating(file_path, title):
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # --- SAFETY CHECK ---
        if not data or "error" in data:
            print(f"⚠️ Skipping Daily {title}: No valid data in file.")
            return

        history = data.get('result', {}).get('ratingHistory', [])
        df = pd.DataFrame(history)
        if df.empty:
            print(f"⚠️ Skipping Daily {title}: No history entries found.")
            return

        df['matchDate'] = pd.to_datetime(df['matchDate'])
        df_daily = df.sort_values('matchDate').groupby('matchDate').tail(1).copy()
        
        # Filter out 0 delta
        df_daily['delta'] = df_daily['rating'].diff()
        df_daily = df_daily[(df_daily['delta'] != 0) | (df_daily['delta'].isna())]
        
        plt.figure(figsize=(12, 6))    
        plt.plot(df_daily['matchDate'], df_daily['rating'], marker='o', markersize=5, 
                 markerfacecolor='red', linestyle='--', linewidth=1, color='#000000')
        
        plt.title(f"Ending {title} History", fontsize=14)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
    except Exception as e:
        print(f"❌ Error plotting Daily {title}: {e}")

# --- Execution ---
doubles_data = get_dupr_rating(PLAYER_ID, "DOUBLES")
singles_data = get_dupr_rating(PLAYER_ID, "SINGLES")

# Plot only if data exists
plot_rating_history(doubles_data, title="Doubles Rating")
plot_rating_history(singles_data, title="Singles Rating")

# Save results for the final daily plots
with open("doubles_results.txt", "w") as f: json.dump(doubles_data, f)
with open("singles_results.txt", "w") as f: json.dump(singles_data, f)

plot_daily_final_rating("doubles_results.txt", "Doubles Rating")
plot_daily_final_rating("singles_results.txt", "Singles Rating")