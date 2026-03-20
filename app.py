import streamlit as st
import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats

st.set_page_config(page_title="NBA Last 5 Games", layout="wide")

st.title("🏀 Estadísticas: Últimos 5 Partidos")

# 1. Función para obtener los últimos 5 juegos de todos los jugadores
@st.cache_data(ttl=600)
def get_last_5_stats():
    # El parámetro 'last_n_games' es la clave aquí
    stats = leaguedashplayerstats.LeagueDashPlayerStats(
        season='2025-26',
        last_n_games=5,
        per_mode_detailed='PerGame'
    )
    return stats.get_data_frames()[0]

try:
    with st.spinner('Cargando datos de la NBA...'):
        df = get_last_5_stats()

    # 2. Selector de Equipo en la barra lateral
    team_list = sorted(df['TEAM_ABBREVIATION'].unique())
    selected_team = st.sidebar.selectbox("Selecciona un Equipo", team_list)

    # 3. Filtrado y Limpieza
    # Seleccionamos solo las columnas que nos interesan para que sea legible
    cols_to_show = ['PLAYER_NAME', 'GP', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'FG_PCT', 'FG3_PCT']
    df_team = df[df['TEAM_ABBREVIATION'] == selected_team][cols_to_show]

    # Mostramos los resultados
    st.subheader(f"Rendimiento de {selected_team} en sus últimos 5 encuentros")
    
    # Formateo de porcentajes para que se vean bien (ej. 0.45 -> 45%)
    df_team['FG_PCT'] = (df_team['FG_PCT'] * 100).map('{:.1f}%'.format)
    df_team['FG3_PCT'] = (df_team['FG3_PCT'] * 100).map('{:.1f}%'.format)

    st.dataframe(
        df_team.sort_values(by='PTS', ascending=False), 
        use_container_width=True,
        hide_index=True
    )

    st.caption("Nota: Los datos muestran el promedio por partido durante los últimos 5 juegos disputados por cada jugador.")

except Exception as e:
    st.error(f"Hubo un problema al obtener los datos: {e}")
