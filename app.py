import streamlit as st
import pandas as pd
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

st.set_page_config(page_title="NBA Player Game Log", layout="wide")

st.title("🏀 Historial de los Últimos 5 Partidos")

# 1. Obtener todos los equipos para el selector
@st.cache_data
def get_all_teams():
    return teams.get_teams()

nba_teams = get_all_teams()
team_names = {t['full_name']: t['id'] for t in nba_teams}

# Selectores en la barra lateral
st.sidebar.header("Filtros de Búsqueda")
selected_team_name = st.sidebar.selectbox("1. Selecciona un Equipo", sorted(team_names.keys()))
team_id = team_names[selected_team_name]

# 2. Obtener jugadores del equipo seleccionado
@st.cache_data
def get_team_roster(team_id):
    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    return roster.get_data_frames()[0]

df_roster = get_team_roster(team_id)
player_names = sorted(df_roster['PLAYER'].tolist())
selected_player_name = st.sidebar.selectbox("2. Selecciona un Jugador", player_names)

# 3. Obtener el ID del jugador seleccionado
player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

# 4. Obtener el Log de partidos
@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
    df_log = log.get_data_frames()[0]
    return df_log.head(5) # Solo los últimos 5

try:
    with st.spinner(f'Buscando partidos de {selected_player_name}...'):
        df_last_5 = get_player_last_5(player_id)

    if not df_last_5.empty:
        st.subheader(f"Últimos 5 juegos de {selected_player_name}")
        
        # Seleccionamos columnas clave para el análisis
        cols = ['GAME_DATE', 'MATCHUP', 'WL', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT']
        df_display = df_last_5[cols].copy()
        
        # Mejorar formato
        df_display['FG_PCT'] = (df_display['FG_PCT'] * 100).map('{:.1f}%'.format)
        
        st.table(df_display) # Usamos table para que se vea fijo y claro
        
        # Un pequeño resumen visual abajo
        avg_pts = df_last_5['PTS'].mean()
        st.info(f"💡 **Promedio en estos 5 juegos:** {avg_pts:.1f} puntos.")
    else:
        st.warning("No se encontraron partidos para este jugador en la temporada actual.")

except Exception as e:
    st.error(f"Error al obtener los datos: {e}")
