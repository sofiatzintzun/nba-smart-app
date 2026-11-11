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
tabs = st.tabs([
    "📅 Calendario y Partidos de Hoy", 
    "🛡️ Escáner General", 
    "🎟️ Mi Papeleta", 
    "👤 Vista Individual (Google Sheets)"
])

with tabs[0]:
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

with tabs[1]:
    st.subheader("🔥 Picks Blindados del Día (Escáner General)")
    st.markdown("Escanea **exclusivamente a los equipos con partido programado hoy**, cruzando la información de Google Sheets con las líneas de los casinos.")

    if not todays_matchups:
        st.warning("No hay partidos programados para el día de hoy, por lo que el escáner no muestra jugadores activos.")
    else:
        # Extraer los nombres de los equipos que juegan hoy según la cartelera de ESPN
        teams_playing_today = set()
        for m in todays_matchups:
            teams_playing_today.add(m['team1']['name'].lower())
            teams_playing_today.add(m['team2']['name'].lower())
            # Añadir también abreviaturas o fragmentos clave por si acaso
            teams_playing_today.add(m['team1']['abbreviation'].lower())
            teams_playing_today.add(m['team2']['abbreviation'].lower())

        lista_equipos_sheets = [
            "Pistons", "76ers", "Trail Blazers", "Lakers", "Celtics", "Warriors", "Spurs", "Suns", "Nuggets",
            "Bucks", "Cavaliers", "Thunder", "Timberwolves", "Mavericks", "Grizzlies",
            "Clippers", "Kings", "Rockets", "Pelicans", "Jazz", "Hawks", "Heat",
            "Magic", "Knicks", "Bulls", "Pacers", "Nets", "Hornets",
            "Wizards", "Raptors"
        ]

        safe_picks_found = 0
        
        for team_name in lista_equipos_sheets:
            # Filtro estricto: verificar si el equipo de la hoja juega hoy
            # (Comparamos si el nombre de la hoja o parte de él coincide con los equipos de la cartelera de hoy)
            t_lower = team_name.lower()
            is_playing = any(t_lower in tp or tp in t_lower for tp in teams_playing_today)
            
            if not is_playing:
                continue  # Salta los equipos que NO juegan hoy

            df_raw, err = load_team_raw_data(team_name)
            if err or df_raw.empty:
                continue
                
            players_dict = parse_player_blocks(df_raw)
            for player_name, df_p in players_dict.items():
                if df_p.shape[1] < 6:
                    continue
                    
                df_stats = df_p.iloc[:, :6].copy()
                df_stats.columns = ['Puntos', 'Triples', 'Rebotes', 'Asistencias', 'Robos', 'Bloqueos']
                
                for col in df_stats.columns:
                    df_stats[col] = pd.to_numeric(df_stats[col], errors='coerce').fillna(0).astype(int)
                    
                avg_pts = df_stats['Puntos'].mean()
                avg_reb = df_stats['Rebotes'].mean()
                avg_ast = df_stats['Asistencias'].mean()
                
                p_key_lower = player_name.lower().strip()
                market_info = all_market_data.get(p_key_lower, {})
                
                picks_to_evaluate = []
                if avg_pts >= 15:
                    line_pts = market_info.get('PTS', round(avg_pts - 3, 1))
                    picks_to_evaluate.append(('Puntos', avg_pts, line_pts))
                if avg_reb >= 6:
                    line_reb = market_info.get('REB', round(avg_reb - 1, 1))
                    picks_to_evaluate.append(('Rebotes', avg_reb, line_reb))
                if avg_ast >= 5:
                    line_ast = market_info.get('AST', round(avg_ast - 1, 1))
                    picks_to_evaluate.append(('Asistencias', avg_ast, line_ast))
                    
                for stat_type, avg_val, line_val in picks_to_evaluate:
                    safe_picks_found += 1
                    pick_text = f"Más de {line_val} {stat_type} (Avg L5: {avg_val:.1f})"
                    
                    col_card, col_btn_view, col_btn_add = st.columns([3, 1, 1])
                    with col_card:
                        st.markdown(f"""
                            <div class='safe-pick-card'>
                                <b>👤 {player_name}</b> ({team_name}) — 🎯 <b>{pick_text}</b><br>
                                <small>Estadísticas L5 | Pts: {avg_pts:.1f} | Reb: {avg_reb:.1f} | Ast: {avg_ast:.1f}</small>
                            </div>
                        """, unsafe_allow_html=True)
                    with col_btn_view:
                        if st.button("👁️ Ver", key=f"view_{team_name}_{player_name}_{stat_type}"):
                            st.session_state.target_team = team_name
                            st.session_state.target_player = player_name
                            st.rerun()
                    with col_btn_add:
                        if st.button("➕ Agregar", key=f"add_{team_name}_{player_name}_{stat_type}"):
                            ticket_item = {'Jugador': player_name, 'Equipo': team_name, 'Pick': pick_text}
                            if ticket_item not in st.session_state.my_ticket:
                                st.session_state.my_ticket.append(ticket_item)
                                st.success("¡Agregado!")
                                st.rerun()
                            else:
                                st.warning("Ya está.")

        if safe_picks_found == 0:
            st.info("ℹ️ Ningún jugador de los equipos que juegan hoy cumple con los filtros mínimos de rendimiento L5.")

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
    
    lista_equipos_sheets = [
        "Pistons", "76ers", "Trail Blazers", "Lakers", "Celtics", "Warriors", "Spurs", "Suns", "Nuggets",
        "Bucks", "Cavaliers", "Thunder", "Timberwolves", "Mavericks", "Grizzlies",
        "Clippers", "Kings", "Rockets", "Pelicans", "Jazz", "Hawks", "Heat",
        "Magic", "Knicks", "Bulls", "Pacers", "Nets", "Hornets",
        "Wizards", "Raptors"
    ]
    
    sorted_teams = sorted(lista_equipos_sheets)
    default_team_idx = sorted_teams.index(st.session_state.target_team) if st.session_state.target_team in sorted_teams else 0
    
    selected_sheet_name = st.sidebar.selectbox("🏀 Seleccionar Equipo (Hoja)", sorted_teams, index=default_team_idx)
    
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
                
            selected_player = st.sidebar.selectbox("👤 Seleccionar Jugador", lista_jugadores, index=default_player_idx)
            
            # Limpiamos el objetivo temporal de navegación
            st.session_state.target_player = None
            
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
            avg_pts = df_display['Puntos'].mean()
            avg_reb = df_display['Rebotes'].mean()
            avg_ast = df_display['Asistencias'].mean()
            avg_3p = df_display['Triples'].mean()
            
            c1.metric("Avg Puntos", f"{avg_pts:.1f}")
            c2.metric("Avg Rebotes", f"{avg_reb:.1f}")
            c3.metric("Avg Asistencias", f"{avg_ast:.1f}")
            c4.metric("Avg Triples", f"{avg_3p:.1f}")

            st.markdown("---")
            st.subheader("💡 Sugerencias de Apuesta (L5)")
            
            p_key_lower = selected_player.lower().strip()
            market_info = all_market_data.get(p_key_lower, {})
            
            col_s1, col_s2, col_s3 = st.columns(3)
            
            with col_s1:
                line_p = market_info.get('PTS', round(avg_pts - 3, 1))
                st.markdown(f"**Línea Puntos:** {line_p}")
                if st.button(f"➕ Agregar Más de {line_p} PTS", key=f"btn_pts_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"Más de {line_p} Puntos"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado a la papeleta!")
                        
            with col_s2:
                line_r = market_info.get('REB', round(avg_reb - 1, 1))
                st.markdown(f"**Línea Rebotes:** {line_r}")
                if st.button(f"➕ Agregar Más de {line_r} REB", key=f"btn_reb_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"Más de {line_r} Rebotes"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado a la papeleta!")
                        
            with col_s3:
                line_a = market_info.get('AST', round(avg_ast - 1, 1))
                st.markdown(f"**Línea Asistencias:** {line_a}")
                if st.button(f"➕ Agregar Más de {line_a} AST", key=f"btn_ast_{selected_player}"):
                    item = {'Jugador': selected_player, 'Equipo': selected_sheet_name, 'Pick': f"Más de {line_a} Asistencias"}
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.success("¡Agregado a la papeleta!")
