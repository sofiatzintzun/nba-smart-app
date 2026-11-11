import streamlit as st
import pandas as pd
import requests

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

st.title("🏀 Estadísticas: Últimos 5 Partidos (vía ESPN)")

# 1. Obtener equipos desde la API de ESPN
@st.cache_data(ttl=3600)
def get_espn_teams():
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=50"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        teams_list = []
        for item in data.get('sports', [])[0].get('leagues', [])[0].get('teams', []):
            t = item['team']
            teams_list.append({
                'full_name': t['displayName'],
                'abbreviation': t['abbreviation'],
                'id': t['id']
            })
        return teams_list
    return []

nba_teams = get_espn_teams()
if not nba_teams:
    st.error("No se pudieron cargar los equipos desde ESPN.")
    st.stop()

team_names = {t['full_name']: t for t in nba_teams}
selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
selected_team_info = team_names[selected_team_name]
espn_team_abbrev = selected_team_info['abbreviation']

# 2. Obtener el roster del equipo seleccionado desde ESPN
@st.cache_data(ttl=3600)
def get_espn_roster(team_abbrev):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_abbrev}/roster"
    response = requests.get(url)
    players_list = []
    if response.status_code == 200:
        data = response.json()
        # ESPN agrupa por categorías (atletas)
        athletes = data.get('athletes', [])
        for athlete in athletes:
            players_list.append({
                'PLAYER': athlete.get('displayName'),
                'PLAYER_ID': athlete.get('id')
            })
    return players_list

df_roster = get_espn_roster(espn_team_abbrev)
if not df_roster:
    st.warning("No se encontró el plantel para este equipo.")
    st.stop()

player_names = sorted([p['PLAYER'] for p in df_roster])
selected_player_name = st.sidebar.selectbox("Jugador", player_names)
player_id = next(p['PLAYER_ID'] for p in df_roster if p['PLAYER'] == selected_player_name)

# 3. Obtener los últimos partidos del jugador desde el endpoint de estadísticas de ESPN
@st.cache_data(ttl=3600)
def get_espn_player_logs(player_id):
    url = f"https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{player_id}/gamelog"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Buscamos las estadísticas de la temporada regular actual
        events = []
        season_types = data.get('seasonTypes', [])
        for stype in season_types:
            # Generalmente la temporada regular es el tipo 2
            if stype.get('type') == 2:
                categories = stype.get('categories', [])
                for cat in categories:
                    if 'events' in cat:
                        events = cat['events']
                        break
        
        rows = []
        # Recorremos los eventos en orden inverso (más recientes primero) si es necesario, o tomamos los últimos
        for ev in reversed(events):
            stats = ev.get('stats', [])
            # Mapeo aproximado de estadísticas comunes de ESPN en listas o diccionario según la estructura
            # Como ESPN varía en formato de listas de estadísticas por partido, extraemos por nombre de etiqueta si está disponible
            game_date = ev.get('game', {}).get('date', '')[:10]
            opponent = ev.get('game', {}).get('opponent', {}).get('abbreviation', '')
            is_home = ev.get('game', {}).get('homeAway', '') == 'home'
            matchup = f"vs. {opponent}" if is_home else f"@ {opponent}"
            result = ev.get('gameResult', 'N/A')
            
            # Extraer estadísticas clave por su posición o etiqueta si vienen estructuradas
            # Estadísticas típicas de ESPN en gamelog: Min, PTS, REB, AST, STL, BLK, TO, PF, FG, 3PT
            stat_dict = {
                'Fecha': game_date,
                'Partido': matchup,
                'R': result,
                'Min': stats[0] if len(stats) > 0 else 0,
                'PTS': float(stats[12]) if len(stats) > 12 else 0.0, # Posición típica de puntos en tablas ESPN
                'REB': float(stats[3]) if len(stats) > 3 else 0.0,
                'AST': float(stats[4]) if len(stats) > 4 else 0.0,
                'STL': float(stats[5]) if len(stats) > 5 else 0.0,
                'BLK': float(stats[6]) if len(stats) > 6 else 0.0,
                'ERR': float(stats[8]) if len(stats) > 8 else 0.0,
                'PF': float(stats[9]) if len(stats) > 9 else 0.0,
                'TC': 0, '3P': 0
            }
            rows.append(stat_dict)
        
        df = pd.DataFrame(rows)
        return df.tail(5) # Últimos 5 partidos
    return pd.DataFrame()

try:
    with st.spinner(f"Cargando datos de {selected_player_name}..."):
        df_display = get_espn_player_logs(player_id)

    if not df_display.empty:
        # Asegurar columnas numéricas para las métricas y estilos
        num_cols = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'ERR', 'PF']
        for col in num_cols:
            if col in df_display.columns:
                df_display[col] = pd.to_numeric(df_display[col], errors='fillna').fillna(0)

        styled_df = df_display.style.map(highlight_cells, subset=['PTS', 'REB', 'AST', 'STL', 'BLK'])

        st.write(f"### {selected_player_name} | {selected_team_name}")
        st.table(styled_df)

        # Métricas de los últimos partidos cargados
        def count_doubles(row):
            stats = [row.get('PTS', 0), row.get('REB', 0), row.get('AST', 0), row.get('STL', 0), row.get('BLK', 0)]
            return sum(1 for s in stats if s >= 10)

        df_display['doubles_count'] = df_display.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_display['doubles_count'] if x >= 2)
        td = sum(1 for x in df_display['doubles_count'] if x >= 3)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg PTS", f"{df_display['PTS'].mean():.1f}" if 'PTS' in df_display else "0.0")
        c2.metric("Avg REB", f"{df_display['REB'].mean():.1f}" if 'REB' in df_display else "0.0")
        c3.metric("Avg AST", f"{df_display['AST'].mean():.1f}" if 'AST' in df_display else "0.0")
        c4.metric("DD", f"{dd}/5")
        c5.metric("TD", f"{td}/5")
    else:
        st.warning("No hay suficientes registros de partidos recientes disponibles para este jugador en la API de ESPN.")

except Exception as e:
    st.error(f"Ocurrió un error al procesar los datos de ESPN: {e}")
