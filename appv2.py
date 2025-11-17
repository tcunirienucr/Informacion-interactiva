import streamlit as st
import branca.colormap as cm
import geopandas as gpd
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import io
from pandas import ExcelWriter

# ===============================
# FUNCIÓN DE LÓGICA DE FILTROS
# ===============================
def procesar_filtro_todos(seleccion_cruda, opciones_disponibles_completas):
    """
    Procesa la lógica de un multiselect con "Todos" y previene 
    que "Todos" esté seleccionado con otras opciones.
    """
    seleccion_limpia = seleccion_cruda.copy()
    
    # 1. Lógica de UX: Limpiar la selección
    if "Todos" in seleccion_limpia and len(seleccion_limpia) > 1:
        seleccion_limpia.remove("Todos")
    elif not seleccion_limpia:
        seleccion_limpia = ["Todos"]
    elif set(seleccion_limpia) == set(opciones_disponibles_completas):
        seleccion_limpia = ["Todos"]

    # 2. Lógica de Filtrado
    if "Todos" in seleccion_limpia:
        opciones_para_filtrar = opciones_disponibles_completas
    else:
        opciones_para_filtrar = seleccion_limpia
            
    return seleccion_limpia, opciones_para_filtrar

# ===============================
# FUNCIONES DE LIMPIEZA DE DATOS
# ===============================
def clasificar_edad(valor):
    try:
        if pd.isna(valor):
            return 'Sin dato'
        if isinstance(valor, (int, float)):
            if 13 <= valor <= 18: return "13 a 18"
            if 19 <= valor <= 35: return "19 a 35"
            if 36 <= valor <= 64: return "36 a 64"
            if 65 <= valor < 98: return "Mayor a 65"
            if valor in [98, 102, 109]: return "19 a 35"
            if valor in [99, 105, 106]: return "36 a 64"
            if valor == 103: return "30 a 39"
            return 'Sin dato'
        v = str(valor).strip()
        if v in ['', 'Información incompleta', 'Sin dato']: return 'Sin dato'
        if v in ['15-19', '15 a 18', "15-18"]: return '13 a 18'
        if v in ["19-35", "20-29", "20 a 29", "18 a 35 años", "20 o más", "Más de 20"]: return '19 a 35'
        if v in ["30-39", "30 a 39"]: return "30 a 39"
        if v in ["36-64", "40-49", "40 a 49", "50-59", "Más de 50", "36 a 64 años", "Más de 30"]: return '36 a 64'
        if v in ["Más de 60", "Más de 65"]: return 'Mayor a 65'
    except:
        return 'Sin dato'
    return 'Sin dato'

def normalizar_sexo(valor):
    if pd.isna(valor): return "Sin dato"
    v = str(valor).strip()
    if v == "": return "Sin dato"
    if v == 'Femenino': return 'Femenino'
    if v == 'Masculino': return 'Masculino'
    if v in ['No indica', 'No responde', 'No contesta', 'NR']: return 'NR'
    if v == 'Sin dato': return 'Sin dato'
    return 'Sin dato' # "Otro" se trata como "Sin dato"

# ===============================
# CONFIGURACIÓN INICIAL
# ===============================
ruta_mapa = "limitecantonal_5k_fixed.geojson"
columna_mapa = "CANTÓN"

nombre_amigable = {
    "admision": "Admisión y lógica",
    "eplve": "Economía para la vida",
    "eplvim": "Economía para la vida: indicadores macroeconómicos",
    "eplvmys": "Economía para la Vida: mercado y sociedad",
    "excel": "Excel",
    "excelbasico": "Excel básico",
    "excelintermedio": "Excel intermedio",
    "redaccion": "Redacción Consciente"
}

st.title("📊 Mapa y Estadísticas de las personas beneficiarias: TCU Nirien - Habilidades para la Vida - UCR")

# ===============================
# CARGA DE DATOS (CACHEADO)
# ===============================
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
# --- INICIA REEMPLAZO DE cargar_datos ---

