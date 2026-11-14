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
                    for sheet_eq in teams_to_check:
                        df_raw, err = load_team_raw_data(sheet_eq)
                        if err or df_raw.empty:
                            continue
                        p_dict = parse_player_blocks(df_raw)
                        if p_dict:
                            rival_actual = mapa_enfrentamientos.get(sheet_eq, "el equipo rival")
                            for p_name, df_p in p_dict.items():
                                if df_p.shape[1] < 6:
                                    continue
                                df_st = df_p.iloc[:, :6].copy()
                                df_st.columns = ['Puntos', 'Triples', 'Rebotes', 'Asistencias', 'Robos', 'Bloqueos']
                                for col in df_st.columns:
                                    df_st[col] = pd.to_numeric(df_st[col], errors='coerce').fillna(0).astype(int)
                                
                                m_info = all_market_data.get(p_name.lower().strip(), {})
                                lp = m_info.get('PTS', round(df_st['Puntos'].mean() - 3, 1))
                                lr = m_info.get('REB', round(df_st['Rebotes'].mean() - 1, 1))
                                la = m_info.get('AST', round(df_st['Asistencias'].mean() - 1, 1))
                                l3 = m_info.get('3P', round(df_st['Triples'].mean() - 0.5, 1))
                                # Asegurar que líneas bajas (como robos/bloqueos) tengan decimal .5 limpio o entero
                                ls = m_info.get('STL', round(df_st['Robos'].mean() - 0.5, 1))
                                lb = m_info.get('BLK', round(df_st['Bloqueos'].mean() - 0.5, 1))
                                if ls <= 0: ls = 0.5
                                if lb <= 0: lb = 0.5
                                
                                ok_p, tipo_p, _, msg_p = analizar_racha_contra_rival(df_st, 'Puntos', lp, rival_actual, "Puntos")
                                ok_r, tipo_r, _, msg_r = analizar_racha_contra_rival(df_st, 'Rebotes', lr, rival_actual, "Rebotes")
                                ok_a, tipo_a, _, msg_a = analizar_racha_contra_rival(df_st, 'Asistencias', la, rival_actual, "Asistencias")
                                ok_3, tipo_3, _, msg_3 = analizar_racha_contra_rival(df_st, 'Triples', l3, rival_actual, "Triples")
                                ok_s, tipo_s, _, msg_s = analizar_racha_contra_rival(df_st, 'Robos', ls, rival_actual, "Robos")
                                ok_b, tipo_b, _, msg_b = analizar_racha_contra_rival(df_st, 'Bloqueos', lb, rival_actual, "Bloqueos")
                                
                                if ok_p or ok_r or ok_a or ok_3 or ok_s or ok_b:
                                    encontro_picks = True
                                    st.markdown(f"**👤 {p_name}** ({sheet_eq} vs {rival_actual})")
                                    
                                    c_b1, c_b2, c_b3, c_b4, c_b5, c_b6 = st.columns(6)
                                    with c_b1:
                                        if ok_p and st.button(f"➕ {tipo_p} {lp} PTS", key=f"s_pts_{m_idx}_{sheet_eq}_{p_name}"):
                                            item = {'Jugador': p_name, 'Equipo': sheet_eq, 'Pick': f"{tipo_p} {lp} Puntos vs {rival_actual}"}
                                            if item not in st.session_state.my_ticket:
                                                st.session_state.my_ticket.append(item)
                                                st.success("¡Agregado!")
                                                st.rerun()
                                    with c_b2:
                                        if ok_r and st.button(f"➕ {tipo_r} {lr} REB", key=f"s_reb_{m_idx}_{sheet_eq}_{p_name}"):
                                            item = {'Jugador': p_name, 'Equipo': sheet_eq, 'Pick': f"{tipo_r} {lr} Rebotes vs {rival_actual}"}
                                            if item not in st.session_state.my_ticket:
                                                st.session_state.my_ticket.append(item)
                                                st.success("¡Agregado!")
                                                st.rerun()
                                    with c_b3:
                                        if ok_a and st.button(f"➕ {tipo_a} {la} AST", key=f"s_ast_{m_idx}_{sheet_eq}_{p_name}"):
                                            item = {'Jugador': p_name, 'Equipo': sheet_eq, 'Pick': f"{tipo_a} {la} Asistencias vs {rival_actual}"}
                                            if item not in st.session_state.my_ticket:
                                                st.session_state.my_ticket.append(item)
                                                st.success("¡Agregado!")
                                                st.rerun()
                                    with c_b4:
                                        if ok_3 and st.button(f"➕ {tipo_3} {l3} 3P", key=f"s_3p_{m_idx}_{sheet_eq}_{p_name}"):
                                            item = {'Jugador': p_name, 'Equipo': sheet_eq, 'Pick': f"{tipo_3} {l3} Triples vs {rival_actual}"}
                                            if item not in st.session_state.my_ticket:
                                                st.session_state.my_ticket.append(item)
                                                st.success("¡Agregado!")
                                                st.rerun()
                                    with c_b5:
                                        if ok_s and st.button(f"➕ {tipo_s} {ls} STL", key=f"s_stl_{m_idx}_{sheet_eq}_{p_name}"):
                                            item = {'Jugador': p_name, 'Equipo': sheet_eq, 'Pick': f"{tipo_s} {ls} Robos vs {rival_actual}"}
                                            if item not in st.session_state.my_ticket:
                                                st.session_state.my_ticket.append(item)
                                                st.success("¡Agregado!")
                                                st.rerun()
                                    with c_b6:
                                        if ok_b and st.button(f"➕ {tipo_b} {lb} BLK", key=f"s_blk_{m_idx}_{sheet_eq}_{p_name}"):
                                            item = {'Jugador': p_name, 'Equipo': sheet_eq, 'Pick': f"{tipo_b} {lb} Bloqueos vs {rival_actual}"}
                                            if item not in st.session_state.my_ticket:
                                                st.session_state.my_ticket.append(item)
                                                st.success("¡Agregado!")
                                                st.rerun()
                                    st.divider()
                                    
                    if not encontro_picks:
                        st.info("No hay jugadores que cumplan estrictamente con racha de 4/5 o 5/5 para este partido.")

