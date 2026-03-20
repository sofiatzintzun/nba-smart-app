import streamlit as st
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

st.set_page_config(page_title="NBA Player Game Log", layout="wide")

st.title("🏀 Historial con Semáforo y Dobles")

@st.cache_data
def get_all_teams():
    return teams.get_teams()

nba_teams = get_all_teams()
team_names = {t['full_name']: t['id'] for t in nba_teams}

st.sidebar.header("Filtros de Búsqueda")
selected_team_name = st.sidebar.selectbox("1. Selecciona un Equipo", sorted(team_names.keys()))
team_id = team_names[selected_team_name]

@st.cache_data
def get_team_roster(team_id):
    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    return roster.get_data_frames()[0]

df_roster = get_team_roster(team_id)
player_names = sorted(df_roster['PLAYER'].tolist())
selected_player_name = st.sidebar.selectbox("2. Selecciona un Jugador", player_names)

player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
    df_log = log.get_data_frames()[0]
    return df_log.head(5) 

# --- Lógica del Semáforo PRO ---
def apply_custom_style(df):
    # Creamos una tabla de estilos vacía
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    
    # Color verde
    css_verde = 'background-color: #28a745; color: white; font-weight: bold'
    
    for col in df.columns:
        for idx in df.index:
            val = df.loc[idx, col]
            
            if isinstance(val, (int, float)):
                # REGLA A: Robos y Bloqueos >= 1
                if col in ['Robos', 'Bloqueos']:
                    if val >= 1:
                        style_df.loc[idx, col] = css_verde
                # REGLA B: Resto de columnas >= 10
                elif val >= 10:
                    style_df.loc[idx, col] = css_verde
                    
    return style_df

try:
    with st.spinner(f'Buscando estadísticas de {selected_player_name}...'):
        df_last_5 = get_player_last_5(player_id)

    if not df_last_5.empty:
        st.subheader(f"Desempeño de {selected_player_name} (Últimos 5 juegos)")
        
        cols_map = {
            'GAME_DATE': 'Fecha',
            'MATCHUP':