@st.cache_data(ttl=300)
def cargar_datos():
    df = conn.read(worksheet="mapa_más_reciente")
    
    df["CURSO_NORMALIZADO"] = df["CURSO"].str.lower().str.normalize('NFKD') \
        .str.encode('ascii', errors='ignore').str.decode('utf-8')
    
    if 'EDAD' in df.columns:
        df['EDAD_CLASIFICADA'] = df['EDAD'].apply(clasificar_edad)
    else:
        st.warning("No se encontró la columna 'EDAD' en los datos.")
        df['EDAD_CLASIFICADA'] = 'Sin dato'
        
    if 'SEXO' in df.columns:
        df['SEXO_NORMALIZADO'] = df['SEXO'].apply(normalizar_sexo)
    else:
        st.warning("No se encontró la columna 'SEXO' en los datos.")
        df['SEXO_NORMALIZADO'] = 'Sin dato'
    
    # --- INICIA LA CORRECCIÓN DE AÑO ---
    if 'AÑO' in df.columns:
        # 1. Convertir a numérico. '2022.0' -> 2022.0, 'Sin dato' -> NaN
        df['AÑO'] = pd.to_numeric(df['AÑO'], errors='coerce')
        
        # 2. Convertir a tipo Int64 (entero que soporta NaNs)
        # 2022.0 -> 2022, NaN -> <NA>
        df['AÑO'] = df['AÑO'].astype('Int64')
        
        # 3. Convertir a string. 2022 -> '2022', <NA> -> '<NA>'
        df['AÑO'] = df['AÑO'].astype(str)
        
        # 4. Reemplazar los strings nulos por 'Sin dato'
        df['AÑO'] = df['AÑO'].replace(['<NA>', 'nan'], 'Sin dato')
    else:
        st.warning("No se encontró la columna 'AÑO' en los datos.")
        df['AÑO'] = 'Sin dato'
    # --- FIN DE LA CORRECCIÓN DE AÑO ---

    if 'CERTIFICADO' in df.columns:
        df['CERTIFICADO'] = df['CERTIFICADO'].astype(str)

    return df

# --- FIN DE REEMPLAZO ---

@st.cache_data
def cargar_geojson():
    return gpd.read_file(ruta_mapa)

try:
    df = cargar_datos()
    gdf = cargar_geojson()
except Exception as e:
    st.error(f"Ocurrió un error cargando los archivos: {e}")
    st.stop()