with tabs[1]:
    st.subheader("🛡️ Escáner Estricto (Filtro 4/5 o 5/5 - Over/Under)")
    st.markdown("Escáner riguroso que evalúa tanto líneas altas como bajas (Menos de / Más de) con base en la racha L5.")

    if not todays_matchups:
        st.warning("No hay partidos programados para el día de hoy.")
    else:
        teams_playing_today = set()
        matchup_map_by_team = {}
        for m in todays_matchups:
            t1_name = m['team1']['name']
            t2_name = m['team2']['name']
            t1_abbrev = m['team1']['abbreviation']
            t2_abbrev = m['team2']['abbreviation']
            
            teams_playing_today.add(t1_name.lower())
            teams_playing_today.add(t2_name.lower())
            teams_playing_today.add(t1_abbrev.lower())
            teams_playing_today.add(t2_abbrev.lower())
            
            hoja_t1 = buscar_hoja_equipo(t1_name)
            hoja_t2 = buscar_hoja_equipo(t2_name)
            if hoja_t1 and hoja_t2:
                matchup_map_by_team[hoja_t1] = t2_name
                matchup_map_by_team[hoja_t2] = t1_name

        safe_picks_found = 0
        
        for team_name in lista_equipos_sheets:
            t_lower = team_name.lower()
            is_playing = any(t_lower in tp or tp in t_lower for tp in teams_playing_today)
            
            if not is_playing:
                continue

            df_raw, err = load_team_raw_data(team_name)
            if err or df_raw.empty:
                continue
                
            rival_nombre = matchup_map_by_team.get(team_name, "el equipo rival")
            players_dict = parse_player_blocks(df_raw)
            
            for player_name, df_p in players_dict.items():
                if df_p.shape[1] < 6:
                    continue
                    
                df_stats = df_p.iloc[:, :6].copy()
                df_stats.columns = ['Puntos', 'Triples', 'Rebotes', 'Asistencias', 'Robos', 'Bloqueos']
                
                for col in df_stats.columns:
                    df_stats[col] = pd.to_numeric(df_stats[col], errors='coerce').fillna(0).astype(int)
                    
                m_info = all_market_data.get(player_name.lower().strip(), {})
                line_pts = m_info.get('PTS', round(df_stats['Puntos'].mean() - 3, 1))
                line_reb = m_info.get('REB', round(df_stats['Rebotes'].mean() - 1, 1))
                line_ast = m_info.get('AST', round(df_stats['Asistencias'].mean() - 1, 1))
                line_3p  = m_info.get('3P', round(df_stats['Triples'].mean() - 0.5, 1))
                line_stl = m_info.get('STL', round(df_stats['Robos'].mean() - 0.5, 1))
                line_blk = m_info.get('BLK', round(df_stats['Bloqueos'].mean() - 0.5, 1))
                if line_stl <= 0: line_stl = 0.5
                if line_blk <= 0: line_blk = 0.5
                
                ok_p, _, _, msg_p = analizar_racha_contra_rival(df_stats, 'Puntos', line_pts, rival_nombre, "Puntos")
                ok_r, _, _, msg_r = analizar_racha_contra_rival(df_stats, 'Rebotes', line_reb, rival_nombre, "Rebotes")
                ok_a, _, _, msg_a = analizar_racha_contra_rival(df_stats, 'Asistencias', line_ast, rival_nombre, "Asistencias")
                ok_3, _, _, msg_3 = analizar_racha_contra_rival(df_stats, 'Triples', line_3p, rival_nombre, "Triples")
                ok_s, _, _, msg_s = analizar_racha_contra_rival(df_stats, 'Robos', line_stl, rival_nombre, "Robos")
                ok_b, _, _, msg_b = analizar_racha_contra_rival(df_stats, 'Bloqueos', line_blk, rival_nombre, "Bloqueos")
                
                mensajes_validos = [m for ok, m in [(ok_p, msg_p), (ok_r, msg_r), (ok_a, msg_a), (ok_3, msg_3), (ok_s, msg_s), (ok_b, msg_b)] if ok]
                
                if mensajes_validos:
                    safe_picks_found += 1
                    html_msg = "<br>• ".join(mensajes_validos)
                    st.markdown(f"""
                        <div class='safe-pick-card'>
                            <b>👤 {player_name}</b> ({team_name}) vs <i>{rival_nombre}</i><br>
                            <small>• {html_msg}</small>
                        </div>
                    """, unsafe_allow_html=True)

        if safe_picks_found == 0:
            st.info("ℹ️ No hay jugadores con rachas estrictas de 4/5 o 5/5 para los partidos de hoy.")

