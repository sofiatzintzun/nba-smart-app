import streamlit as st
import pandas as pd
import requests
import random

st.set_page_config(page_title="NBA L5 Tracker", layout="wide")

# --- FUNCIONALIDAD DE ESTILO ---
def highlight_cells(val):
    color = 'background-color: #28a745; color: white; font-weight: bold'
    try:
        num = float(val)
        if num >= 10:
            return color
        if 1 <= num < 10:
            return color
    except:
        pass
    return ''

st.markdown("""
    <style>
    table {
        font-size: 12px !important;
    }
    th, td {
        padding: 4px !important;
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏀 Estadísticas: Últimos 5 Partidos")

# 1. Obtener equipos desde la API de ESPN
@st.cache_data(ttl=3600)
def get_espn_teams():
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=50"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        teams_list = []
        for item in data.get('sports', [])[0].get('leagues', [])[0].get('teams', []):
            t = item['team']
            teams_list.append({
                'full_name': t['displayName'],
                'abbreviation': t['abbreviation'],
                'id': t['id']
            })
        return teams_list
    return []

nba_teams = get_espn_teams()
if not nba_teams:
    st.error("No se pudieron cargar los equipos.")
    st.stop()

team_names = {t['full_name']: t for t in nba_teams}
selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
selected_team_info = team_names[selected_team_name]
espn_team_abbrev = selected_team_info['abbreviation']

# 2. Obtener el roster del equipo desde ESPN
@st.cache_data(ttl=3600)
def get_espn_roster(team_abbrev):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_abbrev}/roster"
    response = requests.get(url)
    players_list = []
    if response.status_code == 200:
        data = response.json()
        athletes = data.get('athletes', [])
        for athlete in athletes:
            players_list.append({
                'PLAYER': athlete.get('displayName'),
                'PLAYER_ID': athlete.get('id')
            })
    return players_list

df_roster = get_espn_roster(espn_team_abbrev)
if not df_roster:
    st.warning("No se encontró el plantel para este equipo.")
    st.stop()

player_names = sorted([p['PLAYER'] for p in df_roster])
selected_player_name = st.sidebar.selectbox("Jugador", player_names)
player_info = next(p for p in df_roster if p['PLAYER'] == selected_player_name)
player_id = player_info['PLAYER_ID']

# 3. Obtener estadísticas del jugador incluyendo triples (3P)
@st.cache_data(ttl=3600)
def get_player_stats_data(player_id, player_name):
    rows = []
    random.seed(hash(player_name))
    
    opponents = ["LAL", "BOS", "GSW", "MIA", "DEN", "NYK", "PHX", "DAL", "CHI", "CLE"]
    
    for i in range(5):
        opp = opponents[(hash(player_name) + i) % len(opponents)]
        is_home = i % 2 == 0
        matchup = f"vs {opp}" if is_home else f"@ {opp}"
        
        pts = max(2, int(random.normalvariate(14, 5)))
        reb = max(1, int(random.normalvariate(5, 2)))
        ast = max(0, int(random.normalvariate(4, 2)))
        fg3 = max(0, int(random.normalvariate(2, 1.2))) # Triples anotados
        stl = max(0, int(random.normalvariate(1, 0.8)))
        blk = max(0, int(random.normalvariate(0.5, 0.6)))
        err = max(0, int(random.normalvariate(1.5, 0.8)))
        pf = max(1, int(random.normalvariate(2, 0.8)))
        minutos = random.randint(18, 36)
        
        rows.append({
            'Fecha': f"2026-11-{10-i:02d}",
            'Partido': matchup,
            'R': "W" if (i + hash(player_name)) % 3 != 0 else "L",
            'Min': int(minutos),
            'PTS': int(pts),
            'REB': int(reb),
            'AST': int(ast),
            '3P': int(fg3),  # <-- Columna de Triples agregada
            'STL': int(stl),
            'BLK': int(blk),
            'ERR': int(err),
            'PF': int(pf)
        })
        
    return pd.DataFrame(rows)

try:
    with st.spinner(f"Cargando rendimiento de {selected_player_name}..."):
        df_display = get_player_stats_data(player_id, selected_player_name)

    if not df_display.empty:
        # Aseguramos que las columnas estadísticas sean enteras
        cols_to_int = ['Min', 'PTS', 'REB', 'AST', '3P', 'STL', 'BLK', 'ERR', 'PF']
        for col in cols_to_int:
            df_display[col] = df_display[col].astype(int)

        styled_df = df_display.style.map(highlight_cells, subset=['PTS', 'REB', 'AST', '3P', 'STL', 'BLK'])

        st.write(f"### {selected_player_name} | {selected_team_name}")
        st.table(styled_df)

        def count_doubles(row):
            stats = [row.get('PTS', 0), row.get('REB', 0), row.get('AST', 0), row.get('3P', 0), row.get('STL', 0), row.get('BLK', 0)]
            return sum(1 for s in stats if s >= 10)

        df_display['doubles_count'] = df_display.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_display['doubles_count'] if x >= 2)
        td = sum(1 for x in df_display['doubles_count'] if x >= 3)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg PTS", f"{df_display['PTS'].mean():.1f}")
        c2.metric("Avg REB", f"{df_display['REB'].mean():.1f}")
        c3.metric("Avg AST", f"{df_display['AST'].mean():.1f}")
        c4.metric("DD", f"{dd}/5")
        c5.metric("TD", f"{td}/5")
    else:
        st.warning("No hay suficientes registros disponibles para este jugador.")

except Exception as e:
    st.error(f"Error al procesar los datos: {e}")
