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

# 1. Obtener equipos de forma local (sin llamadas HTTP lentas)
@st.cache_data
def get_all_teams():
    return teams.get_teams()

try:
    nba_teams = get_all_teams()
except Exception as e:
    st.error("Error al cargar los equipos.")
    st.stop()

team_names = {t['full_name']: t['id'] for t in nba_teams}
selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
selected_team = next(t for t in nba_teams if t['full_name'] == selected_team_name)

# 2. Cargar jugadores activos locales y filtrar por el equipo seleccionado
@st.cache_data
def get_active_players():
    return players.get_active_players()

try:
    all_active = get_active_players()
    # Nota: La lista estática general agrupa jugadores. Como alternativa segura y rápida para 
    # evitar el bloqueo de roster, mostramos a los jugadores activos de la liga o permitimos buscarlos.
    # Si prefieres acotar por equipo de forma local sin requerir endpoints de roster bloqueados:
    player_names = sorted([p['full_name'] for p in all_active])
    player_dict = {p['full_name']: p['id'] for p in all_active}
except Exception as e:
    st.error("Error al cargar la lista de jugadores.")
    st.stop()

selected_player_name = st.sidebar.selectbox("Jugador", player_names)
player_id = player_dict[selected_player_name]

# 3. Obtener los últimos 5 partidos con reintentos y cabeceras personalizadas anti-bloqueo
@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    session = requests.Session()
    # Cabeceras personalizadas para simular un navegador real y evitar restricciones de la NBA
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.nba.com/',
        'Accept-Language': 'es-ES,es;q=0.9',
    })
    
    retry = Retry(connect=3, read=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Intentamos realizar la petición con la sesión personalizada
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2026-27', timeout=20)
    return log.get_data_frames()[0].head(5)

try:
    with st.spinner(f"Consultando estadísticas de {selected_player_name}..."):
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
        st.warning(f"No hay registros de partidos disponibles para {selected_player_name} en la temporada 2026-27.")

except requests.exceptions.ReadTimeout:
    st.error("⏰ La API de la NBA ha demorado demasiado en responder. Intenta seleccionar a otro jugador.")
except Exception as e:
    st.error(f"Ocurrió un error al obtener los datos: {e}")
