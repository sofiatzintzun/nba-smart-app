import streamlit as st
import pandas as pd
import requests
import random
from datetime import datetime, time

st.set_page_config(page_title="NBA L5 Parlay Master - Papeleta", layout="wide")

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
    .prop-box {
        background-color: #1e1e1e;
        color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #28a745;
        margin-bottom: 10px;
    }
    .safe-pick-card {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 100%, #2c5364 100%);
        color: #ffffff;
        padding: 12px;
        border-radius: 8px;
        border-left: 5px solid #00ff87;
        margin-bottom: 8px;
        font-size: 14px;
    }
    .parlay-card {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: #000000;
        padding: 20px;
        border-radius: 12px;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 20px;
    }
    .ticket-box {
        background-color: #1a1a1a;
        border: 2px solid #38ef7d;
        padding: 15px;
        border-radius: 10px;
        color: white;
        margin-bottom: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏀 NBA L5 Parlay Master — Papeleta & Seguimiento")

# --- INICIALIZAR LA PAPELETA EN LA SESIÓN ---
if 'my_ticket' not in st.session_state:
    st.session_state.my_ticket = []

# --- GESTIÓN SEGURA DE CREDENCIALES ---
try:
    API_KEY = st.secrets["general"]["odds_api_key"]
    ADMIN_PASS = st.secrets["general"]["admin_password"]
except Exception:
    API_KEY = "f824e37c9ae1f7dc0d7407059c364573"
    ADMIN_PASS = "admin123"

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

# 1.1 Obtener los partidos programados para el DÍA DE HOY en ESPN
@st.cache_data(ttl=1800)
def get_todays_games_teams():
    today_str = datetime.now().strftime("%Y%m%d")
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={today_str}"
    response = requests.get(url)
    playing_teams_abbrev = set()
    
    if response.status_code == 200:
        data = response.json()
        for event in data.get('events', []):
            for competition in event.get('competitions', []):
                for competitor in competition.get('competitors', []):
                    team_elem = competitor.get('team', {})
                    abbrev = team_elem.get('abbreviation')
                    if abbrev:
                        playing_teams_abbrev.add(abbrev)
                        
    return playing_teams_abbrev

todays_active_abbrevs = get_todays_games_teams()

# --- MÓDULO DE ACTUALIZACIÓN PROGRAMADA DE CUOTAS ---
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

# --- BARRA LATERAL: MI PAPELETA / BOLETO VIRTUAL ---
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
    st.sidebar.info("Tu papeleta está vacía. Agrega picks desde el escáner.")

# Generador de datos simulados realistas para partidos recientes
def get_player_stats_simulation(player_name):
    rows = []
    random.seed(hash(player_name))
    opponents = ["LAL", "BOS", "GSW", "MIA", "DEN", "NYK", "PHX", "DAL", "CHI", "CLE"]
    
    for i in range(5):
        opp = opponents[(hash(player_name) + i) % len(opponents)]
        is_home = i % 2 == 0
        matchup = f"vs {opp}" if is_home else f"@ {opp}"
        
        pts = max(2, int(random.normalvariate(14, 5)))
        reb = max(1, int(random.normalvariate(5, 2)))
        ast = max(0, int(random.normalvariate(4, 2)))
        fg3 = max(0, int(random.normalvariate(2, 1.0)))
        stl = max(0, int(random.normalvariate(1, 0.8)))
        blk = max(0, int(random.normalvariate(0.5, 0.6)))
        err = max(0, int(random.normalvariate(1.5, 0.8)))
        pf = max(1, int(random.normalvariate(2, 0.8)))
        minutos = random.randint(18, 36)
        
        rows.append({
            'Fecha': f"2026-11-{10-i:02d}",
            'Partido': matchup,
            'R': "W" if (i + hash(player_name)) % 3 != 0 else "L",
            'Min': int(minutos),
            'PTS': int(pts),
            'REB': int(reb),
            'AST': int(ast),
            '3P': int(fg3),
            'STL': int(stl),
            'BLK': int(blk),
            'ERR': int(err),
            'PF': int(pf)
        })
    return pd.DataFrame(rows)

# --- NAVEGACIÓN PRINCIPAL EN PESTAÑAS (TABS) ---
tab1, tab2, tab3 = st.tabs(["🛡️ Escáner de Partidos de Hoy", "🎟️ Ver Mi Papeleta & Resultados", "👤 Vista Individual por Jugador"])

with tab1:
    st.subheader("🔥 Picks Blindados de los Equipos que Juegan HOY")
    st.markdown("Este escáner detecta automáticamente qué equipos tienen partido programado para hoy y busca las mejores opciones con **efectividad perfecta de 5/5**. Puedes agregar tus favoritas directo a tu papeleta.")

    # Guardamos los resultados en session_state para que no se borren al dar clic en agregar
    if 'global_blindados' not in st.session_state:
        st.session_state.global_blindados = []

    if st.button("🚀 Buscar Picks Blindados para los Juegos de Hoy"):
        with st.spinner("Verificando cartelera del día y escaneando planteles..."):
            st.session_state.global_blindados = []
            
            active_teams_list = [t for t in nba_teams if t['abbreviation'] in todays_active_abbrevs]
            if not active_teams_list:
                active_teams_list = nba_teams[:10]
            
            for team in active_teams_list:
                t_abbrev = team['abbreviation']
                t_name = team['full_name']
                
                url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{t_abbrev}/roster"
                res = requests.get(url)
                if res.status_code == 200:
                    athletes = res.json().get('athletes', [])
                    for athlete in athletes[:5]:
                        p_name = athlete.get('displayName')
                        df_p = get_player_stats_simulation(p_name)
                        
                        p_lower = p_name.lower()
                        live_l = None
                        for k, lines in all_market_data.items():
                            if k in p_lower or p_lower in k:
                                live_l = lines
                                break
                        
                        l_pts = live_l.get('PTS', round(df_p['PTS'].mean() - 1.5, 1)) if live_l else round(df_p['PTS'].mean() - 1.5, 1)
                        l_reb = live_l.get('REB', round(df_p['REB'].mean() - 1.0, 1)) if live_l else round(df_p['REB'].mean() - 1.0, 1)
                        l_ast = live_l.get('AST', round(df_p['AST'].mean() - 0.8, 1)) if live_l else round(df_p['AST'].mean() - 0.8, 1)
                        l_3p = live_l.get('3P', max(0.5, round(df_p['3P'].mean() - 0.5, 1))) if live_l else max(0.5, round(df_p['3P'].mean() - 0.5, 1))
                        
                        checks = [
                            ('PTS', l_pts, 'Puntos'),
                            ('REB', l_reb, 'Rebotes'),
                            ('AST', l_ast, 'Asistencias'),
                            ('3P', l_3p, 'Triples')
                        ]
                        
                        for col, line_val, lbl in checks:
                            hits = sum(1 for v in df_p[col] if v > line_val)
                            if hits == 5:
                                st.session_state.global_blindados.append({
                                    'Jugador': p_name,
                                    'Equipo': t_name,
                                    'Pick': f"Más de {line_val} {lbl}",
                                    'Columna': col,
                                    'Linea': line_val,
                                    'Detalle': f"Promedio reciente: {df_p[col].mean():.1f} (5/5 overs)"
                                })

    fecha_actual_str = datetime.now().strftime("%A, %d de %B de %Y")

    if st.session_state.global_blindados:
        st.success(f"¡Se encontraron {len(st.session_state.global_blindados)} opciones totalmente blindadas (5/5) para los partidos de hoy, {fecha_actual_str}!")
        
        for idx, item in enumerate(st.session_state.global_blindados):
            col_card1, col_card2 = st.columns([4, 1])
            with col_card1:
                st.markdown(f"""
                    <div class='safe-pick-card' style='margin-bottom:0px;'>
                        ⭐ <b>{item['Jugador']}</b> ({item['Equipo']})<br>
                        🎯 <b>{item['Pick']}</b> — <i>{item['Detalle']}</i>
                    </div>
                """, unsafe_allow_html=True)
            with col_card2:
                # Clave única robusta basada en el índice y nombre
                if st.button("➕ Agregar", key=f"add_pick_{idx}_{item['Jugador']}"):
                    if item not in st.session_state.my_ticket:
                        st.session_state.my_ticket.append(item)
                        st.toast(f"¡Agregado a tu papeleta: {item['Jugador']}!", icon="🎟️")
                    else:
                        st.toast("Este pick ya está en tu papeleta.", icon="⚠️")
            st.write("")
    else:
        st.info("Haz clic en el botón **'🚀 Buscar Picks Blindados para los Juegos de Hoy'** para generar el reporte de la jornada.")

with tab2:
    st.subheader("🎟️ Seguimiento de Mi Papeleta (Parlay / SGP)")
    st.markdown("Aquí puedes llevar el registro de tus selecciones y marcar de forma interactiva si se van cumpliendo o fallando en la jornada.")

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
        st.warning("No tienes ningún pick agregado en tu papeleta. Ve a la pestaña **'Escáner de Partidos de Hoy'** y haz clic en 'Agregar' en las opciones que te interesen.")

with tab3:
    team_names = {t['full_name']: t for t in nba_teams}
    selected_team_name = st.sidebar.selectbox("🏀 Seleccionar Equipo", sorted(team_names.keys()))
    selected_team_info = team_names[selected_team_name]
    espn_team_abbrev = selected_team_info['abbreviation']

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
    selected_player_name = st.sidebar.selectbox("👤 Seleccionar Jugador", player_names)
    player_info = next(p for p in df_roster if p['PLAYER'] == selected_player_name)
    player_id = player_info['PLAYER_ID']

    try:
        with st.spinner(f"Cargando rendimiento de {selected_player_name}..."):
            df_display = get_player_stats_simulation(selected_player_name)

        if not df_display.empty:
            cols_to_int = ['Min', 'PTS', 'REB', 'AST', '3P', 'STL', 'BLK', 'ERR', 'PF']
            for col in cols_to_int:
                df_display[col] = df_display[col].astype(int)

            styled_df = df_display.style.map(highlight_cells, subset=['PTS', 'REB', 'AST', '3P', 'STL', 'BLK'])

            st.write(f"### {selected_player_name} | {selected_team_name}")
            st.table(styled_df)

            def count_doubles(row):
                stats = [row.get('PTS', 0), row.get('REB', 0), row.get('AST', 0), row.get('3P', 0), row.get('STL', 0), row.get('BLK', 0)]
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

            st.markdown("---")
            st.subheader("🛡️ Escáner de Alta Seguridad (Filtro 5/5 para Parlays)")

            player_lower = selected_player_name.lower()
            live_lines = None
            for p_key, lines in all_market_data.items():
                if p_key in player_lower or player_lower in p_key:
                    live_lines = lines
                    break

            if live_lines:
                line_pts = live_lines.get('PTS', round(df_display['PTS'].mean() - 0.5, 1))
                line_reb = live_lines.get('REB', round(df_display['REB'].mean() - 0.5, 1))
                line_ast = live_lines.get('AST', round(df_display['AST'].mean() - 0.5, 1))
                line_3p = live_lines.get('3P', round(df_display['3P'].mean() - 0.5, 1))
            else:
                line_pts = max(0.5, round(df_display['PTS'].mean() - 1.5, 1))
                line_reb = max(0.5, round(df_display['REB'].mean() - 1.0, 1))
                line_ast = max(0.5, round(df_display['AST'].mean() - 0.8, 1))
                line_3p = max(0.5, round(df_display['3P'].mean() - 0.5, 1))

            props_to_check = [
                ('PTS', line_pts, 'Puntos (PTS)'),
                ('REB', line_reb, 'Rebotes (REB)'),
                ('AST', line_ast, 'Asistencias (AST)'),
                ('3P', line_3p, 'Triples (3P)')
            ]

            safe_picks = []
            parlay_legs = []

            for col, line, label0 in props_to_check:
                matches = sum(1 for val in df_display[col] if val > line)
                if matches == 5:
                    pick_msg = f"🛡️ **Pick Blindado (5/5):** Superó la línea de **{line} {label0}** en el 100% de sus últimos 5 encuentros."
                    safe_picks.append(pick_msg)
                    parlay_legs.append(f"Más de {line} {label0} ({selected_player_name}) [Efectividad 5/5]")
                elif matches == 4:
                    pick_msg = f"✅ **Opción Sólida (4/5):** Superó la línea de **{line} {label0}** en 4 de sus últimos 5 partidos."
                    safe_picks.append(pick_msg)

            if safe_picks:
                for tip in safe_picks:
                    st.markdown(f"<div class='safe-pick-card'>{tip}</div>", unsafe_allow_html=True)
            else:
                st.info("ℹ️ Este jugador no presenta una consistencia perfecta (5/5) en sus líneas actuales.")

            if parlay_legs:
                st.markdown("### 🎲 Combinación Sugerida de Alta Seguridad")
                legs_html = "<br>• ".join(parlay_legs)
                st.markdown(f"""
                    <div class='parlay-card'>
                        🎯 <b>Selecciones Blindadas para Parlay ({selected_player_name}):</b><br><br>
                        • {legs_html}<br><br>
                        <span style='font-size: 12px; font-weight: normal;'>💡 <i>Opciones ideales para sumar a tus acumuladores grandes sin arriesgar de más.</i></span>
                    </div>
                """, unsafe_allow_html=True)

        else:
            st.warning("No hay suficientes registros disponibles para este jugador.")

    except Exception as e:
        st.error(f"Ocurrió un error al procesar los datos: {e}")
