try:
    with st.spinner('Actualizando estadísticas...'):
        df_raw = get_player_last_5(player_id)

    if not df_raw.empty:
        # 1. Limpieza profunda para evitar el error de 'non-unique index'
        df_last_5 = df_raw.copy().reset_index(drop=True)
        
        st.caption(f"Últimos 5 juegos: {selected_player_name}")
        
        # Mapeo de columnas (usando nombres cortos para móvil)
        cols_map = {
            'GAME_DATE': 'Fecha',
            'MATCHUP': 'Vs',
            'WL': 'R',
            'PTS': 'P',
            'REB': 'REB',
            'AST': 'AST',
            'FGM': 'TC',
            'FGA': 'TCA',
            'FG3M': '3P',
            'FG3A': '3PA',
            'STL': 'RB',
            'BLK': 'BL',
            'TOV': 'PÉRD',
            'PF': 'F'
        }
        
        # Seleccionamos y renombramos asegurando que no haya duplicados
        df_display = df_last_5[list(cols_map.keys())].copy()
        df_display.columns = [cols_map[col] for col in df_display.columns]
        
        # 2. Aplicar el estilo (Semáforo >= 10)
        # Usamos .applymap() en versiones anteriores de pandas o .map() en las nuevas
        # Para evitar errores, validamos que la tabla sea limpia
        styled_df = df_display.style.map(highlight_high_values)
        
        # 3. Mostrar tabla responsiva
        st.dataframe(
            styled_df,
            use_container_width=True,
            hide_index=True
        )
        
        # --- Lógica de Dobles (PTS, REB, AST, STL, BLK) ---
        def count_doubles(row):
            stats = [row['PTS'], row['REB'], row['AST'], row['STL'], row['BLK']]
            return sum(1 for s in stats if s >= 10)

        df_last_5['doubles_count'] = df_last_5.apply(count_doubles, axis=1)
        dd = sum(1 for x in df_last_5['doubles_count'] if x >= 2)
        td = sum(1 for x in df_last_5['doubles_count'] if x >= 3)
        
        # Métricas inferiores compactas
        m1, m2, m3 = st.columns(3)
        m1.metric("AVG PTS", f"{df_last_5['PTS'].mean():.1f}")
        m2.metric("AVG REB", f"{df_last_5['REB'].mean():.1f}")
        m3.metric("AVG AST", f"{df_last_5['AST'].mean():.1f}")
        
        m4, m5 = st.columns(2)
        m4.metric("Doble-Doble", f"{dd}/5")
        m5.metric("Triple-Doble", f"{td}/5")

    else:
        st.warning("No hay datos disponibles para este jugador.")

except Exception as e:
    st.error(f"Error técnico: {e}")
