import streamlit as st
import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import playergamelog, commonteamroster

# Configuración optimizada para móviles
st.set_page_config(page_title="NBA L5", layout="wide", initial_sidebar_state="collapsed")

# CSS inyectado para reducir márgenes y fuentes en móviles
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 0.5rem; padding-right: 0.5rem; }
    [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏀 NBA L5 Tracker")

@st.cache_data
def get_all_teams():
    return teams.get_teams()

nba_teams = get_all_teams()
team_names = {t['full_name']: t['id'] for t in nba_teams}

# Selectores en el cuerpo principal para mejor acceso en móvil
c1, c2 = st.columns(2)
with c1:
    selected_team_name = st.selectbox("Equipo", sorted(team_names.keys()))
    team_id = team_names[selected_team_name]

@st.cache_data
def get_team_roster(team_id):
    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    return roster.get_data_frames()[0]

df_roster = get_team_roster(team_id)
player_names = sorted(df_roster['PLAYER'].tolist())

with c2:
    selected_player_name = st.selectbox("Jugador", player_names)

player_id = df_roster[df_roster['PLAYER'] == selected_player_name]['PLAYER_ID'].values[0]

@st.cache_data(ttl=3600)
def get_player_last_5(player_id):
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
    df_log = log.get_data_frames()[0]
    return df_log.head(5) 

def highlight_high_values(val):
    if isinstance(val, (int, float)) and val >= 10:
        return 'background-color: #28a745; color: white; font-weight: bold'
    return ''

try:
    with st.spinner('Actualizando...'):
        df_last_5 = get_player_last_5(player_id)

    if not df_last_5.empty:
        # Título más compacto
        st.caption(f"Últimos 5 juegos: {selected_player_name}")
        
        # Mapeo con nombres ultra-cortos para ahorrar espacio en pantalla móvil
        cols_map = {
            'GAME_DATE': 'Fecha',
            'MATCHUP': 'Vs',
            'WL': 'R',
            'PTS': 'P',
            'REB': 'R',
            'AST': 'A',
            'FGM': 'TC',
            'FGA': 'TCA',
            'FG3M': '3P',
            'FG3A': '3PA',
            'STL': 'RB',
            'BLK': 'BL',
            'TOV': 'PÉRD',
            'PF': 'F'
        }
        
        df_display = df_last_5[list(cols_map.keys())].copy()
        df_display.rename(columns=cols_map, inplace=True)
        
        # st.dataframe con column_config para fijar anchos mínimos
        st.dataframe(
            df_display.style.applymap(highlight_high_values),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fecha": st.column_config.TextColumn("Fecha", width="small"),
                "Vs": st.column_config.TextColumn("Vs", width="small"),
                "R": st.column_config.TextColumn("R", width="extrasmall"),
            }
        )
        
        # Lógica de Dobles
        def count_doubles(row):
            stats = [row['PTS'], row['REB'], row['AST'], row['STL'], row['BLK']]
            return sum(1 for s in stats if s >= 10)

        df_last_5['doubles_count'] = df_last_5.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_last_5['doubles_count'] if x >= 2)
        td = sum(1 for x in df_last_5['doubles_count'] if x >= 3)
        
        # Métricas en 2 filas para que no se amontonen en el móvil
        m1, m2, m3 = st.columns(3)
        m1.metric("AVG PTS", f"{df_last_5['PTS'].mean():.1f}")
        m2.metric("AVG REB", f"{df_last_5['REB'].mean():.1f}")
        m3.metric("AVG AST", f"{df_last_5['AST'].mean():.1f}")
        
        m4, m5 = st.columns(2)
        m4.metric("Doble-Doble", f"{dd}/5")
        m5.metric("Triple-Doble", f"{td}/5")

    else:
        st.warning("No hay datos.")

except Exception as e:
    st.error(f"Error: {e}")
