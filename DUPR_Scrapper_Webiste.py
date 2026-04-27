import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

# ─────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="DUPR Dashboard",
    page_icon="🏓",
    layout="wide",
)

# ─────────────────────────────────────────────
#  CUSTOM CSS  (dark, minimal, sport-forward)
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    h1, h2, h3, .metric-label {
        font-family: 'Space Mono', monospace;
    }
    .stApp {
        background-color: #0e0e0e;
        color: #f0f0f0;
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton > button {
        background: #00e5a0;
        color: #0e0e0e;
        font-family: 'Space Mono', monospace;
        font-weight: 700;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 2rem;
        letter-spacing: 0.04em;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #00ffb3;
        transform: translateY(-1px);
    }
    .stTextInput input, .stNumberInput input {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
        color: #f0f0f0;
        border-radius: 4px;
    }
    .stDataFrame {
        border: 1px solid #2a2a2a;
    }
    .stDivider {
        border-color: #2a2a2a;
    }
    /* Token expiry warning box */
    .token-box {
        background: #1a1a1a;
        border-left: 3px solid #00e5a0;
        padding: 0.75rem 1rem;
        border-radius: 0 4px 4px 0;
        font-family: 'Space Mono', monospace;
        font-size: 0.75rem;
        margin-bottom: 1rem;
    }
    .stAlert {
        background: #1a1a1a;
        border: 1px solid #2a2a2a;
    }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  TOKEN LOADING
#  Priority: st.secrets > sidebar manual entry
# ─────────────────────────────────────────────
def load_token():
    """Load token from Streamlit secrets if available."""
    try:
        return st.secrets["DUPR_TOKEN"]
    except Exception:
        return None

secret_token = load_token()

# ─────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏓 DUPR Dashboard")
    st.markdown("---")

    if secret_token:
        st.success("Token loaded from secrets ✓")
        token = secret_token
        # Decode JWT expiry without external lib
        try:
            import base64, json as _json
            payload_b64 = secret_token.split(".")[1]
            payload_b64 += "=" * (4 - len(payload_b64) % 4)
            payload = _json.loads(base64.b64decode(payload_b64))
            exp_ts = payload.get("exp")
            if exp_ts:
                exp_dt = datetime.utcfromtimestamp(exp_ts)
                days_left = (exp_dt - datetime.utcnow()).days
                color = "#00e5a0" if days_left > 7 else "#ff4444"
                st.markdown(
                    f'<div class="token-box">Token expires in '
                    f'<span style="color:{color};font-weight:700">{days_left} days</span><br>'
                    f'{exp_dt.strftime("%b %d, %Y")}</div>',
                    unsafe_allow_html=True
                )
        except Exception:
            pass
    else:
        st.warning("No token in secrets.")
        st.markdown(
            "Paste your JWT token below, or add it to "
            "`secrets.toml` as `DUPR_TOKEN = \"...\"`"
        )
        manual_token = st.text_area(
            "Bearer Token", height=120,
            placeholder="eyJhbGci...",
            help="Copy from browser DevTools → Network → any api.dupr.gg request → Authorization header"
        )
        token = manual_token.strip() if manual_token else ""

    st.markdown("---")
    player_id = st.text_input(
        "Player ID",
        placeholder="e.g. 5608790853",
        help="The numeric ID from your DUPR profile URL"
    )
    min_matches = st.number_input(
        "Min matches (partner/opponent table)",
        min_value=1, value=10, step=1
    )
    submit = st.button("Generate Dashboard", use_container_width=True)

    st.markdown("---")
    debug_mode = st.toggle("🔍 Debug mode", value=False, help="Shows raw API responses")

# ─────────────────────────────────────────────
#  HERO HEADER
# ─────────────────────────────────────────────
st.markdown("""
<h1 style="font-size:2.2rem;letter-spacing:-0.02em;margin-bottom:0.2rem">
    DUPR <span style="color:#00e5a0">Dashboard</span>
</h1>
<p style="color:#888;font-size:0.95rem;margin-top:0">
    Rating history · Partner analytics · Opponent breakdowns
</p>
""", unsafe_allow_html=True)
st.markdown("---")

# ─────────────────────────────────────────────
#  API HELPERS
# ─────────────────────────────────────────────
BASE_URL = "https://api.dupr.gg"

def make_headers(tok):
    return {
        "Authorization": f"Bearer {tok}",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Origin": "https://dashboard.dupr.com",
        "Referer": "https://dashboard.dupr.com/",
    }


def get_rating_history(numeric_id, match_type, tok, debug=False):
    url = f"{BASE_URL}/player/v1.0/{numeric_id}/rating-history"
    all_history = []
    full_name = None
    offset = 0
    limit = 100
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    # Go back 10 years to capture full history
    start_date = (datetime.utcnow().replace(year=datetime.utcnow().year - 3)).strftime("%Y-%m-%d")

    while True:
        payload = {
            "endDate": end_date,
            "limit": limit,
            "offset": offset,
            "startDate": start_date,
            "sortBy": "asc",
            "type": match_type,
        }
        try:
            r = requests.post(url, headers=make_headers(tok), json=payload, timeout=15)
            if debug and offset == 0:
                st.markdown(f"**`{match_type}` — status:** `{r.status_code}`")
                st.markdown(f"**Payload sent:** `{payload}`")
                try:
                    st.json(r.json())
                except Exception:
                    st.code(r.text[:2000])
            if r.status_code == 200:
                data = r.json()
                result = data.get("result", {})
                if not full_name:
                    full_name = result.get("fullName")
                history = result.get("ratingHistory", [])
                all_history.extend(history)
                # If we got fewer than limit, we've reached the end
                if len(history) < limit:
                    break
                offset += limit
            elif r.status_code == 401:
                st.error("❌ Token expired or invalid. Please update your DUPR token.")
                st.stop()
            else:
                break
        except Exception as e:
            st.error(f"Request failed: {e}")
            break

    if not all_history:
        return None
    # Return in same shape as before so the rest of the code works unchanged
    return {"result": {"fullName": full_name, "ratingHistory": all_history}}


def get_match_history(numeric_id, tok):
    url = f"{BASE_URL}/player/v1.0/{numeric_id}/history"
    partner_stats, opponent_stats = {}, {}
    offset, limit = 0, 25

    progress = st.progress(0, text="Fetching match history…")
    total_fetched = 0

    while True:
        payload = {
            "filters": {"eventFormat": None},
            "limit": limit,
            "offset": offset,
            "sort": {"order": "DESC", "parameter": "MATCH_DATE"},
        }
        try:
            r = requests.post(url, headers=make_headers(tok), json=payload, timeout=15)
            if r.status_code != 200:
                break
            data = r.json()
            result = data.get("result", {})
            matches = result.get("hits", [])
            has_more = result.get("hasMore", False)
            total_fetched += len(matches)

            progress.progress(
                min(total_fetched / max(total_fetched + 25, 1), 0.99),
                text=f"Fetched {total_fetched} matches…"
            )

            for m in matches:
                teams = m.get("teams", [])
                if len(teams) < 2:
                    continue

                user_team_idx, user_won = -1, False
                for i, team in enumerate(teams):
                    p1 = team.get("player1") or {}
                    p2 = team.get("player2") or {}
                    if (str(p1.get("id")) == str(numeric_id) or
                            str(p2.get("id")) == str(numeric_id)):
                        user_team_idx = i
                        user_won = team.get("winner") is True
                        break

                if user_team_idx == -1:
                    continue

                my_team = teams[user_team_idx]
                pre = my_team.get("preMatchRatingAndImpact") or {}

                if str((my_team.get("player1") or {}).get("id")) == str(numeric_id):
                    dupr_delta = pre.get("matchDoubleRatingImpactPlayer1")
                elif str((my_team.get("player2") or {}).get("id")) == str(numeric_id):
                    dupr_delta = pre.get("matchDoubleRatingImpactPlayer2")
                else:
                    dupr_delta = None

                # Partners
                for pk in ["player1", "player2"]:
                    p = my_team.get(pk) or {}
                    if p.get("id") and str(p["id"]) != str(numeric_id):
                        name = p.get("fullName", "Unknown")
                        s = partner_stats.setdefault(name, {"wins": 0, "losses": 0, "total": 0, "dupr_delta": 0.0})
                        s["total"] += 1
                        s["wins" if user_won else "losses"] += 1
                        if dupr_delta is not None:
                            s["dupr_delta"] += dupr_delta

                # Opponents
                other_team = teams[1 if user_team_idx == 0 else 0]
                for ok in ["player1", "player2"]:
                    o = other_team.get(ok) or {}
                    if o.get("fullName"):
                        name = o["fullName"]
                        s = opponent_stats.setdefault(name, {"wins": 0, "losses": 0, "total": 0, "dupr_delta": 0.0})
                        s["total"] += 1
                        s["wins" if user_won else "losses"] += 1
                        if dupr_delta is not None:
                            s["dupr_delta"] += dupr_delta

            if not has_more or not matches:
                break
            offset += limit

        except Exception as e:
            st.warning(f"Error at offset {offset}: {e}")
            break

    progress.empty()
    return partner_stats, opponent_stats


# ─────────────────────────────────────────────
#  CHART HELPER
# ─────────────────────────────────────────────
CHART_STYLE = {
    "bg": "#111111",
    "grid": "#222222",
    "line": "#00e5a0",
    "dot": "#ffffff",
    "text": "#888888",
    "title_color": "#f0f0f0",
}

def render_chart(json_data, title, is_daily=False):
    if not json_data or "result" not in json_data:
        st.caption(f"No data — {title}")
        return

    history = json_data["result"].get("ratingHistory", [])
    if not history:
        st.caption(f"No match history — {title}")
        return

    df = pd.DataFrame(history)
    df["matchDate"] = pd.to_datetime(df["matchDate"])
    df = df.sort_values("matchDate")

    if is_daily:
        df = df.groupby("matchDate").tail(1).copy()

    if len(df) > 1:
        df["delta"] = df["rating"].diff()
        df = df[(df["delta"] != 0) | df["delta"].isna()].copy()

    if df.empty:
        st.caption(f"No plottable data — {title}")
        return

    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor(CHART_STYLE["bg"])
    ax.set_facecolor(CHART_STYLE["bg"])

    ax.plot(
        df["matchDate"], df["rating"],
        color=CHART_STYLE["line"], linewidth=1.8,
        linestyle="-", zorder=3,
    )
    ax.scatter(
        df["matchDate"], df["rating"],
        color=CHART_STYLE["dot"], s=18, zorder=4, linewidths=0,
    )

    ax.set_title(title, color=CHART_STYLE["title_color"],
                 fontsize=11, pad=10, loc="left", fontweight="bold")
    ax.set_xlabel("", color=CHART_STYLE["text"])
    ax.set_ylabel("Rating", color=CHART_STYLE["text"], fontsize=9)
    ax.tick_params(colors=CHART_STYLE["text"], labelsize=8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=30, ha="right")

    for spine in ax.spines.values():
        spine.set_edgecolor("#222222")
    ax.grid(True, color=CHART_STYLE["grid"], linewidth=0.6, zorder=0)

    # Annotate last rating
    last_date = df["matchDate"].iloc[-1]
    last_rating = df["rating"].iloc[-1]
    ax.annotate(
        f" {last_rating:.3f}",
        xy=(last_date, last_rating),
        color=CHART_STYLE["line"],
        fontsize=9, fontweight="bold",
        va="center",
    )

    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────
#  STATS TABLE BUILDER
# ─────────────────────────────────────────────
def build_stats_df(stats_dict, min_matches):
    filtered = {k: v for k, v in stats_dict.items() if v["total"] >= min_matches}
    if not filtered:
        return pd.DataFrame()

    df = pd.DataFrame.from_dict(filtered, orient="index")
    df.index.name = "Player"
    df["Win %"] = (df["wins"] / df["total"] * 100).round(1)
    df["DUPR +/-"] = df["dupr_delta"].round(3)
    df["Per Match"] = (df["dupr_delta"] / df["total"]).round(4)
    df = df.rename(columns={"wins": "W", "losses": "L", "total": "GP"})
    df = df.sort_values("Per Match", ascending=False)
    return df[["W", "L", "GP", "Win %", "DUPR +/-", "Per Match"]]


def style_delta(val):
    color = "#00e5a0" if val > 0 else ("#ff4444" if val < 0 else "#888")
    return f"color: {color}"


# ─────────────────────────────────────────────
#  MAIN FLOW
# ─────────────────────────────────────────────
if not submit:
    st.markdown("""
<div style="text-align:center;padding:4rem 0;color:#444">
    <div style="font-size:3rem">🏓</div>
    <div style="font-family:'Space Mono',monospace;font-size:1rem;margin-top:1rem">
        Enter a Player ID in the sidebar and hit Generate Dashboard
    </div>
</div>
    """, unsafe_allow_html=True)
    st.stop()

# Validate inputs
if not token:
    st.error("No token available. Paste your JWT token in the sidebar or add it to secrets.toml.")
    st.stop()

if not player_id.strip():
    st.error("Please enter a Player ID in the sidebar.")
    st.stop()

numeric_id = player_id.strip()

# ── Fetch rating histories ──────────────────
with st.spinner("Fetching rating history…"):
    if debug_mode:
        st.markdown("### 🔍 Debug Output")
        st.markdown("#### Doubles API response")
    doubles_json = get_rating_history(numeric_id, "DOUBLES", token, debug=debug_mode)

    if debug_mode:
        st.markdown("#### Singles API response")
    singles_json = get_rating_history(numeric_id, "SINGLES", token, debug=debug_mode)

# Extract player name
full_name = None
if doubles_json:
    full_name = doubles_json.get("result", {}).get("fullName")
if not full_name and singles_json:
    full_name = singles_json.get("result", {}).get("fullName")
if not full_name:
    full_name = f"Player {numeric_id}"

# ── Player header ───────────────────────────
st.markdown(f"""
<h2 style="font-family:'Space Mono',monospace;font-size:1.6rem;margin-bottom:0.2rem">
    {full_name}
</h2>
<p style="color:#555;font-size:0.85rem;margin-top:0">ID: {numeric_id}</p>
""", unsafe_allow_html=True)

# ── Quick stat pills ─────────────────────────
def latest_rating(json_data):
    try:
        h = json_data["result"]["ratingHistory"]
        if h:
            return sorted(h, key=lambda x: x["matchDate"])[-1]["rating"]
    except Exception:
        pass
    return None

d_rating = latest_rating(doubles_json)
s_rating = latest_rating(singles_json)

col_a, col_b, col_c = st.columns(3)
with col_a:
    if d_rating:
        st.metric("Doubles Rating", f"{d_rating:.3f}")
    else:
        st.metric("Doubles Rating", "N/A")
with col_b:
    if s_rating:
        st.metric("Singles Rating", f"{s_rating:.3f}")
    else:
        st.metric("Singles Rating", "N/A")
with col_c:
    d_count = len((doubles_json or {}).get("result", {}).get("ratingHistory", []))
    s_count = len((singles_json or {}).get("result", {}).get("ratingHistory", []))
    st.metric("Total Matches", f"{d_count + s_count:,}")

st.markdown("---")

# ── Rating charts ────────────────────────────
st.markdown("### Rating History")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**Doubles**")
    render_chart(doubles_json, "All Doubles Matches")
    render_chart(doubles_json, "Doubles — Daily Final", is_daily=True)

with col2:
    st.markdown("**Singles**")
    render_chart(singles_json, "All Singles Matches")
    render_chart(singles_json, "Singles — Daily Final", is_daily=True)

st.markdown("---")

# ── Partner / Opponent analysis ──────────────
st.markdown("### Partner & Opponent Analytics")

p_stats, o_stats = get_match_history(numeric_id, token)

if not p_stats and not o_stats:
    st.info("No detailed match history available.")
else:
    col_p, col_o = st.columns(2)

    with col_p:
        st.markdown(f"**Top Partners** *(min {min_matches} matches)*")
        pdf = build_stats_df(p_stats, min_matches)
        if not pdf.empty:
            st.dataframe(
                pdf.style
                   .applymap(style_delta, subset=["DUPR +/-", "Per Match"])
                   .format({"Win %": "{:.1f}%", "DUPR +/-": "{:+.3f}", "Per Match": "{:+.4f}"}),
                use_container_width=True,
                height=400,
            )
        else:
            st.caption(f"No partners with {min_matches}+ matches.")

    with col_o:
        st.markdown(f"**Frequent Opponents** *(min {min_matches} matches)*")
        odf = build_stats_df(o_stats, min_matches)
        if not odf.empty:
            st.dataframe(
                odf.style
                   .applymap(style_delta, subset=["DUPR +/-", "Per Match"])
                   .format({"Win %": "{:.1f}%", "DUPR +/-": "{:+.3f}", "Per Match": "{:+.4f}"}),
                use_container_width=True,
                height=400,
            )
        else:
            st.caption(f"No opponents with {min_matches}+ matches.")

st.markdown("---")
st.markdown(
    "<p style='color:#333;font-size:0.75rem;text-align:center'>"
    "DUPR Dashboard · not affiliated with DUPR</p>",
    unsafe_allow_html=True
)
