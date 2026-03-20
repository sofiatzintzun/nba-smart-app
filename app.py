import streamlit as st
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

st.set_page_config(page_title="NBA L5 Tracker", layout="wide")

# --- FUNCIONALIDAD DE ESTILO (Súper Simple) ---
def highlight_cells(val):
    # Definimos el color verde
    color = 'background-color: #28a745; color: white; font-weight: bold'
    
    # Intentamos convertir a número por si acaso
    try:
        num = float(val)
        # REGLA: Si es 1, 2, 3, 4, 5, 6, 7, 8, 9 (típico de robos/bloqueos) 
        # o si es >= 10 (puntos, rebotes, etc.)
        if num >= 10:
            return color
        # Esta regla cubre Robos y Bloqueos (>=1) sin necesidad de saber el nombre de la columna
        if num >= 1 and num < 10:
            # Aquí hay un truco: como queremos que solo Robos/Bloqueos se pinten con 1,
            # pero no queremos que la Fecha (ej. 2024) se pinte, 
            # el reset_index y el filtrado de columnas abajo ayudarán.
            return color
    except:
        pass
    return ''

st.markdown("""
    <style>
    /* Ajusta el tamaño de fuente y espacio en las tablas */
    table {
        font-size: 12px !important;
    }
    th, td {
        padding: 4px !important;
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏀 NBA Tracker - Semáforo Total")

# ... (Todo tu código de obtención de equipos y jugadores se mantiene igual) ...
@st.cache_data
def get_all_teams():
    return teams.get_teams()

nba_teams = get_all_teams()
team_names = {t['full_name']: t['id'] for t in nba_teams}

selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
team_id = team_names[selected_team_name]

@st.cache_data
def get_team_roster(team_id):
    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    return roster.get_data_frames()[0]

df_roster = get_team_roster(team_id)
player_names = sorted(df_roster['PLAYER'].tolist())
selected_player_name = st.sidebar.selectbox("Jugador", player_names)
player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
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
        
        # 2. Aplicar estilo celda por celda (A PRUEBA DE TODO)
        # Usamos .style.applymap() que es el método más directo
        styled_df = df_display.style.applymap(highlight_cells, subset=['PTS', 'REB', 'AST', 'STL', 'BLK', 'TC', '3P'])

        # 3. Renderizar con st.table (A veces st.dataframe da problemas de CSS en móvil)
        # Probemos con st.table para asegurar que el HTML se renderice con colores
        st.write(f"### {selected_player_name}")
        st.table(styled_df)

        # ... (Tus métricas de abajo se mantienen igual) ...
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

except Exception as e:
    st.error(f"Error: {e}")
