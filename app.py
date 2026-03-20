import streamlit as st
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

st.set_page_config(page_title="NBA Player Game Log", layout="wide")

st.title("🏀 Historial Detallado: Últimos 5 Partidos")

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

# 4. Obtener el Log de partidos (Temporada actual)
@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    # Traemos el log de la temporada 2025-26
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
    df_log = log.get_data_frames()[0]
    return df_log.head(5) 

try:
    with st.spinner(f'Buscando estadísticas de {selected_player_name}...'):
        df_last_5 = get_player_last_5(player_id)

    if not df_last_5.empty:
        st.subheader(f"Desempeño de {selected_player_name} (Últimos 5 juegos)")
        
        # Mapeo de columnas solicitadas:
        # FGM: Tiros de campo anotados | FGA: Intentos de tiros de campo
        # FG3M: Triples anotados | FG3A: Intentos de triples
        # TOV: Pérdidas | PF: Faltas personales
        cols_map = {
            'GAME_DATE': 'Fecha',
            'MATCHUP': 'Partido',
            'WL': 'Rtdo',
            'MIN': 'Min',
            'PTS': 'PTS',
            'FGM': 'TC Conv',
            'FGA': 'TC Int',
            'FG3M': '3P Conv',
            'FG3A': '3P Int',
            'REB': 'REB',
            'AST': 'AST',
            'TOV': 'Pérdidas',
            'PF': 'Faltas'
        }
        
        # Filtramos y renombramos para que la tabla sea clara
        df_display = df_last_5[list(cols_map.keys())].copy()
        df_display.rename(columns=cols_map, inplace=True)
        
        # Mostramos la tabla principal
        st.table(df_display)
        
        # Resumen rápido de eficiencia
        avg_3p = df_last_5['FG3M'].mean()
        avg_tov = df_last_5['TOV'].mean()
        
        col1, col2 = st.columns(2)
        col1.metric("Promedio Triples (L5)", f"{avg_3p:.1f}")
        col2.metric("Promedio Pérdidas (L5)", f"{avg_tov:.1f}")

    else:
        st.warning("No se encontraron registros recientes para este jugador.")

except Exception as e:
    st.error(f"Error al conectar con la base de datos de la NBA: {e}")
