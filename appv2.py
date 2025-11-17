import streamlit as st
import branca.colormap as cm
import geopandas as gpd
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

#FUNCION PARA SELECCIONAR TODOS

# --- INICIA EL NUEVO BLOQUE DE CÓDIGO (FUNCIÓN DE AYUDA) ---

# --- INSERTA ESTA FUNCIÓN EN LA PARTE SUPERIOR ---

def procesar_filtro_todos(seleccion_cruda, opciones_disponibles_completas):
    """
    Procesa la lógica de un multiselect con "Todos" y previene 
    que "Todos" esté seleccionado con otras opciones.
    
    Retorna:
    - seleccion_limpia: La lista que debe mostrar el widget (ej. ["Todos"] o ["Excel", "Redacción"])
    - opciones_para_filtrar: La lista de valores para usar en el .isin() de pandas
    """
    seleccion_limpia = seleccion_cruda.copy()
    
    # 1. Lógica de UX: Limpiar la selección
    
    # Si "Todos" está y algo más también, "Todos" se elimina.
    if "Todos" in seleccion_limpia and len(seleccion_limpia) > 1:
        seleccion_limpia.remove("Todos")
        
    # Si la lista queda vacía (porque se deseleccionó la última opción), 
    # se fuerza a "Todos".
    elif not seleccion_limpia:
        seleccion_limpia = ["Todos"]
        
    # Si se seleccionan todas las opciones específicas, es igual a "Todos".
    elif set(seleccion_limpia) == set(opciones_disponibles_completas):
        seleccion_limpia = ["Todos"]

    # 2. Lógica de Filtrado: ¿Qué opciones usamos para el dataframe?
    if "Todos" in seleccion_limpia:
        opciones_para_filtrar = opciones_disponibles_completas
    else:
        opciones_para_filtrar = seleccion_limpia
            
    return seleccion_limpia, opciones_para_filtrar

# --- FIN DE LA FUNCIÓN ---
# --- FIN DEL NUEVO BLOQUE DE CÓDIGO ---

#FUNCIONES DE EDAD Y SEXO
def clasificar_edad(valor):
    """
    Clasifica el valor de la edad en las categorías deseadas,
    basado en la lógica que proporcionaste.
    """
    try:
        # 1. Manejar valores nulos
        if pd.isna(valor):
            return 'Sin dato'

        # 2. Manejar valores numéricos (enteros o flotantes)
        if isinstance(valor, (int, float)):
            if 13 <= valor <= 18:
                return "13 a 18"
            elif 19 <= valor <= 35:
                return "19 a 35"
            elif 36 <= valor <= 64:
                return "36 a 64"
            elif valor >= 65 and valor <98:
                return "Mayor a 65"
            elif valor == 98:
                return "19 a 35"
            elif valor == 102: 
                return "19 a 35"
            elif valor == 99:
                return "36 a 64"
            elif  valor == 103: 
                return "30 a 39"
            elif valor == 105: 
                return "36 a 64"
            elif valor == 109:
                return "19 a 35"
            elif valor == 106:
                return "36 a 64"
            else:
                # Números fuera de rango (ej. 0-12) se consideran 'Sin dato'
                return 'Sin dato'

        # 3. Manejar valores de texto
        v = str(valor).strip()
        if v == '' or v == 'Información incompleta':
            return 'Sin dato'

        if v in ['15-19', '15 a 18', "15-18"]:
            return '13 a 18'
        elif v in ["19-35", "20-29", "20 a 29", "18 a 35 años", "20 o más", "Más de 20"]:
            return '19 a 35'
        elif v in ["30-39", "30 a 39"]:
            return "30 a 39"
        elif v in ["36-64", "40-49", "40 a 49", "50-59", "Más de 50", "36 a 64 años", "Más de 30"]:
            return '36 a 64'
        elif v in ["Más de 60", "Más de 65"]:
            return 'Mayor a 65'
        elif v in ["Sin dato"]:
            return "Sin dato"

    except:
        # Cualquier error en la conversión se marca como 'Sin dato'
        return 'Sin dato'

    # 4. Cualquier valor no clasificado se considera 'Sin dato'
    return 'Sin dato'

