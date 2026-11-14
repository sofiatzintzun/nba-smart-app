
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, time
import locale
from streamlit_gsheets import GSheetsConnection

# Intentamos configurar el español para las fechas
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except:
    pass

st.set_page_config(page_title="NBA L5 Parlay Master - Google Sheets", layout="wide")

# --- FUNCIONALIDAD DE ESTILO ---
def highlight_cells(val):
    color = 'background-color: #28a745; color: white; font-weight: bold'
    try:
        num = float(val)
        if num >= 1:
            return color
    except:
        pass
    return ''

st.markdown("""
    <style>
    table { font-size: 12px !important; }
    th, td { padding: 4px !important; text-align: center !important; }
    .safe-pick-card {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 100%, #2c5364 100%);
        color: #ffffff; padding: 12px; border-radius: 8px; border-left: 5px solid #00ff87; margin-bottom: 8px; font-size: 14px;
    }
    .match-card {
        background-color: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); color: #ffffff !important;
    }
    .team-name { color: #ffffff !important; font-size: 16px !important; font-weight: bold !important; }
    .ticket-box {
        background-color: #1a1a1a; border: 2px solid #38ef7d; padding: 15px; border-radius: 10px; color: white; margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏀 NBA L5 Parlay Master — Google Sheets & Estadísticas Reales")

# --- INICIALIZAR LA PAPELETA Y ESTADOS DE NAVEGACIÓN EN LA SESIÓN ---
if 'my_ticket' not in st.session_state:
    st.session_state.my_ticket = []

if 'target_team' not in st.session_state:
    st.session_state.target_team = "Pistons"

if 'target_player' not in st.session_state:
    st.session_state.target_player = None

# --- GESTIÓN SEGURA DE CREDENCIALES ---
try:
    API_KEY = st.secrets["general"]["odds_api_key"]
    ADMIN_PASS = st.secrets["general"]["admin_password"]
except Exception:
    API_KEY = "f824e37c9ae1f7dc0d7407059c364573"
    ADMIN_PASS = "0911"

# --- CARGA AISLADA Y DIRECTA POR HOJA ---
@st.cache_data(ttl=60)
def load_team_raw_data(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0, header=None)
        if not df.empty:
            return df, None
    except Exception as e:
        try:
            sheet_url = "https://docs.google.com/spreadsheets/d/1r7GvrxEB4dGcjM8vsbh0Q8jSdQDeIT5lBala7v3wq0E/edit"
            csv_url = sheet_url.replace('/edit', f'/gviz/tq?tqx=out:csv&sheet={sheet_name}')
            df = pd.read_csv(csv_url, header=None)
            if not df.empty:
                return df, None
        except Exception as alt_e:
            return pd.DataFrame(), f"GSheets Error: {str(e)} | CSV Alt Error: {str(alt_e)}"
    return pd.DataFrame(), f"La hoja '{sheet_name}' devolvió datos vacíos o no existe en el documento."

# --- ANALIZADOR DE BLOQUES AISLADO ---
def parse_player_blocks(df_raw):
    players_dict = {}
    current_player = None
    current_rows = []
    header_found = False
    
    df_clean = df_raw.dropna(how='all')
    
    for idx, row in df_clean.iterrows():
        val_col0 = str(row.iloc[0]).strip()
        
        if not val_col0 or val_col0.lower() in ['nan', 'none']:
            continue
            
        if val_col0.lower() in ['puntos', 'points', 'triples', 'rebotes']:
            header_found = True
            continue
            
        first_val = val_col0.replace('.', '', 1)
        if current_player and header_found and first_val.isdigit():
            current_rows.append(row.values)
            continue
            
        if not first_val.isdigit() and val_col0.lower() not in ['puntos', 'points', 'triples', 'rebotes', 'asistencias', 'robos', 'bloqueos']:
            if current_player and current_rows:
                df_p = pd.DataFrame(current_rows)
                if not df_p.empty:
                    players_dict[current_player] = df_p
            current_player = val_col0
            current_rows = []
            header_found = False
            
    if current_player and current_rows:
        df_p = pd.DataFrame(current_rows)
        if not df_p.empty:
            players_dict[current_player] = df_p
            
    return players_dict

# 1. Obtener equipos desde la API de ESPN para la cartelera de hoy
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
                'logo': t.get('logos', [{}])[0].get('href', ''),
                'id': t['id']
            })
        return teams_list
    return []

nba_teams = get_espn_teams()
team_dict_by_abbrev = {t['abbreviation']: t for t in nba_teams} if nba_teams else {}

def traducir_horario_espanol(detail_str):
    if not detail_str:
        return "Horario por confirmar"
    texto = detail_str
    dias_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dias_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    meses_es = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    for en, es in zip(dias_en, dias_es): texto = texto.replace(en, es)
    for en, es in zip(meses_en, meses_es): texto = texto.replace(en, es)
    return texto.replace("th", "").replace("st", "").replace("nd", "").replace("rd", "").replace("at ", " vs ").replace("Final", "Finalizado")

@st.cache_data(ttl=1800)
def get_todays_matchups():
    today_str = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today_str}"
    response = requests.get(url)
    matchups_list = []
    fecha_formateada = datetime.now().strftime("%A, %d de %B de %Y").capitalize()
    if response.status_code == 200:
        data = response.json()
        for event in data.get('events', []):
            status_detail = event.get('status', {}).get('type', {}).get('detail', '')
            status_traducido = traducir_horario_espanol(status_detail)
            teams_in_game = []
            for competition in event.get('competitions', []):
                for competitor in competition.get('competitors', []):
                    team_elem = competitor.get('team', {})
                    abbrev = team_elem.get('abbreviation')
                    logo_url = team_dict_by_abbrev.get(abbrev, {}).get('logo', '')
                    teams_in_game.append({'name': team_elem.get('displayName'), 'abbreviation': abbrev, 'logo': logo_url})
            if len(teams_in_game) == 2:
                matchups_list.append({'fecha_es': fecha_formateada, 'time_detail': status_traducido, 'team1': teams_in_game[1], 'team2': teams_in_game[0]})
    return matchups_list

todays_matchups = get_todays_matchups()

# --- FUNCIÓN ESTRICTA DE RACHA Y RIVAL (CON SOPORTE DE OVER / UNDER Y LÍNEAS REALES) ---
def analizar_racha_contra_rival(df_stats, col_name, linea_prop, nombre_rival, label_stat):
    """
    Evalúa la racha estricta (4/5 o 5/5) para Más de (Over) o Menos de (Under), 
    asegurando que las líneas y proyecciones tengan sentido real (ej. 0.5, 1.5).
    """
    serie = df_stats[col_name]
    total_partidos = len(serie)
    
    # Evaluar OVER (Más de)
    cumplidos_over = sum(1 for x in serie if x >= linea_prop)
    
    # Evaluar UNDER (Menos de) -> si la línea es ej. 1.5 y hace 0 o 1, cumple el under
    cumplidos_under = sum(1 for x in serie if x <= linea_prop)
    
    factor_rival = 0.95 if "spurs" in nombre_rival.lower() or "pacers" in nombre_rival.lower() else 1.05
    proyeccion_estimada = round(serie.mean() * factor_rival, 1)
    
    # Determinar si cumple el filtro estricto de 4/5 o 5/5 en Over o Under
    if cumplidos_over >= 4:
        tipo_apuesta = "Más de"
        cumplidos = cumplidos_over
    elif cumplidos_under >= 4:
        tipo_apuesta = "Menos de"
        cumplidos = cumplidos_under
    else:
        return False, "", 0, ""
    
    mensaje = (
        f"🔥 **{label_stat} ({cumplidos}/{total_partidos} partidos):** {tipo_apuesta} {linea_prop}. "
        f"Proyección contra **{nombre_rival}**: **{proyeccion_estimada}** (Alta probabilidad 🟢)."
    )
    return True, tipo_apuesta, proyeccion_estimada, mensaje

# --- MÓDULO OPTIMIZADO DE CUOTAS DE CASINOS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Control de Cuotas de Casinos")

def get_current_slot():
    now = datetime.now().time()
    if now < time(10, 0):
        return "slot_12am"
    elif now < time(17, 0):
        return "slot_10am"
    else:
        return "slot_5pm"

@st.cache_data(ttl=28800)
def get_scheduled_market_lines(api_key, time_slot):
    if not api_key:
        return {}
    try:
        events_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events?apiKey={api_key}"
        res_events = requests.get(events_url)
        if res_events.status_code != 200:
            return {}
        events = res_events.json()
        if not events:
            return {}
            
        master_dict = {}
        markets_to_fetch = "player_points,player_rebounds,player_assists,player_threes,player_steals,player_blocks"
        
        if events:
            event_id = events[0]['id']
            odds_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{event_id}/odds?apiKey={api_key}&regions=us&markets={markets_to_fetch}&oddsFormat=decimal"
            res_odds = requests.get(odds_url)
            if res_odds.status_code == 200:
                data_odds = res_odds.json()
                for bookmaker in data_odds.get('bookmakers', []):
                    for market in bookmaker.get('markets', []):
                        m_key = market.get('key')
                        for outcome in market.get('outcomes', []):
                            desc = outcome.get('description', '') or outcome.get('name', '')
                            if desc:
                                p_name_clean = desc.lower().strip()
                                if p_name_clean not in master_dict:
                                    master_dict[p_name_clean] = {}
                                point = outcome.get('point')
                                if point is not None:
                                    if m_key == 'player_points' and 'PTS' not in master_dict[p_name_clean]:
                                        master_dict[p_name_clean]['PTS'] = point
                                    elif m_key == 'player_rebounds' and 'REB' not in master_dict[p_name_clean]:
                                        master_dict[p_name_clean]['REB'] = point
                                    elif m_key == 'player_assists' and 'AST' not in master_dict[p_name_clean]:
                                        master_dict[p_name_clean]['AST'] = point
                                    elif m_key == 'player_threes' and '3P' not in master_dict[p_name_clean]:
                                        master_dict[p_name_clean]['3P'] = point
                                    elif m_key == 'player_steals' and 'STL' not in master_dict[p_name_clean]:
                                        master_dict[p_name_clean]['STL'] = point
                                    elif m_key == 'player_blocks' and 'BLK' not in master_dict[p_name_clean]:
                                        master_dict[p_name_clean]['BLK'] = point
        return master_dict
    except Exception:
        return {}

current_slot = get_current_slot()
st.sidebar.caption(f"🕒 Bloque de cuotas activo: **{current_slot.upper()}** (Gasto optimizado: 1 crédito)")
all_market_data = get_scheduled_market_lines(API_KEY, current_slot)

with st.sidebar.expander("⚙️ Forzar actualización manual"):
    pass_input = st.text_input("Contraseña de administrador:", type="password")
    if st.button("🔄 Actualizar líneas de los casinos ahora"):
        if pass_input == ADMIN_PASS:
            st.cache_data.clear()
            st.success("¡Caché limpiada! Las cuotas se actualizarán gastando solo 1 crédito.")
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")

# --- BARRA LATERAL: MI PAPELETA ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎟️ Mi Papeleta de Parlay")

if st.session_state.my_ticket:
    st.sidebar.write(f"Selecciones guardadas: **{len(st.session_state.my_ticket)}**")
    for idx, item in enumerate(st.session_state.my_ticket):
        col_t1, col_t2 = st.sidebar.columns([4, 1])
        col_t1.text(f"• {item['Jugador']}: {item['Pick']}")
        if col_t2.button("❌", key=f"del_{idx}"):
            st.session_state.my_ticket.pop(idx)
            st.rerun()
            
    if st.sidebar.button("🗑️ Vaciar Papeleta"):
        st.session_state.my_ticket = []
        st.rerun()
else:
    st.sidebar.info("Tu papeleta está vacía.")

# --- NAVEGACIÓN PRINCIPAL ---
tabs = st.tabs([
    "📅 Calendario y Partidos de Hoy", 
    "🛡️ Escáner Estricto (4/5 o 5/5)", 
    "🎟️ Mi Papeleta", 
    "👤 Vista Individual (Google Sheets)"
])

lista_equipos_sheets = [
    "Pistons", "76ers", "Trail Blazers", "Lakers", "Celtics", "Warriors", "Spurs", "Suns", "Nuggets",
    "Bucks", "Cavaliers", "Thunder", "Timberwolves", "Mavericks", "Grizzlies",
    "Clippers", "Kings", "Rockets", "Pelicans", "Jazz", "Hawks", "Heat",
    "Magic", "Knicks", "Bulls", "Pacers", "Nets", "Hornets",
    "Wizards", "Raptors"
]

def buscar_hoja_equipo(nombre_espn):
    n_lower = nombre_espn.lower()
    for hoja in lista_equipos_sheets:
        if hoja.lower() in n_lower or n_lower in hoja.lower():
            return hoja
    return None

with tabs[0]:
    st.subheader("📅 Cartelera del Día — Picks Estrictos (4/5 o 5/5)")
    st.markdown("Mostrando únicamente selecciones con rachas sólidas (Over/Under) frente al rival de hoy.")

    if not todays_matchups:
        st.warning("No se encontraron partidos oficiales programados para el día de hoy.")
    else:
        fecha_str = todays_matchups[0]['fecha_es']
        st.info(f"📍 **Jornada de Hoy:** {fecha_str} | Partidos programados: **{len(todays_matchups)}**")
        
        for m_idx, matchup in enumerate(todays_matchups):
            t1 = matchup['team1']
            t2 = matchup['team2']
            
            st.markdown(f"""
                <div class='match-card'>
                    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;'>
                        <div style='display: flex; align-items: center; gap: 10px;'>
                            <img src='{t1['logo']}' width='35' style='background: white; border-radius: 50%; padding: 2px;' onerror="this.style.display='none'">
                            <span class='team-name'>{t1['name']}</span>
                        </div>
                        <span style='color: #8b949e; font-weight: bold;'>VS</span>
                        <div style='display: flex; align-items: center; gap: 10px; text-align: right;'>
                            <span class='team-name'>{t2['name']}</span>
                            <img src='{t2['logo']}' width='35' style='background: white; border-radius: 50%; padding: 2px;' onerror="this.style.display='none'">
                        </div>
                    </div>
                    <div style='text-align: center; color: #58a6ff; font-size: 13px; font-weight: bold; border-bottom: 1px solid #30363d; padding-bottom: 8px; margin-bottom: 10px;'>
                        Estado / Horario: {matchup['time_detail']}
                    </div>
                </div>
            """, unsafe_allow_html=True)

            with st.expander(f"🔥 Ver Picks Estrictos: {t1['name']} vs {t2['name']}", expanded=False):
                eq_hoja_1 = buscar_hoja_equipo(t1['name'])
                eq_hoja_2 = buscar_hoja_equipo(t2['name'])
                
                mapa_enfrentamientos = {}
                if eq_hoja_1 and eq_hoja_2:
                    mapa_enfrentamientos[eq_hoja_1] = t2['name']
                    mapa_enfrentamientos[eq_hoja_2] = t1['name']
                
                teams_to_check = [e for e in [eq_hoja_1, eq_hoja_2] if e is not None]
                
                if not teams_to_check:
                    st.info("No se encontraron hojas configuradas en Google Sheets para estos equipos.")
                else:
                    encontro_picks = False
                    for sheet_eq in