with tabs[2]:
    st.subheader("🎟️ Seguimiento de Mi Papeleta (Parlay / SGP)")
    st.markdown("Lleva el registro de tus selecciones y marca de forma interactiva si se van cumpliendo en la jornada.")

    if st.session_state.my_ticket:
        st.markdown("<div class='ticket-box'>", unsafe_allow_html=True)
        st.write(f"### 📋 Boleto Activo ({len(st.session_state.my_ticket)} selecciones)")
        
        hits_count = 0
        for idx, ticket_item in enumerate(st.session_state.my_ticket):
            c_check, c_info = st.columns([1, 5])
            is_hit = c_check.checkbox("¿Se dio?", key=f"chk_hit_{idx}")
            if is_hit:
                hits_count += 1
                status_text = "🟢 ACERTADO"
            else:
                status_text = "⏳ PENDIENTE / POR JUGAR"
                
            c_info.markdown(f"**{ticket_item['Jugador']}** ({ticket_item['Equipo']})<br>🎯 *{ticket_item['Pick']}* — **{status_text}**")
            st.divider()
            
        if hits_count == len(st.session_state.my_ticket):
            st.success("🎉 ¡Felicidades! Todas las selecciones marcadas de tu papeleta se han cumplido con éxito.")
        else:
            st.info(f"Progreso actual: {hits_count} de {len(st.session_state.my_ticket)} selecciones marcadas como acertadas.")
            
        st.markdown("</div>", unsafe_allow_html=True)
        
        if st.button("🗑️ Limpiar Toda la Papeleta"):
            st.session_state.my_ticket = []
            st.rerun()
    else:
        st.warning("No tienes ningún pick agregado en tu papeleta.")