def normalizar_sexo(valor):
    """
    Clasifica el valor de SEXO en las 4 categorías de la imagen:
    Femenino, Masculino, NR (No Responde), Sin dato (Nulo/Vacío).
    """
    # 1. Manejar nulos
    if pd.isna(valor):
        return "Sin dato"

    v = str(valor).strip()

    # 2. Manejar vacíos
    if v == "":
        return "Sin dato"

    # 3. Categorías principales
    if v == 'Femenino':
        return 'Femenino'
    if v == 'Masculino':
        return 'Masculino'

    # 4. Agrupar "No Responde" (basado en tu lógica)
    if v in ['No indica', 'No responde', 'No contesta', 'NR']:
        return 'NR'

    # 5. Manejar "Sin dato" explícito
    if v == 'Sin dato':
        return 'Sin dato'

    # 6. Cualquier otro valor (ej. "Otro") se considera 'Sin dato'
    return 'Sin dato'

#FIN DE FUNCIONES DE EDAD Y SEXO

ruta_mapa="limitecantonal_5k_fixed.geojson"
columna_mapa="CANTÓN"

# ===============================
# Diccionario para mostrar nombres amigables
# ===============================
nombre_amigable = {
    "admision": "Admisión y lógica",
    "admisión": "Admisión y lógica",
    "eplve": "Economía para la vida",
    "eplvim": "Economía para la vida: indicadores macroeconómicos",
    "eplvmys": "Economía para la Vida: mercado y sociedad",
    "excel": "Excel",
    "excelbasico": "Excel básico",
    "excelintermedio": "Excel intermedio",
    "redaccion": "Redacción Consciente"
}

# ===============================
# Título de la app
# ===============================
st.title("📊 Mapa y Estadísticas de las personas beneficiarias: TCU Nirien - Habilidades para la Vida - UCR")

# ===============================
# Cargar datos desde Google Sheets con caché
# ===============================
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
# --- REEMPLAZA ESTE BLOQUE ---

@st.cache_data(ttl=300)
def cargar_datos():
    df = conn.read(worksheet="mapa_más_reciente")
    
    # Normalización de Cursos
    df["CURSO_NORMALIZADO"] = df["CURSO"].str.lower().str.normalize('NFKD') \
        .str.encode('ascii', errors='ignore').str.decode('utf-8')
    
    # === INICIO DE NUEVO CÓDIGO ===
    # Asumimos que las columnas se llaman 'EDAD' y 'SEXO' en tu Google Sheet
    # Si se llaman diferente, ajusta 'EDAD' y 'SEXO' aquí.
    if 'EDAD' in df.columns:
        df['EDAD_CLASIFICADA'] = df['EDAD'].apply(clasificar_edad)
    else:
        st.warning("No se encontró la columna 'EDAD' en los datos.")
        df['EDAD_CLASIFICADA'] = 'Sin dato' # Crear columna dummy
        
    if 'SEXO' in df.columns:
        df['SEXO_NORMALIZADO'] = df['SEXO'].apply(normalizar_sexo)
    else:
        st.warning("No se encontró la columna 'SEXO' en los datos.")
        df['SEXO_NORMALIZADO'] = 'Sin dato' # Crear columna dummy
    # === FIN DE NUEVO CÓDIGO ===
        
    return df

df = cargar_datos()

# --- FIN DEL REEMPLAZO ---

# ===============================
# Cargar geojson con caché
# ===============================
@st.cache_data

def cargar_geojson():
    return gpd.read_file(ruta_mapa)

try:
    gdf = cargar_geojson()
except Exception as e:
    st.error(f"Ocurrió un error cargando los archivos: {e}")
    st.stop()

# --- REEMPLAZA TODA LA SECCIÓN "with st.sidebar:" CON ESTO ---
# --- REEMPLAZA TODA LA SECCIÓN "with st.sidebar:" CON ESTO ---
# --- REEMPLAZA TODA LA SECCIÓN "with st.sidebar:" CON ESTO ---