# ===============================
# SIDEBAR - FILTROS GLOBALES
# ===============================
with st.sidebar:
    st.title("Filtros Globales")

    # ===== Cursos =====
    cursos_filtrables_normalizados = sorted(set(df["CURSO_NORMALIZADO"].unique()) & set(nombre_amigable.keys()))
    cursos_filtrables_amigables = [nombre_amigable[c] for c in cursos_filtrables_normalizados]
    opciones_cursos_widget = ["Todos"] + cursos_filtrables_amigables
    
    if 'seleccion_cursos' not in st.session_state:
        st.session_state.seleccion_cursos = ["Todos"]
    
    seleccion_limpia, cursos_seleccionados_amigables = procesar_filtro_todos(
        st.session_state.seleccion_cursos, 
        cursos_filtrables_amigables
    )
    st.session_state.seleccion_cursos = seleccion_limpia
    
    if "Todos" in st.session_state.seleccion_cursos:
        cursos_filtrados = cursos_filtrables_normalizados
    else:
        inverso_nombre_amigable = {v: k for k, v in nombre_amigable.items()}
        cursos_filtrados = [inverso_nombre_amigable[v] for v in cursos_seleccionados_amigables]

    st.multiselect(
        "Cursos", 
        opciones_cursos_widget, 
        key='seleccion_cursos'
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

    # ===== Certificados =====
    certificados_disponibles = sorted(df["CERTIFICADO"].dropna().unique())
    # Asignar un default que funcione (ej. todas las opciones)
    if 'seleccion_certificados' not in st.session_state:
        st.session_state.seleccion_certificados = certificados_disponibles.copy()

    st.multiselect(
        "Certificado",
        certificados_disponibles,
        key='seleccion_certificados',
        help="1: Sí obtuvo certificado y concluyó el curso.\n0: No concluyó el curso, o lo concluyó sin certificarse."
    )
    # Usar el valor del state para el filtro
    certificados_seleccionados = st.session_state.seleccion_certificados


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

# ===============================
# FILTRADO PRINCIPAL DE DATOS
# ===============================
try:
    df_filtrado = df[
        (df["CURSO_NORMALIZADO"].isin(cursos_filtrados)) &
        (df["AÑO"].isin(anios_seleccionados)) &
        (df["CERTIFICADO"].isin(certificados_seleccionados)) &
        (df["CANTON_DEF"].isin(cantones_seleccionados)) &
        (df["EDAD_CLASIFICADA"].isin(edades_seleccionadas)) &
        (df["SEXO_NORMALIZADO"].isin(sexos_seleccionados))
    ]
except Exception as e:
    st.error(f"Error al aplicar filtros: {e}")
    st.stop()


# ===============================
# MAPA INTERACTIVO (OPTIMIZADO)
# ===============================
st.subheader("🗺️ Mapa Interactivo")

# 1. Preparar los datos (Función de caché de DATOS)
@st.cache_data
def preparar_datos_mapa_heatmap(_df_filtrado, _cantones_seleccionados, _columna_mapa, _gdf):
    # Aplicar filtro de cantón AQUÍ para el detalle
    df_filtrado_mapa = _df_filtrado[_df_filtrado['CANTON_DEF'].isin(_cantones_seleccionados)]
    
    df_cantonal = df_filtrado_mapa.groupby('CANTON_DEF').size().reset_index(name='cantidad_beneficiarios')
    df_detalle = df_filtrado_mapa.groupby(['CANTON_DEF', 'CURSO_NORMALIZADO', 'AÑO']).size().reset_index(name='conteo')
    
    gdf_merged = _gdf.merge(df_cantonal, how="left", left_on=_columna_mapa, right_on="CANTON_DEF")
    gdf_merged['cantidad_color'] = gdf_merged['cantidad_beneficiarios'].fillna(0)
    
    return gdf_merged, df_detalle

# 2. Generar el mapa (Función de caché de RECURSOS)
# --- OPTIMIZACIÓN ---
# Esta función crea el objeto 'm' y lo guarda en caché.
# Solo se volverá a ejecutar si los datos de entrada (gdf_merged, df_detalle, etc.) cambian.
@st.cache_resource
def generar_mapa_folium(_gdf_merged, _df_detalle, _columna_mapa, _cantones_seleccionados, _nombre_amigable):
    m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

    max_beneficiarios = _gdf_merged['cantidad_color'].max()
    if max_beneficiarios < 10:
        max_beneficiarios = 10
        
    color_cero = '#ece7f2'
    color_no_seleccionado = '#D3D3D3'
    colores_escala = ['#a6bddb', '#74a9cf', '#3690c0', '#0570b0', '#034e7b']

    try:
        pasos = np.logspace(start=0, stop=np.log10(max_beneficiarios), num=6)
        pasos = [int(round(p)) for p in pasos]
        pasos = sorted(list(set(pasos)))
        
        num_colores_necesarios = len(pasos) - 1
        if num_colores_necesarios < 1:
            pasos = [1, 2]
            colores_escala = [colores_escala[0]]
        else:
            colores_escala = colores_escala[:num_colores_necesarios]
    except Exception:
        pasos = [1, 10]
        colores_escala = [colores_escala[0]]

    colormap = cm.StepColormap(
        colors=colores_escala,
        index=pasos,
        vmin=1,
        vmax=max_beneficiarios,
        caption='Cantidad de Beneficiarios (Escala por pasos)'
    )

    # Este es el bucle lento que ahora está DENTRO de la función cacheada
    for _, row in _gdf_merged.iterrows():
        canton = row[_columna_mapa]
        cantidad_real_popup = row['cantidad_beneficiarios']
        cantidad_para_color = row['cantidad_color']
        
        if canton not in _cantones_seleccionados:
            color = color_no_seleccionado
            fill_opacity = 0.3
        elif cantidad_para_color == 0:
            color = color_cero
            fill_opacity = 0.7
        else:
            color = colormap(cantidad_para_color)
            fill_opacity = 0.7

        detalles = _df_detalle[_df_detalle['CANTON_DEF'] == canton]
        if detalles.empty:
            detalle_html += f"<li>{curso} ({d['AÑO']}): {d['conteo']} personas</li>"
        else:
            detalle_html = "<ul>"
            for _, d in detalles.iterrows():
                curso = _nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
                detalle_html += f"<li>{curso} ({int(d['AÑO'])}): {d['conteo']} personas</li>"
            detalle_html += "</ul>"

        popup_html = f"<strong>Cantón:</strong> {canton}<br>" \
                     f"<strong>Total de beneficiarios:</strong> {cantidad_real_popup if not pd.isnull(cantidad_real_popup) else '0'}<br>" \
                     f"<strong>Detalle:</strong> {detalle_html}"

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
        
    m.add_child(colormap)
    return m

# 3. Llamar a las funciones cacheadas en orden
gdf_merged, df_detalle = preparar_datos_mapa_heatmap(df_filtrado, cantones_seleccionados, columna_mapa, gdf)
mapa_generado = generar_mapa_folium(gdf_merged, df_detalle, columna_mapa, cantones_seleccionados, nombre_amigable)

# 4. Mostrar el mapa (¡Esta es la única parte que se ejecuta siempre, y es rápido!)
st_folium(mapa_generado, width=700, height=500, returned_objects=[])


# ===============================
# EXPANDER "SIN DATO" (Corregido)
# ===============================
df_sin_dato = df_filtrado[df_filtrado['CANTON_DEF'] == "Sin dato"]
total_sin_dato = len(df_sin_dato)

# --- CORRECCIÓN DE BUG ---
# Cambiado de >= 0 a > 0 para que no se muestre si hay 0
if total_sin_dato > 0:
    with st.expander(f"ℹ️ **Observaciones 'Sin dato' (fuera del mapa): {total_sin_dato} personas**"):
        
        # Usamos los datos de df_detalle que ya están filtrados
        detalles_sin_dato = df_detalle[df_detalle['CANTON_DEF'] == "Sin dato"]
        
        if detalles_sin_dato.empty:
            st.write("No se encontró detalle para las observaciones 'Sin dato'.")
        else:
            st.markdown("<strong>Detalle por curso y año:</strong>", unsafe_allow_html=True)
            detalle_html = "<ul>"
            for _, d in detalles_sin_dato.iterrows():
                curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
                detalle_html += f"<li>{curso} ({int(d['AÑO'])}): {d['conteo']} personas</li>"
            detalle_html += "</ul>"
            st.markdown(detalle_html, unsafe_allow_html=True)

# ===============================
# ESTADÍSTICAS DESCRIPTIVAS (Optimizadas)
# ===============================
st.subheader("📊 Estadísticas Descriptivas")

# --- OPTIMIZACIÓN ---
# Mover la generación de estadísticas a una función cacheada
@st.cache_data
def generar_estadisticas(_df_filtrado, _nombre_amigable):
    # Tabla resumen por curso
    resumen_curso = _df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
    if not resumen_curso.empty:
        resumen_curso['Total'] = resumen_curso.sum(axis=1)
        # Evitar división por cero si 'Total' es 0
        resumen_curso['% Certificado'] = resumen_curso.apply(
            lambda row: (row['1'] / row['Total']) * 100 if row['Total'] > 0 and '1' in row else 0, axis=1
        )
        resumen_curso = resumen_curso.rename(index=_nombre_amigable)
    
    # Tabla resumen por cantón
    resumen_canton = _df_filtrado.groupby(['CANTON_DEF', 'CERTIFICADO']).size().unstack(fill_value=0)
    if not resumen_canton.empty:
        resumen_canton['Total'] = resumen_canton.sum(axis=1)
        resumen_canton['% Certificado'] = resumen_canton.apply(
            lambda row: (row['1'] / row['Total']) * 100 if row['Total'] > 0 and '1' in row else 0, axis=1
        )

    # Gráfico de línea
    df_anual = _df_filtrado.groupby(['AÑO', 'CERTIFICADO']).size().unstack(fill_value=0)
    if not df_anual.empty:
        df_anual['Total'] = df_anual.sum(axis=1)
        df_anual['% Certificado'] = df_anual.apply(
            lambda row: (row['1'] / row['Total']) * 100 if row['Total'] > 0 and '1' in row else 0, axis=1
        )
    
    fig_linea = px.line(df_anual, x=df_anual.index, y='% Certificado',
                        title='Evolución de la Aprobación por Año',
                        labels={'AÑO': 'Año', '% Certificado': '% Certificado'})
    
    return resumen_curso, resumen_canton, fig_linea

# Llamar a la función cacheada
resumen_curso, resumen_canton, fig_linea = generar_estadisticas(df_filtrado, nombre_amigable)

st.subheader("Resumen por Curso")
st.dataframe(resumen_curso)

st.subheader("Resumen por Cantón")
st.dataframe(resumen_canton)

st.subheader("Gráfico de Línea por Año")
st.plotly_chart(fig_linea)

# ===============================
# DESCARGAR DATOS (Corregido)
# ===============================

# Función de conversión (cacheada)
@st.cache_data
def convertir_a_excel(_df):
    output = io.BytesIO()
    with ExcelWriter(output, engine='xlsxwriter') as writer:
        _df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

# --- Descarga 1: Datos Filtrados ---
st.subheader("📥 Descargar Datos Filtrados")
archivo_excel_filtrado = convertir_a_excel(df_filtrado)
st.download_button(
    label="📥 Descargar datos filtrados en Excel",
    data=archivo_excel_filtrado,
    file_name='datos_filtrados.xlsx',
    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
)

# --- Descarga 2: Datos Colapsados ---
st.subheader("📥 Descargar Datos Colapsados (por Cantón - Curso - Año)")
activar_colapsado = st.checkbox("Generar datos colapsados para descargar")

if activar_colapsado:
    st.info("Generando archivo colapsado... esto puede tardar un momento.")
    
    # --- CORRECCIÓN DE BUG ---
    # Usar .copy() para evitar el SettingWithCopyWarning
    df_para_pivot = df_filtrado.copy()
    
    df_para_pivot['CURSO_AÑO'] = df_para_pivot['CURSO_NORMALIZADO'].map(nombre_amigable).fillna(df_para_pivot['CURSO_NORMALIZADO'].str.title()) + " " + df_para_pivot['AÑO'].astype(str)
    
    df_pivot = df_para_pivot.pivot_table(
        index='CANTON_DEF',
        columns='CURSO_AÑO',
        values='CERTIFICADO', # Usar una columna que no sea numérica para contar
        aggfunc='count',
        fill_value=0
    ).reset_index()

    df_pivot['TOTAL'] = df_pivot.drop(columns='CANTON_DEF').sum(axis=1)
    columnas_ordenadas = ['CANTON_DEF'] + sorted([c for c in df_pivot.columns if c not in ['CANTON_DEF', 'TOTAL']]) + ['TOTAL']
    df_pivot = df_pivot[columnas_ordenadas]

    archivo_excel_colapsado = convertir_a_excel(df_pivot)

    st.download_button(
        label="📥 Descargar datos colapsados en Excel",
        data=archivo_excel_colapsado,
        file_name='datos_colapsados.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