with tabs[3]:
    st.subheader("👤 Vista Individual desde Google Sheets")
    
    sorted_teams = sorted(lista_equipos_sheets)
    default_team_idx = sorted_teams.index(st.session_state.target_team) if st.session_state.target_team in sorted_teams else 0
    
    selected_sheet_name = st.sidebar.selectbox("🏀 Seleccionar Equipo (Hoja)", sorted_teams, index=default_team_idx, key="sb_team")
    
    df_raw, error_msg = load_team_raw_data(selected_sheet_name)
    
    if error_msg:
        st.error(f"❌ Error al conectar o leer la hoja '{selected_sheet_name}': `{error_msg}`")
    elif df_raw.empty:
        st.warning(f"⚠️ La hoja '{selected_sheet_name}' está vacía o aún no tiene datos cargados.")
    else:
        players_dict = parse_player_blocks(df_raw)
        
        if not players_dict:
            st.warning(f"No se pudieron detectar bloques de jugadores en la hoja '{selected_sheet_name}'.")
        else:
            lista_jugadores = sorted(list(players_dict.keys()))
            
            default_player_idx = 0
            if st.session_state.target_player in lista_jugadores:
                default_player_idx = lista_jugadores.index(st.session_state.target_player)
                
            selected_player = st.sidebar.selectbox("👤 Seleccionar Jugador", lista_jugadores, index=default_player_idx, key="sb_player")
            
            if st.session_state.target_player and st.session_state.target_player == selected_player:
                st.session_state.target_player = None
                
            df_player_raw = players_dict[selected_player]
            
            if df_player_raw.shape[1] >= 6:
                df_display = df_player_raw.iloc[:, :6].copy()
                df_display.columns = ['Puntos', 'Triples', 'Rebotes', 'Asistencias', 'Robos', 'Bloqueos']
            else:
                df_display = df_player_raw.copy()
                
            for col in df_display.columns:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0).astype(int)
                
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #1f4068 0%, #162447 100%); padding: 15px; border-radius: 10px; border-left: 5px solid #e43f5a; margin-bottom: 20px; color: white;'>
                    <h2 style='margin:0; color: #ffffff;'>⭐ {selected_player}</h2>
                    <p style='margin:0; color: #a4b3b6;'>Franquicia: <b>{selected_sheet_name}</b> | Análisis basado en últimos 5 partidos (L5)</p>
                </div>
            """, unsafe_allow_html=True)
            
            st.write(f"### 📋 Registros de Últimos Partidos")
            styled_df = df_display.style.map(highlight_cells, subset=df_display.columns.tolist())
            st.table(styled_df)
            
            c1, c2, c3, c4 = st.columns(4)
            avg_pts = df_display['Puntos'].mean()
            avg_reb = df_display['Rebotes'].mean()
            avg_ast = df_display['Asistencias'].mean()
            avg_3p  = df_display['Triples'].mean()
            
            c1.metric("Avg Puntos", f"{avg_pts:.1f}")
            c2.metric("Avg Rebotes", f"{avg_reb:.1f}")
            c3.metric("Avg Asistencias", f"{avg_ast:.1f}")
            c4.metric("Avg Triples", f"{avg_3p:.1f}")

            st.markdown("---")
            st.subheader("💡 Sugerencias de Apuesta con Filtro Estricto (Over/Under)")
            
            p_key_lower = selected_player.lower().strip()
            market_info = all_market_data.get(p_key_lower, {})
            
            line_p = market_info.get('PTS', round(avg_pts - 3, 1))
            line_r = market_info.get('REB', round(avg_reb - 1, 1))
            line_a = market_info.get('AST', round(avg_ast - 1, 1))
            line_3 = market_info.get('3P', round(avg_3p - 0.5, 1))
            line_s = market_info.get('STL', round(df_display['Robos'].mean() - 0.5, 1))
            line_b = market_info.get('BLK', round(df_display['Bloqueos'].mean() - 0.5, 1))
            if line_s <= 0: line_s = 0.5
            if line_b <= 0: line_b = 0.5
            
            rival_opcion = st.selectbox("Selecciona el equipo rival para la proyección:", [t for t in lista_equipos_sheets if t != selected_sheet_name])
            
            ok_p, tipo_p, _, msg_p = analizar_racha_contra_rival(df_display, 'Puntos', line_p, rival_opcion, "Puntos")
            ok_r, tipo_r, _, msg_r = analizar_racha_contra_rival(df_display, 'Rebotes', line_r, rival_opcion, "Rebotes")
            ok_a, tipo_a, _, msg_a = analizar_racha_contra_rival(df_display, 'Asistencias', line_a, rival_opcion, "Asistencias")
            ok_3, tipo_3, _, msg_3 = analizar_racha_contra_rival(df_display, 'Triples', line_3, rival_opcion, "Triples")
            ok_s, tipo_s, _, msg_s = analizar_racha_contra_rival(df_display, 'Robos', line_s, rival_opcion, "Robos")
            ok_b, tipo_b, _, msg_b = analizar_racha_contra_rival(df_display, 'Bloqueos', line_b, rival_opcion, "Bloqueos")
            
            mensajes_activos = [m for ok, m in [(ok_p, msg_p), (ok_r, msg_r), (ok_a, msg_a), (ok_3, msg_3), (ok_s, msg_s), (ok_b, msg_b)] if ok]
            
            if mensajes_activos:
                st.success("¡Se encontraron mercados que cumplen con el filtro estricto (4/5 o 5/5)! 👇")
                for m in mensajes_activos:
                    st.markdown(f"- {m}")
            else:
                st.warning("⚠️ Este jugador no tiene ningún mercado que cumpla con el criterio estricto de 4/5 o 5/5 partidos en su racha L5.")
            
            col_s1, col_s2, col_s3, col_s4, col_s5, col_s6 = st.columns(6)
            with col_s1:
                if ok_p and st.button(f"➕ {tipo_p} {line_p} PTS", key=f"b_pts_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"{tipo_p} {line_p} Puntos vs {rival_opcion}"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado!")
            with col_s2:
                if ok_r and st.button(f"➕ {tipo_r} {line_r} REB", key=f"b_reb_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"{tipo_r} {line_r} Rebotes vs {rival_opcion}"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado!")
            with col_s3:
                if ok_a and st.button(f"➕ {tipo_a} {line_a} AST", key=f"b_ast_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"{tipo_a} {line_a} Asistencias vs {rival_opcion}"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado!")
            with col_s4:
                if ok_3 and st.button(f"➕ {tipo_3} {line_3} 3P", key=f"b_3p_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"{tipo_3} {line_3} Triples vs {rival_opcion}"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado!")
            with col_s5:
                if ok_s and st.button(f"➕ {tipo_s} {line_s} STL", key=f"b_stl_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"{tipo_s} {line_s} Robos vs {rival_opcion}"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado!")
            with col_s6:
                if ok_b and st.button(f"➕ {tipo_b} {line_b} BLK", key=f"b_blk_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"{tipo_b} {line_b} Bloqueos vs {rival_opcion}"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado!")
