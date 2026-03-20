import streamlit as st
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

# 1. CONFIGURACIÓN DE PÁGINA (ESTÉTICA MÓVIL)
st.set_page_config(page_title="NBA L5 Tracker", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 0.5rem; padding-right: 0.5rem; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE APOYO (DEFINIDAS AL INICIO PARA EVITAR NAMEERROR) ---

def highlight_high_values(val):
    """Pinta de verde celdas con valor >= 10"""
    try:
        if isinstance(val, (int, float)) and val >= 10:
            return 'background-color: #28a745; color: white; font-weight: bold'
    except:
        pass
    return ''

@st.cache_data
def get_all_teams():
    return teams.get_teams()

@st.cache_data
def get_team_roster(team_id):
    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    return roster.get_data_frames()[0]

@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
    df_log = log.get_data_frames()[0]
    return df_log.head(5)

# --- CUERPO DE LA APP ---

st.title("🏀 NBA L5 Tracker")

try:
    nba_teams = get_all_teams()
    team_names = {t['full_name']: t['id'] for t in nba_teams}

    # Selectores en el cuerpo principal
    c1, c2 = st.columns(2)
    with c1:
        selected_team_name = st.selectbox("Equipo", sorted(team_names.keys()))
        team_id = team_names[selected_team_name]

    df_roster = get_team_roster(team_id)
    player_names = sorted(df_roster['PLAYER'].tolist())

    with c2:
        selected_player_name = st.selectbox("Jugador", player_names)

    player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

    with st.spinner('Actualizando estadísticas...'):
        df_raw = get_player_last_5(player_id)

    if not df_raw.empty:
        # Limpieza de datos
        df_last_5 = df_raw.copy().reset_index(drop=True)
        
        st.caption(f"Últimos 5 juegos: {selected_player_name}")
        
        # Mapeo de columnas corregido
        cols_map = {
            'GAME_DATE': 'Fecha',
            'MATCHUP': 'Vs',
            'WL': 'R',
            'PTS': 'P',
            'REB': 'REB',
            'AST': 'AST',
            'FGM': 'TC',
            'FGA': 'TCA',
            'FG3M': '3P',
            'FG3A': '3PA',
            'STL': 'RB',
            'BLK': 'BL',
            'TOV': 'PÉRD',
            'PF': 'F'
        }
        
        # Filtrar y renombrar
        df_display = df_last_5[list(cols_map.keys())].copy()
        df_display.columns = [cols_map[col] for col in df_display.columns]
        
        # Aplicar el estilo del semáforo
        # Nota: En versiones recientes de Pandas se usa .map(), en antiguas .applymap()
        try:
            styled_df = df_display.style.map(highlight_high_values)
        except AttributeError:
            styled_df = df_display.style.applymap(highlight_high_values)
        
        # Mostrar tabla
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Lógica de Dobles
        def count_doubles(row):
            stats = [row['PTS'], row['REB'], row['AST'], row['STL'], row['BLK']]
            return sum(1 for s in stats if s >= 10)