with st.sidebar:
    st.title("Filtros Globales")

    # ===== Cursos =====
    cursos_filtrables_normalizados = sorted(set(df["CURSO_NORMALIZADO"].unique()) & set(nombre_amigable.keys()))
    cursos_filtrables_amigables = [nombre_amigable[c] for c in cursos_filtrables_normalizados]
    opciones_cursos_widget = ["Todos"] + cursos_filtrables_amigables
    
    # 1. Inicializar estado (si es la primera ejecución)
    if 'seleccion_cursos' not in st.session_state:
        st.session_state.seleccion_cursos = ["Todos"]
    
    # 2. Procesar el estado ACTUAL (que pudo ser modificado por el usuario en el paso anterior)
    seleccion_limpia, cursos_seleccionados_amigables = procesar_filtro_todos(
        st.session_state.seleccion_cursos, 
        cursos_filtrables_amigables
    )
    
    # 3. ACTUALIZAR el estado ANTES de dibujar el widget
    st.session_state.seleccion_cursos = seleccion_limpia
    
    # 4. Determinar los valores para el filtro del DataFrame
    if "Todos" in st.session_state.seleccion_cursos:
        cursos_filtrados = cursos_filtrables_normalizados
    else:
        inverso_nombre_amigable = {v: k for k, v in nombre_amigable.items()}
        cursos_filtrados = [inverso_nombre_amigable[v] for v in cursos_seleccionados_amigables]

    # 5. DIBUJAR el widget (ahora lee el estado ya limpio)
    st.multiselect(
        "Cursos", 
        opciones_cursos_widget, 
        key='seleccion_cursos' # Usamos 'key' para vincularlo al estado
    )

    # ===== Años =====
    anios_disponibles = sorted(df['AÑO'].dropna().unique())
    opciones_anios_widget = ["Todos"] + list(anios_disponibles)
    
    if 'seleccion_anios' not in st.session_state:
        st.session_state.seleccion_anios = ["Todos"]
        
    seleccion_limpia_anios, anios_seleccionados = procesar_filtro_todos(
        st.session_state.seleccion_anios, 
        anios_disponibles
    )
    st.session_state.seleccion_anios = seleccion_limpia_anios
    
    st.multiselect(
        "Años", 
        opciones_anios_widget, 
        key='seleccion_anios'
    )

    # ===== Cantones =====
    cantones_disponibles = sorted(gdf[columna_mapa].dropna().unique())
    opciones_cantones_widget = ["Todos"] + list(cantones_disponibles)
    
    if 'seleccion_cantones' not in st.session_state:
        st.session_state.seleccion_cantones = ["Todos"]
        
    seleccion_limpia_cantones, cantones_seleccionados = procesar_filtro_todos(
        st.session_state.seleccion_cantones, 
        cantones_disponibles
    )
    st.session_state.seleccion_cantones = seleccion_limpia_cantones
    
    st.multiselect(
        "Cantones", 
        opciones_cantones_widget, 
        key='seleccion_cantones'
    )

    # ===== Certificados (Sin cambios, ya que no usa "Todos") =====
    certificados_disponibles = sorted(df["CERTIFICADO"].dropna().unique())
    certificados_seleccionados = st.multiselect(
        "Certificado",
        certificados_disponibles,
        default=certificados_disponibles,
        help="1: Sí obtuvo certificado y concluyó el curso.\n0: No concluyó el curso, o lo concluyó sin certificarse."
    )

    st.divider()

    # ===== Edades =====
    edades_disponibles = sorted(df['EDAD_CLASIFICADA'].dropna().unique())
    opciones_edades_widget = ["Todos"] + list(edades_disponibles)
    
    if 'seleccion_edades' not in st.session_state:
        st.session_state.seleccion_edades = ["Todos"]
        
    seleccion_limpia_edades, edades_seleccionadas = procesar_filtro_todos(
        st.session_state.seleccion_edades, 
        edades_disponibles
    )
    st.session_state.seleccion_edades = seleccion_limpia_edades
    
    st.multiselect(
        "Grupo de Edad", 
        opciones_edades_widget, 
        key='seleccion_edades'
    )

    # ===== Sexo =====
    sexos_disponibles = sorted(df['SEXO_NORMALIZADO'].dropna().unique())
    opciones_sexos_widget = ["Todos"] + list(sexos_disponibles)
    
    if 'seleccion_sexos' not in st.session_state:
        st.session_state.seleccion_sexos = ["Todos"]
        
    seleccion_limpia_sexos, sexos_seleccionados = procesar_filtro_todos(
        st.session_state.seleccion_sexos, 
        sexos_disponibles
    )
    st.session_state.seleccion_sexos = seleccion_limpia_sexos
    
    st.multiselect(
        "Sexo", 
        opciones_sexos_widget, 
        key='seleccion_sexos'
    )

