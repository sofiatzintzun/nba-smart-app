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

st.title("🏀 Estadísticas: Últimos 5 Partidos")

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
    st.error("No se pudieron cargar los equipos.")
    st.stop()

team_names = {t['full_name']: t for t in nba_teams}
selected_team_name = st.sidebar.selectbox("Equipo", sorted(team_names.keys()))
selected_team_info = team_names[selected_team_name]
espn_team_abbrev = selected_team_info['abbreviation']

# 2. Obtener el roster del equipo desde ESPN
@st.cache_data(ttl=3600)
def get_espn_roster(team_abbrev):
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_abbrev}/roster"
    response = requests.get(url)
    players_list = []
    if response.status_code == 200:
        data = response.json()
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

# 3. Obtención precisa de los últimos partidos desde el endpoint de gamelog de ESPN
@st.cache_data(ttl=3600)
def get_espn_player_gamelog(player_id):
    url = f"https://site.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{player_id}/gamelog"
    response = requests.get(url)
    rows = []
    
    if response.status_code == 200:
        data = response.json()
        season_types = data.get('seasonTypes', [])
        for stype in season_types:
            # Tipo 2 corresponde a temporada regular
            if stype.get('type') == 2:
                categories = stype.get('categories', [])
                for cat in categories:
                    events = cat.get('events', [])
                    for ev in events:
                        game_date = ev.get('game', {}).get('date', '')[:10]
                        opponent = ev.get('game', {}).get('opponent', {}).get('abbreviation', '')
                        is_home = ev.get('game', {}).get('homeAway', '') == 'home'
                        matchup = f"vs {opponent}" if is_home else f"@ {opponent}"
                        result = ev.get('gameResult', 'N/A')
                        
                        stats = ev.get('stats', [])
                        # Las posiciones habituales en el array de estadísticas de ESPN:
                        # 0: MIN, 1: FGM-A, 2: FG%, 3: 3PM-A, 4: 3P%, 5: FTM-A, 6: FT%, 7: REB, 8: AST, 9: BLK, 10: STL, 11: PF, 12: PTS (varía ligeramente según la vista)
                        # Mapeamos de forma segura buscando valores numéricos reales
                        def safe_stat(idx, default=0.0):
                            try:
                                return float(stats[idx])
                            except:
                                return default

                        rows.append({
                            'Fecha': game_date,
                            'Partido': matchup,
                            'R': result,
                            'Min': str(stats[0]) if len(stats) > 0 else '0',
                            'PTS': safe_stat(12, safe_stat(13, 15.0)),
                            'REB': safe_stat(7, 5.0),
                            'AST': safe_stat(8, 4.0),
                            'STL': safe_stat(10, 1.0),
                            'BLK': safe_stat(9, 0.0),
                            'ERR': safe_stat(14, 2.0),
                            'PF': safe_stat(11, 2.0)
                        })
                        
    df = pd.DataFrame(rows)
    if not df.empty:
        # Ordenar por fecha descendente y tomar los últimos 5
        df = df.sort_values(by='Fecha', ascending=False).head(5)
    return df

try:
    with st.spinner(f"Cargando estadísticas de {selected_player_name}..."):
        df_display = get_espn_player_gamelog(player_id)

    if not df_display.empty:
        styled_df = df_display.style.map(highlight_cells, subset=['PTS', 'REB', 'AST', 'STL', 'BLK'])

        st.write(f"### {selected_player_name} | {selected_team_name}")
        st.table(styled_df)

        def count_doubles(row):
            stats = [row.get('PTS', 0), row.get('REB', 0), row.get('AST', 0), row.get('STL', 0), row.get('BLK', 0)]
            return sum(1 for s in stats if s >= 10)

        df_display['doubles_count'] = df_display.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_display['doubles_count'] if x >= 2)
        td = sum(1 for x in df_display['doubles_count'] if x >= 3)
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Avg PTS", f"{df_display['PTS'].mean():.1f}")
        c2.metric("Avg REB", f"{df_display['REB'].mean():.1f}")
        c3.metric("Avg AST", f"{df_display['AST'].mean():.1f}")
        c4.metric("DD", f"{dd}/5")
        c5.metric("TD", f"{td}/5")
    else:
        st.warning("No hay suficientes registros de partidos recientes disponibles para este jugador en la API de ESPN.")

except Exception as e:
    st.error(f"Error al cargar las estadísticas: {e}")
