import streamlit as st
import requests

# Ingresa tu clave de The Odds API
ODDS_API_KEY = "f824e37c9ae1f7dc0d7407059c364573"

@st.cache_data(ttl=900) # Guarda en caché por 15 minutos para no gastar la cuota
def get_live_player_props():
    # Obtiene los eventos activos de la NBA
    url = f'https://api.the-odds-api.com/v4/sports/basketball_nba/events?apiKey={ODDS_API_KEY}'
    response = requests.get(url)
    
    if response.status_code == 200:
        events = response.json()
        # Aquí puedes iterar sobre los eventos para extraer los mercados de props
        # (player_points, player_rebounds, player_assists, player_threes)
        return events
    return []

# Ejemplo de integración en la barra lateral:
st.sidebar.markdown("---")
st.sidebar.subheader("⚡ Líneas Automáticas (The Odds API)")

if st.sidebar.button("🔄 Sincronizar Líneas de Apuestas"):
    with st.spinner("Conectando con la casas de apuestas..."):
        data_odds = get_live_player_props()
        if data_odds:
            st.sidebar.success("¡Líneas actualizadas en tiempo real!")
        else:
            st.sidebar.warning("No se pudieron obtener cuotas en vivo en este momento.")