# --- FIN DEL REEMPLAZO DEL SIDEBAR ---



# ===============================
# Filtrar datos una sola vez
# ===============================
# --- REEMPLAZA ESTE BLOQUE ---

# ===============================
# Filtrar datos una sola vez
# ===============================
# --- REEMPLAZA ESTE BLOQUE ---

# ===============================
# Filtrar datos una sola vez
# ===============================
# Usamos las variables generadas en el sidebar refactorizado
df_filtrado = df[
    df["CURSO_NORMALIZADO"].isin(cursos_filtrados) &
    df["AÑO"].isin(anios_seleccionados) &
    df["CERTIFICADO"].isin(certificados_seleccionados) &
    df["CANTON_DEF"].isin(cantones_seleccionados) &
    df["EDAD_CLASIFICADA"].isin(edades_seleccionadas) &
    df["SEXO_NORMALIZADO"].isin(sexos_seleccionados)
]

# --- FIN DEL REEMPLAZO ---

# --- FIN DEL REEMPLAZO ---


# ===============================
# Mapa interactivo con folium (Versión Heatmap Logarítmico)
# ===============================
st.subheader("🗺️ Mapa Interactivo")

# 1. Preparar los datos (Función de caché)
@st.cache_data
def preparar_datos_mapa_heatmap(df_filtrado, _gdf):
    # Asegurarse de filtrar por los cantones seleccionados ANTES de agrupar
    df_filtrado_mapa = df_filtrado[df_filtrado['CANTON_DEF'].isin(cantones_seleccionados)]
    
    df_cantonal = df_filtrado_mapa.groupby('CANTON_DEF').size().reset_index(name='cantidad_beneficiarios')
    df_detalle = df_filtrado_mapa.groupby(['CANTON_DEF', 'CURSO_NORMALIZADO', 'AÑO']).size().reset_index(name='conteo')
    
    # Hacer el merge solo con los cantones del GeoJSON
    gdf_merged = _gdf.merge(df_cantonal, how="left", left_on=columna_mapa, right_on="CANTON_DEF")
    
    # Creamos 'cantidad_color' que es 0 para NaN
    gdf_merged['cantidad_color'] = gdf_merged['cantidad_beneficiarios'].fillna(0)
    return gdf_merged, df_detalle

gdf_merged, df_detalle = preparar_datos_mapa_heatmap(df_filtrado, gdf)

# 2. Preparar el mapa base
m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)
# --- INICIA EL REEMPLAZO (SOLUCIÓN B) ---

# --- INICIA EL REEMPLAZO (SOLUCIÓN B) ---

# 3. Definir la escala de color (Heatmap por Escalones Logarítmicos)
max_beneficiarios = gdf_merged['cantidad_color'].max()

# Aseguramos un rango válido
if max_beneficiarios < 10:
    max_beneficiarios = 10 
    
# Definimos los colores base
color_cero = '#ece7f2' # El color más bajo (para 0)
color_no_seleccionado = '#D3D3D3' # Gris
colores_escala = ['#a6bddb', '#74a9cf', '#3690c0', '#0570b0', '#034e7b'] # 5 tonos de azul

# Creamos "escalones" logarítmicos. 
# Generamos 6 puntos (para 5 rangos) entre 0 (log 1) y el log del máximo.
try:
    # np.logspace(start, stop, num) -> crea 'num' puntos entre 10^start y 10^stop
    pasos = np.logspace(
        start=0, # 10^0 = 1
        stop=np.log10(max_beneficiarios), # 10^log10(max) = max
        num=6 # 6 puntos (ej. 1, 10, 100, 1000...)
    )
    
    # Redondeamos a enteros para la leyenda
    pasos = [int(round(p)) for p in pasos]
    
    # Aseguramos que los pasos sean únicos (evita [1, 1, 2, 4...])
    pasos = sorted(list(set(pasos))) 
    
    # Si hay menos pasos que colores (ej. max es muy bajo), reducimos los colores
    num_colores_necesarios = len(pasos) - 1
    if num_colores_necesarios < 1:
        # Fallback por si max_beneficiarios es 1
        pasos = [1, 2]
        colores_escala = [colores_escala[0]]
    else:
        colores_escala = colores_escala[:num_colores_necesarios]

