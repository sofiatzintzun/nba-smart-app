import streamlit as st
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

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
    st.error("Error al conectar con la API de la NBA para obtener los equipos. Por favor, recarga la página.")
    st.stop()

team_names = {t['full_name']: t['id'] for t in nba_teams}

selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
team_id = team_names[selected_team_name]

@st.cache_data(ttl=3600)
def get_team_roster(team_id):
    roster = commonteamroster.CommonTeamRoster(team_id=team_id, timeout=15)
    return roster.get_data_frames()[0]

try:
    df_roster = get_team_roster(team_id)
except Exception as e:
    st.error(f"No se pudo cargar el plantel del equipo seleccionado debido a un retraso en la red (Timeout). Intenta de nuevo en unos segundos.")
    st.stop()

player_names = sorted(df_roster['PLAYER'].tolist())
selected_player_name = st.sidebar.selectbox("Jugador", player_names)
player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    # Configuración de sesión con reintentos para mitigar errores de ReadTimeout
    session = requests.Session()
    retry = Retry(connect=3, read=3, backoff_factor=1)
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26', timeout=15)
    return log.get_data_frames()[0].head(5)

try:
    df_raw = get_player_last_5(player_id)

    if not df_raw.empty:
        # 1. Limpiar y Renombrar
        cols_map = {
            'GAME_DATE': 'Fecha', 'MATCHUP': 'Partido', 'WL': 'R', 'MIN': 'Min',
            'PTS': 'PTS', 'FGM': 'TC', 'FGA': 'TCA', 'FG3M': '3P', 'FG3A': '3PA',
            'REB': 'REB', 'AST': 'AST', 'STL': 'STL', 'BLK': 'BLK',
            'TOV': 'ERR', 'PF': 'PF'
        }
        df_display = df_raw[list(cols_map.keys())].copy()
        df_display.rename(columns=cols_map, inplace=True)
        
        # 2. Aplicar estilo celda por celda (Usando .map en lugar de .applymap)
        styled_df = df_display.style.map(highlight_cells, subset=['PTS', 'REB', 'AST', 'STL', 'BLK', 'TC', '3P'])

        # 3. Renderizar con st.table
        st.write(f"### {selected_player_name} | {selected_team_name}")
        st.table(styled_df)

        # 4. Métricas
        def count_doubles(row):
            stats = [row['PTS'], row['REB'], row['AST'], row['STL'], row['BLK']]
            return sum(1 for s in stats if s >= 10)

        df_raw['doubles_count'] = df_raw.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_raw['doubles_count'] if x >= 2)
        td = sum(1 for x in df_raw['doubles_count'] if x >= 3)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg PTS", f"{df_raw['PTS'].mean():.1f}")
        c2.metric("Avg REB", f"{df_raw['REB'].mean():.1f}")
        c3.metric("Avg AST", f"{df_raw['AST'].mean():.1f}")
        c4.metric("DD", f"{dd}/5")
        c5.metric("TD", f"{td}/5")
    else:
        st.warning("No hay registros de partidos disponibles para este jugador en la temporada seleccionada.")

except requests.exceptions.ReadTimeout:
    st.error("⏰ La solicitud a la API de la NBA ha tardado demasiado (Timeout). Por favor, cambia de jugador o recarga la página para reintentarlo.")
except Exception as e:
    st.error(f"Ocurrió un error inesperado: {e}")
