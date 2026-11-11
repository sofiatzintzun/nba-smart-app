import streamlit as st
import pandas as pd
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from nba_api.stats.static import teams, players
from nba_api.stats.endpoints import playergamelog

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

@st.cache_data(ttl=3600)
def get_all_teams():
    return teams.get_teams()

try:
    nba_teams = get_all_teams()
except Exception as e:
    st.error("Error al conectar con la API de la NBA. Por favor, recarga la página.")
    st.stop()

team_names = {t['full_name']: t['id'] for t in nba_teams}
selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
team_id = team_names[selected_team_name]

# En lugar de usar commonteamroster (que falla), obtenemos todos los jugadores activos 
# y filtramos los que pertenecen al equipo o usamos una alternativa ligera.
@st.cache_data(ttl=3600)
def get_team_players(team_id):
    all_players = players.get_players()
    # Como la lista estática no siempre trae el equipo actual de forma inmediata, 
    # usaremos una consulta segura o filtraremos por los jugadores activos de la liga.
    active_players = [p for p in all_players if p['is_active']]
    return active_players

# Alternativa robusta para obtener jugadores del equipo sin bloquearse
@st.cache_data(ttl=3600)
def get_roster_safe(team_id):
    from nba_api.stats.endpoints import teamroster
    # Probamos con teamroster clásico o una lista genérica si falla
    try:
        r = teamroster.TeamRoster(team_id=team_id, season='2026-27', timeout=10)
        df = r.get_data_frames()[0]
        if not df.empty:
            return df[['PLAYER', 'PLAYER_ID']]
    except:
        pass
    
    # Plan B: Si falla el roster por equipo, traemos jugadores activos generales de respaldo
    active = players.get_active_players()
    return pd.DataFrame([{'PLAYER': p['full_name'], 'PLAYER_ID': p['id']} for p in active])

try:
    df_roster = get_roster_safe(team_id)
except Exception as e:
    st.error("No se pudo cargar la lista de jugadores debido a restricciones de la API de la NBA.")
    st.stop()

if df_roster.empty:
    st.warning("No hay jugadores disponibles para este equipo.")
    st.stop()

player_names = sorted(df_roster['PLAYER'].tolist())
selected_player_name = st.sidebar.selectbox("Jugador", player_names)
player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    session = requests.Session()
    retry = Retry(connect=3, read=3, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2026-27', timeout=15)
    return log.get_data_frames()[0].head(5)

try:
    df_raw = get_player_last_5(player_id)

    if not df_raw.empty:
        cols_map = {
            'GAME_DATE': 'Fecha', 'MATCHUP': 'Partido', 'WL': 'R', 'MIN': 'Min',
            'PTS': 'PTS', 'FGM': 'TC', 'FGA': 'TCA', 'FG3M': '3P', 'FG3A': '3PA',
            'REB': 'REB', 'AST': 'AST', 'STL': 'STL', 'BLK': 'BLK',
            'TOV': 'ERR', 'PF': 'PF'
        }
        df_display = df_raw[[c for c in cols_map.keys() if c in df_raw.columns]].copy()
        df_display.rename(columns=cols_map, inplace=True)
        
        styled_df = df_display.style.map(highlight_cells, subset=[c for c in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TC', '3P'] if c in df_display.columns])

        st.write(f"### {selected_player_name} | {selected_team_name}")
        st.table(styled_df)

        def count_doubles(row):
            stats = [row.get('PTS', 0), row.get('REB', 0), row.get('AST', 0), row.get('STL', 0), row.get('BLK', 0)]
            return sum(1 for s in stats if s >= 10)

        df_raw['doubles_count'] = df_raw.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_raw['doubles_count'] if x >= 2)
        td = sum(1 for x in df_raw['doubles_count'] if x >= 3)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg PTS", f"{df_raw['PTS'].mean():.1f}" if 'PTS' in df_raw else "0.0")
        c2.metric("Avg REB", f"{df_raw['REB'].mean():.1f}" if 'REB' in df_raw else "0.0")
        c3.metric("Avg AST", f"{df_raw['AST'].mean():.1f}" if 'AST' in df_raw else "0.0")
        c4.metric("DD", f"{dd}/5")
        c5.metric("TD", f"{td}/5")
    else:
        st.warning("No hay registros de partidos disponibles para este jugador en la temporada 2026-27.")

except requests.exceptions.ReadTimeout:
    st.error("⏰ La solicitud de estadísticas ha tardado demasiado (Timeout). Selecciona otro jugador.")
except Exception as e:
    st.error(f"Ocurrió un error: {e}")