except Exception as e:
    # Fallback si numpy falla (ej. max_beneficiarios es 0)
    pasos = [1, 10]
    colores_escala = [colores_escala[0]]

# Creamos el StepColormap
colormap = cm.StepColormap(
    colors=colores_escala,
    index=pasos, # Los "escalones" donde cambia el color
    vmin=1, 
    vmax=max_beneficiarios,
    caption='Cantidad de Beneficiarios (Escala por pasos)'
)

# La lógica del bucle "for _, row..." (paso 4) 
# y la lógica de color dentro de él NO CAMBIAN.
# StepColormap y LogColormap se llaman igual: colormap(valor)
# Y tu lógica de "color_cero" y "color_no_seleccionado" ya maneja los casos < 1.


# 4. Iterar y aplicar el color del colormap y el popup
for _, row in gdf_merged.iterrows():
    canton = row[columna_mapa]
    cantidad_real_popup = row['cantidad_beneficiarios'] # Puede ser NaN
    cantidad_para_color = row['cantidad_color'] # Es 0 si es NaN
    
    # Lógica de color MEJORADA
    if canton not in cantones_seleccionados:
        color = color_no_seleccionado
        fill_opacity = 0.3
    elif cantidad_para_color == 0:
        color = color_cero # Color específico para 0
        fill_opacity = 0.7
    else:
        color = colormap(cantidad_para_color) # Aplicar el heatmap logarítmico
        fill_opacity = 0.7 

    # Lógica de Popup (la mantenemos exactamente igual)
    detalles = df_detalle[df_detalle['CANTON_DEF'] == canton]
    if detalles.empty:
        # Mostrar esto solo si el cantón SÍ fue seleccionado pero no tiene datos
        if canton in cantones_seleccionados:
            detalle_html = "<i>0 beneficiarios (según filtros)</i>"
        else:
            detalle_html = "<i>Cantón no seleccionado</i>"
    else:
        detalle_html = "<ul>"
        for _, d in detalles.iterrows():
            curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
            detalle_html += f"<li>{curso} ({int(d['AÑO'])}): {d['conteo']} personas</li>"
        detalle_html += "</ul>"

    popup_html = f"""
        <strong>Cantón:</strong> {canton}<br>
        <strong>Total de beneficiarios:</strong> {cantidad_real_popup if not pd.isnull(cantidad_real_popup) else '0'}<br>
        <strong>Detalle:</strong> {detalle_html}
    """

    folium.GeoJson(
        row['geometry'],
        style_function=lambda feature, color=color, fill_opacity=fill_opacity: {
            'fillColor': color,
            'color': 'black',
            'weight': 1,
            'fillOpacity': fill_opacity
        },
        tooltip=folium.Tooltip(f"{canton}"),
        popup=folium.Popup(popup_html, max_width=300),
        highlight_function=lambda x: {'weight': 3, 'color': 'yellow'},
    ).add_to(m)
    
# 5. Agregar la leyenda (barra de color) al mapa
m.add_child(colormap)

# --- FIN DEL BLOQUE DE REEMPLAZO ---

# 6. Mostrar el mapa en Streamlit
st_folium(m, width=600, height=400, returned_objects=[])

# --- INICIO DEL BLOQUE DE CÓDIGO DE OBSERVACIONES SIN DATO DE CANTÓN ---

# ===============================
# Mostrar observaciones "Sin dato" (fuera del mapa)
# ===============================

# 1. Filtrar los datos 'Sin dato' del dataframe principal ya filtrado
df_sin_dato = df_filtrado[df_filtrado['CANTON_DEF'] == "Sin dato"]
total_sin_dato = len(df_sin_dato)

# 2. Solo mostrar el expander si hay datos 'Sin dato'
if total_sin_dato >= 0:
    with st.expander(f"ℹ️ **Observaciones 'Sin dato' (fuera del mapa): {total_sin_dato} personas**"):
        
        # 3. Obtener el detalle desde el dataframe 'df_detalle' que ya calculamos para el mapa
        detalles_sin_dato = df_detalle[df_detalle['CANTON_DEF'] == "Sin dato"]
        
        if detalles_sin_dato.empty:
            st.write("No se encontró detalle para las observaciones 'Sin dato'.")
        else:
            st.markdown("<strong>Detalle por curso y año:</strong>", unsafe_allow_html=True)
            
            # 4. Reutilizar la misma lógica de los popups del mapa para generar la lista
            detalle_html = "<ul>"
            for _, d in detalles_sin_dato.iterrows():
                # Usamos el diccionario 'nombre_amigable'
                curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
                detalle_html += f"<li>{curso} ({int(d['AÑO'])}): {d['conteo']} personas</li>"
            detalle_html += "</ul>"
            
            st.markdown(detalle_html, unsafe_allow_html=True)

