import streamlit as st
import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats
from nba_api.stats.static import teams

st.set_page_config(page_title="NBA Smart Dashboard", layout="wide")

st.title("🏀 NBA Smart Dashboard v2.0")
st.sidebar.header("Configuración de Análisis")

# Función para obtener datos (con caché para no saturar la API)
@st.cache_data(ttl=3600)
def get_nba_data():
    stats = leaguedashplayerstats.LeagueDashPlayerStats(season='2025-26')
    df = stats.get_data_frames()[0]
    return df

try:
    df_players = get_nba_data()
    
    # Filtros rápidos
    team_list = sorted(df_players['TEAM_ABBREVIATION'].unique())
    selected_team = st.sidebar.multiselect("Filtrar por Equipo", team_list)

    if selected_team:
        df_filtered = df_players[df_players['TEAM_ABBREVIATION'].isin(selected_team)]
    else:
        df_filtered = df_players

    # Tabs para organizar la info
    tab1, tab2, tab3 = st.tabs(["📊 Estadísticas Proyectadas", "🎲 Análisis de Valor", "🚑 Reporte de Lesionados"])

    with tab1:
        st.subheader("Rendimiento por Jugador (Puntos, Rebotes, Asistencias)")
        # Mostramos métricas clave: PTS, REB, AST, STL, BLK
        st.dataframe(df_filtered[['PLAYER_NAME', 'TEAM_ABBREVIATION', 'PTS', 'REB', 'AST', 'STL', 'BLK']].sort_values(by='PTS', ascending=False))

    with tab2:
        st.info("Aquí calcularemos la desviación estándar y el Pace para encontrar ventajas.")

    with tab3:
        st.warning("No olvides cruzar estos datos con el reporte oficial de bajas antes de apostar.")

except Exception as e:
    st.error(f"Error al conectar con la API de la NBA: {e}")