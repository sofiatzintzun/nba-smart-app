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
    # Nota: Asegúrate de que la temporada coincida con la actual
    log = playergamelog.PlayerGameLog(player_id=player_id, season='2025-26')
    df_log = log.get_data_frames()[0]
    return df_log.head(5) 

# --- Lógica del Semáforo CORREGIDA ---
def apply_custom_style(df):
    # Creamos un DataFrame de strings vacíos con la misma forma que el original
    style_df = pd.DataFrame('', index=df.index, columns=df.columns)
    
    # Definimos el estilo verde
    css_verde = 'background-color: #28a745; color: white; font-weight: bold;'

    for col in df.columns:
        for idx in df.index:
            try:
                val = df.loc[idx, col]
                # Verificamos si es un número
                if isinstance(val, (int, float, pd.Number)):
                    # Regla para Robos y Bloqueos (>= 1)
                    if col in ['Robos', 'Bloqueos']:
                        if val >= 1:
                            style_df.loc[idx, col] = css_verde
                    # Regla para las demás columnas numéricas (>= 10)
                    elif val >= 10:
                        style_df.loc[idx, col] = css_verde
            except:
                continue
                
    return style_df

try:
    with st.spinner(f'Buscando estadísticas de {selected_player_name}...'):
        df_raw = get_player_last_5(player_id)

    if not df_raw.empty:
        # 1. Limpieza inicial
        df_last_5 = df_raw.copy().reset_index(drop=True)
        
        st.subheader(f"Desempeño de {selected_player_name} (Últimos 5 juegos)")
        
        # 2. Mapeo de columnas
        cols_map = {
            'GAME_DATE': 'Fecha',
            'MATCHUP': 'Partido',
            'WL': 'Rtdo',
            'MIN': 'Min',
            'PTS': 'PTS',
            'FGM': 'TCampo',
            'FGA': 'Int TCampo',
            'FG3M': '3P',
            'FG3A': 'Int 3P',
            'REB': 'REB',
            'AST': 'AST',
            'STL': 'Robos',
            'BLK': 'Bloqueos',
            'TOV': 'Pérdidas',
            'PF': 'Faltas'
        }
        
        # Seleccionamos y renombramos de forma segura
        df_display = df_last_5[list(cols_map.keys())].copy()
        df_display.columns = [cols_map[c] for c in df_display.columns]
        
        # 3. Aplicar estilo (aquí es donde ocurre la magia)
        # Importante: axis=None envía todo el DataFrame a la función
        styled_df = df_display.style.apply(apply_custom_style, axis=None)
        
        # 4. Mostrar tabla
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # --- Cálculo de Doble-Doble y Triple-Doble ---
        def count_doubles(row):
            stats = [row['PTS'], row['REB'], row['AST'], row['STL'], row['BLK']]
            return sum(1 for s in stats if s >= 10)

        df_last_5['doubles_count'] = df_last_5.apply(count_doubles, axis=1)
        double_doubles = sum(1 for x in df_last_5['doubles_count'] if x >= 2)
        triple_doubles = sum(1 for x in df_last_5['doubles_count'] if x >= 3)
        
        # Métricas Inferiores
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Avg PTS", f"{df_last_5['PTS'].mean():.1f}")
        col2.metric("Avg REB", f"{df_last_5['REB'].mean():.1f}")
        col3.metric("Avg AST", f"{df_last_5['AST'].mean():.1f}")
        col4.metric("Doble-Doble", f"{double_doubles}/5")
        col5.metric("Triple-Doble", f"{triple_doubles}/5")

    else:
        st.warning("No hay datos recientes para este jugador.")

except Exception as e:
    st.error(f"Error técnico: {e}")
