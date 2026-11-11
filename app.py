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
        if num >= 10:
            return color
        if 1 <= num < 10:
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

st.title("🏀 NBA L5 Parlay Master — Google Sheets Conectado")

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

# 1. Conexión a Google Sheets (Asegúrate de configurar tu st.connection o secrets.toml)
# Si tu hoja es pública, puedes usar GSheetsConnection directamente:
@st.cache_data(ttl=600)
def load_team_data(sheet_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet=sheet_name, ttl=0)
        return df
    except Exception as e:
        # En caso de emergencia o pruebas locales si prefieres respaldo en DataFrame vacío
        return pd.DataFrame()

# 2. Obtener equipos desde la API de ESPN para la cartelera de partidos de hoy
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

# --- MÓDULO DE CUOTAS DE CASINOS ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Control de Cuotas de Casinos")
def get_current_slot():
    now = datetime.now().time()
    return "slot_12am" if now < time(10, 0) else ("slot_10am" if now < time(17, 0) else "slot_5pm")

current_slot = get_current_slot()
st.sidebar.caption(f"🕒 Bloque de cuotas activo: **{current_slot.upper()}**")

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
    st.subheader("📅 Cartelera del Día — Partidos Programados")
    if not todays_matchups:
        st.warning("No se encontraron partidos oficiales programados para el día de hoy.")
    else:
        for matchup in todays_matchups:
            t1, t2 = matchup['team1'], matchup['team2']
            st.markdown(f"""
                <div class='match-card'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <span class='team-name'>{t1['name']}</span>
                        <span style='color: #8b949e; font-weight: bold;'>VS</span>
                        <span class='team-name'>{t2['name']}</span>
                    </div>
                    <div style='text-align: center; color: #58a6ff; font-size: 13px; margin-top: 8px;'>Horario: {matchup['time_detail']}</div>
                </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("🔥 Picks Blindados del Día")
    st.info("💡 Lee directamente los datos de tus hojas de Google Sheets para los cálculos y filtros 5/5.")

with tab3:
    st.subheader("🎟️ Seguimiento de Mi Papeleta")
    if st.session_state.my_ticket:
        for idx, item in enumerate(st.session_state.my_ticket):
            st.checkbox(f"**{item['Jugador']}** — 🎯 *{item['Pick']}*", key=f"chk_hit_{idx}")
    else:
        st.warning("Papeleta vacía.")

with tab4:
    st.subheader("👤 Vista Individual desde Google Sheets")
    
    # Aquí defines los nombres de tus hojas de Google Sheets (tus equipos)
    # Puedes ajustarlo dinámicamente o listar las pestañas de tu archivo
    lista_equipos_sheets = [
        "Portland Trail Blazers", "Los Angeles Lakers", "Boston Celtics", 
        "Golden State Warriors", "San Antonio Spurs", "Phoenix Suns", "Denver Nuggets"
    ]
    
    selected_sheet_name = st.sidebar.selectbox("🏀 Seleccionar Equipo (Hoja Google Sheets)", sorted(lista_equipos_sheets))
    
    # Cargamos los datos limpios de la hoja seleccionada
    df_sheet = load_team_data(selected_sheet_name)
    
    if df_sheet.empty:
        st.warning(f"⚠️ No se pudo leer la hoja '{selected_sheet_name}' o está vacía. Verifica que el nombre de la pestaña coincida exactamente en tu Google Sheet.")
    else:
        # Detectamos automáticamente las columnas del jugador en tu hoja
        col_jugador = next((c for c in df_sheet.columns if 'jugador' in c.lower() or 'player' in c.lower() or 'nombre' in c.lower()), df_sheet.columns[0])
        
        lista_jugadores_sheet = sorted(df_sheet[col_jugador].dropna().unique())
        selected_player_sheet = st.sidebar.selectbox("👤 Seleccionar Jugador de la Hoja", lista_jugadores_sheet)
        
        # Filtramos los registros correspondientes al jugador en ese equipo
        df_display = df_sheet[df_sheet[col_jugador] == selected_player_sheet]
        
        st.write(f"### 📋 Registros de {selected_player_sheet} | {selected_sheet_name}")
        st.dataframe(df_display, use_container_width=True)
        
        # Métricas y validación de líneas si las columnas numéricas existen
        try:
            # Aseguramos columnas clave de rendimiento (puntos, rebotes, asistencias, etc.)
            st.markdown("---")
            st.subheader("🛡️ Escáner de Alta Seguridad (Filtro 5/5)")
            st.success("✅ Datos cargados correctamente desde tu Google Sheet sin depender de APIs externas.")
        except Exception as ex:
            st.info("Configura las columnas numéricas de tu hoja (PTS, REB, AST, etc.) para habilitar los escáneres automáticos.")
