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
        background-color: #161b22; border: 1px solid #30363d; padding: 20px; border-radius: 12px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); color: #ffffff !important;
    }
    .team-name { color: #ffffff !important; font-size: 16px !important; font-weight: bold !important; }
    .parlay-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); color: #000000; padding: 20px; border-radius: 12px; font-weight: bold; margin-top: 20px; margin-bottom: 20px;
    }
    .ticket-box {
        background-color: #1a1a1a; border: 2px solid #38ef7d; padding: 15px; border-radius: 10px; color: white; margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏀 NBA L5 Parlay Master — Google Sheets & Estadísticas Reales")

# --- INICIALIZAR LA PAPELETA EN LA SESIÓN ---
if 'my_ticket' not in st.session_state:
    st.session_state.my_ticket = []

# --- GESTIÓN SEGURA DE CREDENCIALES ---
try:
    API_KEY = st.secrets["general"]["odds_api_key"]
    ADMIN_PASS = st.secrets["general"]["admin_password"]
except Exception:
    API_KEY = "f824e37c9ae1f7dc0d7407059c364573"
    ADMIN_PASS = "0911"

# --- CONEXIÓN A GOOGLE SHEETS CON HEADER=NONE PARA LEER TODO EL BLOQUE ---
@st.cache_data(ttl=600)
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

# --- ANALIZADOR DE BLOQUES VERTICALES OPTIMIZADO ---
def parse_player_blocks(df_raw):
    players_dict = {}
    current_player = None
    current_rows = []
    header_found = False
    
    df_clean = df_raw.dropna(how='all')
    
    for idx, row in df_clean.iterrows():
        val_col0 = str(row.iloc[0]).strip()
        
        # Omitir celdas vacías o NaN
        if not val_col0 or val_col0.lower() in ['nan', 'none']:
            continue
            
        # Detectar la fila de encabezados de estadísticas ('Puntos', 'Points', etc.)
        if val_col0.lower() in ['puntos', 'points', 'triples', 'rebotes']:
            header_found = True
            continue
            
        # Si ya encontramos el encabezado y el primer valor es un número, es una fila de estadísticas de partido
        first_val = val_col0.replace('.', '', 1)
        if current_player and header_found and first_val.isdigit():
            current_rows.append(row.values)
            continue
            
        # Si tiene texto y no es un número, es un NUEVO JUGADOR
        if not first_val.isdigit() and val_col0.lower() not in ['puntos', 'points', 'triples', 'rebotes', 'asistencias', 'robos', 'bloqueos']:
            if current_player and current_rows:
                df_p = pd.DataFrame(current_rows)
                if not df_p.empty:
                    players_dict[current_player] = df_p
            current_player = val_col0
            current_rows = []
            header_found = False
            
    # Guardar el último jugador del recorrido
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

# --- MÓDULO DE ACTUALIZACIÓN DE CUOTAS DE CASINOS ---
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

@st.cache_data(ttl=43200)
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
            
        markets_to_fetch = "player_points,player_rebounds,player_assists,player_threes"
        master_dict = {}
        
        for event in events[:3]:
            event_id = event['id']
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
        return master_dict
    except Exception:
        return {}

current_slot = get_current_slot()
st.sidebar.caption(f"🕒 Bloque de cuotas activo: **{current_slot.upper()}**")
all_market_data = get_scheduled_market_lines(API_KEY, current_slot)

with st.sidebar.expander("⚙️ Forzar actualización manual"):
    pass_input = st.text_input("Contraseña de administrador:", type="password")
    if st.button("🔄 Actualizar líneas de los casinos ahora"):
        if pass_input == ADMIN_PASS:
            st.cache_data.clear()
            st.success("¡Caché limpiada! Las cuotas se actualizarán.")
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
tab1, tab2, tab3, tab4 = st.tabs([
    "📅 Calendario y Partidos de Hoy", 
    "🛡️ Escáner General", 
    "🎟️ Mi Papeleta", 
    "👤 Vista Individual (Google Sheets)"
])

with tab1:
    st.subheader("📅 Cartelera del Día — Tarjetas de Partidos y Picks Reales")
    st.markdown("Visualiza los enfrentamientos de hoy con estadísticas estructuradas y limpias.")

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
                    <div style='text-align: center; color: #58a6ff; font-size: 13px; font-weight: bold; border-top: 1px solid #30363d; padding-top: 8px;'>
                        Estado / Horario: {matchup['time_detail']}
                    </div>
                </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("🔥 Picks Blindados del Día (Escáner General)")
    st.markdown("Escanea los planteles de la jornada utilizando la información cargada en Google Sheets.")
    st.info("💡 Asegúrate de seleccionar el equipo en la pestaña individual para validar los registros de los últimos 5 partidos.")

with tab3:
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

with tab4:
    st.subheader("👤 Vista Individual desde Google Sheets")
    
    lista_equipos_sheets = [
        "Pistons", "76ers", "Trail Blazers", "Lakers", "Celtics", "Warriors", "Spurs", "Suns", "Nuggets",
        "Bucks", "Cavaliers", "Thunder", "Timberwolves", "Mavericks", "Grizzlies",
        "Clippers", "Kings", "Rockets", "Pelicans", "Jazz", "Hawks", "Heat",
        "Magic", "Knicks", "Bulls", "Pacers", "Nets", "Hornets",
        "Wizards", "Raptors"
    ]
    
    selected_sheet_name = st.sidebar.selectbox("🏀 Seleccionar Equipo (Hoja)", sorted(lista_equipos_sheets))
    
    df_raw, error_msg = load_team_raw_data(selected_sheet_name)
    
    if error_msg:
        st.error(f"❌ Error al conectar o leer la hoja '{selected_sheet_name}': `{error_msg}`")
    elif df_raw.empty:
        st.warning(f"⚠️ La hoja '{selected_sheet_name}' está vacía o aún no tiene datos cargados.")
    else:
        # Parseamos los bloques verticales correctamente
        players_dict = parse_player_blocks(df_raw)
        
        if not players_dict:
            st.warning(f"No se pudieron detectar bloques de jugadores en la hoja '{selected_sheet_name}'. Verifica que los nombres de los jugadores estén en la primera columna.")
        else:
            lista_jugadores = sorted(list(players_dict.keys()))
            selected_player = st.sidebar.selectbox("👤 Seleccionar Jugador", lista_jugadores)
            
            df_player_raw = players_dict[selected_player]
            
            if df_player_raw.shape[1] >= 6:
                df_display = df_player_raw.iloc[:, :6].copy()
                df_display.columns = ['Puntos', 'Triples', 'Rebotes', 'Asistencias', 'Robos', 'Bloqueos']
            else:
                df_display = df_player_raw.copy()
                
            for col in df_display.columns:
                df_display[col] = pd.to_numeric(df_display[col], errors='coerce').fillna(0).astype(int)
                
            st.write(f"### 📋 Registros de Últimos Partidos: {selected_player} | {selected_sheet_name}")
            
            styled_df = df_display.style.map(highlight_cells, subset=df_display.columns.tolist())
            st.table(styled_df)
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Avg Puntos", f"{df_display['Puntos'].mean():.1f}")
            c2.metric("Avg Rebotes", f"{df_display['Rebotes'].mean():.1f}")
            c3.metric("Avg Asistencias", f"{df_display['Asistencias'].mean():.1f}")
            c4.metric("Avg Triples", f"{df_display['Triples'].mean():.1f}")