# --- FIN DEL BLOQUE DE OBSERVACIONES SIN DATO DE CANTÓN ---




# ===============================
# Estadísticas descriptivas
# ===============================
st.subheader("📊 Estadísticas Descriptivas")

# Tabla resumen por curso
st.subheader("Resumen por Curso")
resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
resumen_curso['Total'] = resumen_curso.sum(axis=1)
resumen_curso['% Certificado'] = (resumen_curso[1] / resumen_curso['Total']) * 100
resumen_curso = resumen_curso.rename(index=nombre_amigable)
st.dataframe(resumen_curso)

# Tabla resumen por cantón
st.subheader("Resumen por Cantón")
resumen_canton = df_filtrado.groupby(['CANTON_DEF', 'CERTIFICADO']).size().unstack(fill_value=0)
resumen_canton['Total'] = resumen_canton.sum(axis=1)
resumen_canton['% Certificado'] = (resumen_canton[1] / resumen_canton['Total']) * 100
st.dataframe(resumen_canton)

# Gráfico de línea
st.subheader("Gráfico de Línea por Año")
df_anual = df_filtrado.groupby(['AÑO', 'CERTIFICADO']).size().unstack(fill_value=0)
df_anual['Total'] = df_anual.sum(axis=1)
df_anual['% Certificado'] = (df_anual[1] / df_anual['Total']) * 100
fig_linea = px.line(df_anual, x=df_anual.index, y='% Certificado', 
                    title='Evolución de la Participación y Aprobación por Año',
                    labels={'AÑO': 'Año', '% Certificado': '% Certificado'})
st.plotly_chart(fig_linea)

# ===============================
# Descargar datos filtrados en formato XLSX
# ===============================
st.subheader("📥 Descargar Datos Filtrados")

@st.cache_data
def convertir_a_excel(df):
    import io
    from pandas import ExcelWriter

    output = io.BytesIO()
    with ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='DatosFiltrados')
    processed_data = output.getvalue()
    return processed_data

archivo_excel = convertir_a_excel(df_filtrado)

st.download_button(
    label="📥 Descargar datos filtrados en Excel",
    data=archivo_excel,
    file_name='datos_filtrados.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# ===============================
# Descargar datos colapsados (por Cantón - Curso - Año)
# ===============================
st.subheader("📥 Descargar Datos Colapsados (por Cantón - Curso - Año)")

# Permitir que el usuario active la opción
activar_colapsado = st.checkbox("Quiero descargar los datos colapsados por Cantón - Curso - Año")

if activar_colapsado:
    # Crear columna combinada Curso + Año
    df_filtrado['CURSO_AÑO'] = df_filtrado['CURSO_NORMALIZADO'].map(nombre_amigable).fillna(df_filtrado['CURSO_NORMALIZADO'].str.title()) + " " + df_filtrado['AÑO'].astype(str)
    
    # Pivotear los datos
    df_pivot = df_filtrado.pivot_table(
        index='CANTON_DEF',
        columns='CURSO_AÑO',
        values='CERTIFICADO',  # o cualquier columna (usamos .size() para contar)
        aggfunc='count',
        fill_value=0
    ).reset_index()

    # Calcular la columna TOTAL
    df_pivot['TOTAL'] = df_pivot.drop(columns='CANTON_DEF').sum(axis=1)

    # Reordenar columnas: CANTON_DEF primero, luego cursos + años ordenados alfabéticamente, luego TOTAL
    columnas_ordenadas = ['CANTON_DEF'] + sorted([c for c in df_pivot.columns if c not in ['CANTON_DEF', 'TOTAL']]) + ['TOTAL']
    df_pivot = df_pivot[columnas_ordenadas]

    # Preparar para descargar
    archivo_excel_colapsado = convertir_a_excel(df_pivot)

    st.download_button(
        label="📥 Descargar datos colapsados en Excel",
        data=archivo_excel_colapsado,
        file_name='datos_colapsados.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
