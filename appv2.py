import streamlit as st
import branca.colormap as cm
import geopandas as gpd
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import plotly.express as px
import unicodedata

st.set_page_config(layout="wide", page_title="Mapa y Estadísticas — TCU Nirien")

# ---------------------------
# Funciones auxiliares
# ---------------------------
def clasificar_edad(valor):
    try:
        if pd.isna(valor):
            return 'Sin dato'
        if isinstance(valor, (int, float, np.integer, np.floating)):
            v = int(valor)
            if 13 <= v <= 18:
                return "13 a 18"
            elif 19 <= v <= 35:
                return "19 a 35"
            elif 36 <= v <= 64:
                return "36 a 64"
            elif v >= 65 and v < 98:
                return "Mayor a 65"
            # casos especiales
            elif v in (98, 102, 109):
                return "19 a 35"
            elif v in (99, 105, 106):
                return "36 a 64"
            elif v == 103:
                return "30 a 39"
            else:
                return 'Sin dato'
        v = str(valor).strip()
        if v == '' or v.lower() == 'información incompleta':
            return 'Sin dato'
        if v in ['15-19', '15 a 18', '15-18']:
            return '13 a 18'
        if v in ["19-35", "20-29", "20 a 29", "18 a 35 años", "20 o más", "Más de 20"]:
            return '19 a 35'
        if v in ["30-39", "30 a 39"]:
            return "30 a 39"
        if v in ["36-64", "40-49", "40 a 49", "50-59", "Más de 50", "36 a 64 años", "Más de 30"]:
            return '36 a 64'
        if v in ["Más de 60", "Más de 65"]:
            return 'Mayor a 65'
        if v in ["Sin dato"]:
            return "Sin dato"
    except Exception:
        return 'Sin dato'
    return 'Sin dato'

def normalizar_sexo(valor):
    if pd.isna(valor):
        return "Sin dato"
    v = str(valor).strip()
    if v == "":
        return "Sin dato"
    low = v.lower()
    if low in ['femenino', 'f', 'mujer', 'female']:
        return 'Femenino'
    if low in ['masculino', 'm', 'hombre', 'male']:
        return 'Masculino'
    if low in ['no indica', 'no responde', 'no contesta', 'nr']:
        return 'NR'
    if low in ['sin dato', 'ns']:
        return 'Sin dato'
    return 'Sin dato'

def strip_accents(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ascii', errors='ignore').decode('utf-8') if isinstance(s, str) else s

def safe_get_column(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

# ---------------------------
# Config y rutas
# ---------------------------
ruta_mapa = "limitecantonal_5k_fixed.geojson"
columna_mapa = "CANTÓN"  # columna en el geojson con el nombre del cantón

# Diccionario nombres amigables
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

st.title("📊 Mapa y Estadísticas de las personas beneficiarias: TCU Nirien - Habilidades para la Vida - UCR")

# ---------------------------
# Cargar datos (cacheados una vez por sesión)
# ---------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def cargar_datos():
    # Lee la hoja (ajustá worksheet si hace falta)
    df = conn.read(worksheet="mapa_más_reciente")

    # Normalizaciones y tipos
    df['CURSO'] = df.get('CURSO', '').fillna('').astype(str)
    df['CURSO_NORMALIZADO'] = df['CURSO'].str.lower().apply(strip_accents).str.strip()

    # AÑO -> Int (si no posible -> NaN)
    df['AÑO'] = pd.to_numeric(df.get('AÑO'), errors='coerce').astype('Int64')

    # Flags -> int 0/1
    for col in ['CERTIFICADO', 'DESERCION', 'INTERMITENTE']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else:
            df[col] = 0

    # CANTON_DEF fallback
    if 'CANTON_DEF' not in df.columns:
        alt = safe_get_column(df, ['CANTÓN', 'Canton', 'CANTON', 'canton'])
        if alt is not None:
            df['CANTON_DEF'] = df[alt].fillna('Sin dato').astype(str).str.strip()
        else:
            df['CANTON_DEF'] = 'Sin dato'
    else:
        df['CANTON_DEF'] = df['CANTON_DEF'].fillna('Sin dato').astype(str).str.strip()

    # EDAD y SEXO
    if 'EDAD' in df.columns:
        df['EDAD_CLASIFICADA'] = df['EDAD'].apply(clasificar_edad)
    else:
        df['EDAD_CLASIFICADA'] = 'Sin dato'

    if 'SEXO' in df.columns:
        df['SEXO_NORMALIZADO'] = df['SEXO'].apply(normalizar_sexo)
    else:
        df['SEXO_NORMALIZADO'] = 'Sin dato'

    return df

@st.cache_data(ttl=3600)
def cargar_geojson():
    return gpd.read_file(ruta_mapa)

# Cargar fuera del formulario (solo una vez por sesión)
try:
    df = cargar_datos()
except Exception as e:
    st.error(f"Error cargando Google Sheet: {e}")
    st.stop()

try:
    gdf = cargar_geojson()
except Exception as e:
    st.error(f"Error cargando GeoJSON: {e}")
    st.stop()

# ---------------------------
# SIDEBAR: filtros dentro de un form (no se ejecuta hasta aplicar)
# ---------------------------
with st.sidebar:
    st.header("Filtros")

    with st.form("form_filtros"):
        # Cursos
        select_all_cursos = st.checkbox("Seleccionar todos los cursos", value=True)
        cursos_disponibles_raw = sorted(df['CURSO_NORMALIZADO'].dropna().unique())
        cursos_display = [nombre_amigable.get(c, c.title()) for c in cursos_disponibles_raw]
        if not select_all_cursos:
            seleccion_cursos_display = st.multiselect("Cursos (seleccioná uno o más)", cursos_display, default=cursos_display[:3])
        else:
            seleccion_cursos_display = None

        # Años
        select_all_anios = st.checkbox("Seleccionar todos los años", value=True)
        anios_disponibles = sorted([int(i) for i in df['AÑO'].dropna().unique()])
        if not select_all_anios:
            seleccion_anios = st.multiselect("Años (seleccioná uno o más)", anios_disponibles, default=anios_disponibles)
        else:
            seleccion_anios = None

        # Cantones
        select_all_cantones = st.checkbox("Seleccionar todos los cantones", value=True)
        cantones_disponibles = sorted(gdf[columna_mapa].dropna().unique())
        if not select_all_cantones:
            seleccion_cantones = st.multiselect("Cantones (seleccioná uno o más)", cantones_disponibles, default=cantones_disponibles[:5])
        else:
            seleccion_cantones = None

        # Estados (CERTIFICADO / DESERCION / INTERMITENTE) - checkboxes
        st.markdown("---")
        select_all_flags = st.checkbox("Seleccionar todos los estados (CERTIFICADO / DESERCION / INTERMITENTE)", value=True)
        if not select_all_flags:
            flag_cert = st.checkbox("CERTIFICADO == 1", value=True)
            flag_des = st.checkbox("DESERCION == 1", value=False)
            flag_int = st.checkbox("INTERMITENTE == 1", value=False)
        else:
            flag_cert = flag_des = flag_int = True

        # Grupo de edad
        st.markdown("---")
        select_all_edades = st.checkbox("Seleccionar todos los grupos de edad", value=True)
        edades_disponibles = sorted(df['EDAD_CLASIFICADA'].dropna().unique())
        if not select_all_edades:
            seleccion_edades = st.multiselect("Grupo de Edad", edades_disponibles, default=edades_disponibles)
        else:
            seleccion_edades = None

        # Sexo
        select_all_sexos = st.checkbox("Seleccionar todos los sexos", value=True)
        sexos_disponibles = sorted(df['SEXO_NORMALIZADO'].dropna().unique())
        if not select_all_sexos:
            seleccion_sexos = st.multiselect("Sexo", sexos_disponibles, default=sexos_disponibles)
        else:
            seleccion_sexos = None

        # Botón para aplicar filtros
        aplicar = st.form_submit_button("Aplicar filtros")

# Si no se aplicó el form: detener la ejecución (evita recálculos)
if not aplicar:
    st.info("Seleccione filtros en el sidebar y presione 'Aplicar filtros' para mostrar resultados.")
    st.stop()

# ---------------------------
# Construir las listas finales de selección (desambiguar nombres amigables)
# ---------------------------
# Cursos: convertir la selección visible a keys normalizadas
if seleccion_cursos_display is None:
    cursos_filtrados = list(cursos_disponibles_raw)
else:
    cursos_filtrados = []
    # primero keys de nombre_amigable que coincidan
    for key, friendly in nombre_amigable.items():
        if friendly in seleccion_cursos_display:
            cursos_filtrados.append(key)
    # luego las que no están en nombre_amigable
    for raw, disp in zip(cursos_disponibles_raw, cursos_display):
        if disp in seleccion_cursos_display and raw not in cursos_filtrados:
            cursos_filtrados.append(raw)

# Años
if seleccion_anios is None:
    anios_seleccionados = anios_disponibles
else:
    anios_seleccionados = seleccion_anios

# Cantones
if seleccion_cantones is None:
    cantones_seleccionados = cantones_disponibles
else:
    cantones_seleccionados = seleccion_cantones

# Flags
cert_flags = {'CERTIFICADO': flag_cert, 'DESERCION': flag_des, 'INTERMITENTE': flag_int}
filter_por_flags = not select_all_flags and not (flag_cert and flag_des and flag_int)  # si el usuario desmarcó select_all_flags y eligió subset

# Edades
if seleccion_edades is None:
    edades_seleccionadas = edades_disponibles
else:
    edades_seleccionadas = seleccion_edades

# Sexos
if seleccion_sexos is None:
    sexos_seleccionados = sexos_disponibles
else:
    sexos_seleccionados = seleccion_sexos

# ---------------------------
# Filtrado eficiente (se hace solo después de presionar aplicar)
# ---------------------------
mask = pd.Series(True, index=df.index)

# Cursos
if cursos_filtrados:
    mask &= df['CURSO_NORMALIZADO'].isin(cursos_filtrados)

# Años (df['AÑO'] es Int64)
if len(anios_seleccionados) > 0:
    mask &= df['AÑO'].fillna(-1).astype('Int64').isin(anios_seleccionados)

# Cantones
if cantones_seleccionados:
    mask &= df['CANTON_DEF'].isin(cantones_seleccionados)

# Flags (OR entre seleccionadas)
if select_all_flags:
    # no filtramos por flags
    pass
else:
    mask_flag = pd.Series(False, index=df.index)
    if cert_flags['CERTIFICADO']:
        mask_flag |= (df['CERTIFICADO'] == 1)
    if cert_flags['DESERCION']:
        mask_flag |= (df['DESERCION'] == 1)
    if cert_flags['INTERMITENTE']:
        mask_flag |= (df['INTERMITENTE'] == 1)
    mask &= mask_flag

# Edades
if edades_seleccionadas:
    mask &= df['EDAD_CLASIFICADA'].isin(edades_seleccionadas)

# Sexos
if sexos_seleccionados:
    mask &= df['SEXO_NORMALIZADO'].isin(sexos_seleccionados)

df_filtrado = df[mask].copy()

# ===========================
# Preparar datos resumidos para mapa y tablas
# ===========================
def preparar_datos_resumen(df_local):
    df_local['CANTON_DEF'] = df_local['CANTON_DEF'].fillna('Sin dato')
    df_cantonal = df_local.groupby('CANTON_DEF').size().reset_index(name='cantidad_beneficiarios')
    df_detalle = df_local.groupby(['CANTON_DEF', 'CURSO_NORMALIZADO', 'AÑO']).size().reset_index(name='conteo')
    return df_cantonal, df_detalle

df_cantonal, df_detalle = preparar_datos_resumen(df_filtrado)

# Merge con geojson (preservando geometrías)
# Hacemos un merge que mantenga todos los polígonos del geojson para mostrarlos aunque no tengan datos
gdf_merged = gdf.merge(df_cantonal, how="left", left_on=columna_mapa, right_on="CANTON_DEF")
gdf_merged['cantidad_beneficiarios'] = gdf_merged['cantidad_beneficiarios'].fillna(0).astype(int)
gdf_merged['cantidad_color'] = gdf_merged['cantidad_beneficiarios']  # nombre claro para style_function

# ===========================
# Mapa (usando un solo GeoJson con style_function — mucho más rápido)
# ===========================
st.subheader("🗺️ Mapa Interactivo")

# Escala y colores
max_beneficiarios = int(gdf_merged['cantidad_color'].max() or 0)
if max_beneficiarios < 10:
    max_beneficiarios = 10

color_cero = '#ece7f2'
color_no_seleccionado = '#D3D3D3'
colores_escala = ['#a6bddb', '#74a9cf', '#3690c0', '#0570b0', '#034e7b']

try:
    pasos = np.logspace(start=0, stop=np.log10(max_beneficiarios), num=6)
    pasos = [int(round(p)) for p in pasos]
    pasos = sorted(list(set(pasos)))
    num_colores_necesarios = max(1, len(pasos) - 1)
    colores_escala = colores_escala[:num_colores_necesarios]
except Exception:
    pasos = [1, 10]
    colores_escala = [colores_escala[0]]

colormap = cm.StepColormap(colors=colores_escala, index=pasos, vmin=1, vmax=max_beneficiarios, caption='Cantidad de Beneficiarios')

m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

# style_function que pinta según properties['cantidad_color'] y atenúa si cantón no seleccionado
def estilo_feature(feature):
    props = feature.get('properties', {})
    canton = props.get(columna_mapa, "")
    cantidad = int(props.get('cantidad_color', 0) or 0)
    if canton not in cantones_seleccionados:
        return {
            'fillColor': color_no_seleccionado,
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.25
        }
    if cantidad == 0:
        return {
            'fillColor': color_cero,
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.7
        }
    return {
        'fillColor': colormap(cantidad),
        'color': 'black',
        'weight': 1,
        'fillOpacity': 0.7
    }

# Tooltip simple con nombre y cantidad
tooltip = folium.GeoJsonTooltip(fields=[columna_mapa, 'cantidad_color'],
                               aliases=['Cantón', 'Beneficiarios'],
                               localize=True)

folium.GeoJson(
    data=gdf_merged.__geo_interface__,
    style_function=lambda feature: estilo_feature(feature),
    tooltip=tooltip,
    name='Cantones'
).add_to(m)

m.add_child(colormap)
st_folium(m, width=900, height=600, returned_objects=[])

# ===========================
# Detalle "Sin dato" y detalle por cantón
# ===========================
df_sin_dato = df_filtrado[df_filtrado['CANTON_DEF'].fillna('Sin dato') == "Sin dato"]
total_sin_dato = len(df_sin_dato)
if total_sin_dato > 0:
    with st.expander(f"ℹ️ Observaciones 'Sin dato' (fuera del mapa): {total_sin_dato} personas"):
        detalles_sin_dato = df_detalle[df_detalle['CANTON_DEF'] == "Sin dato"]
        if detalles_sin_dato.empty:
            st.write("No se encontró detalle para las observaciones 'Sin dato'.")
        else:
            st.markdown("<strong>Detalle por curso y año:</strong>", unsafe_allow_html=True)
            detalle_html = "<ul>"
            for _, d in detalles_sin_dato.iterrows():
                curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
                detalle_html += f"<li>{curso} ({int(d['AÑO']) if not pd.isna(d['AÑO']) else 'ND'}): {d['conteo']} personas</li>"
            detalle_html += "</ul>"
            st.markdown(detalle_html, unsafe_allow_html=True)

# ===========================
# Estadísticas descriptivas
# ===========================
st.subheader("📊 Estadísticas Descriptivas")

# Resumen por Curso
st.subheader("Resumen por Curso")
if df_filtrado.empty:
    st.info("No hay datos con los filtros seleccionados.")
else:
    resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
    resumen_curso['Total'] = resumen_curso.sum(axis=1)
    resumen_curso['% Certificado'] = (resumen_curso.get(1, 0) / resumen_curso['Total']).replace([np.inf, -np.inf], 0).fillna(0) * 100
    resumen_curso = resumen_curso.rename(index=nombre_amigable)
    st.dataframe(resumen_curso)

# Resumen por Cantón
st.subheader("Resumen por Cantón")
resumen_canton = df_filtrado.groupby(['CANTON_DEF', 'CERTIFICADO']).size().unstack(fill_value=0)
resumen_canton['Total'] = resumen_canton.sum(axis=1)
resumen_canton['% Certificado'] = (resumen_canton.get(1, 0) / resumen_canton['Total']).replace([np.inf, -np.inf], 0).fillna(0) * 100
st.dataframe(resumen_canton)

# Gráfico de línea por año
st.subheader("Gráfico de Línea por Año")
if not df_filtrado.empty:
    df_anual = df_filtrado.groupby(['AÑO', 'CERTIFICADO']).size().unstack(fill_value=0)
    df_anual['Total'] = df_anual.sum(axis=1)
    df_anual['% Certificado'] = (df_anual.get(1, 0) / df_anual['Total']).replace([np.inf, -np.inf], 0).fillna(0) * 100
    df_anual = df_anual.sort_index()
    fig_linea = px.line(df_anual.reset_index(), x='AÑO', y='% Certificado',
                        title='Evolución de la Participación y Aprobación por Año',
                        labels={'AÑO': 'Año', '% Certificado': '% Certificado'})
    st.plotly_chart(fig_linea, use_container_width=True)
else:
    st.info("No hay datos para graficar por año con los filtros actuales.")

# ===========================
# Descargas
# ===========================
st.subheader("📥 Descargar Datos Filtrados")

def convertir_a_excel(df_to_save):
    import io
    from pandas import ExcelWriter
    output = io.BytesIO()
    with ExcelWriter(output, engine='xlsxwriter') as writer:
        df_to_save.to_excel(writer, index=False, sheet_name='DatosFiltrados')
    return output.getvalue()

archivo_excel = convertir_a_excel(df_filtrado)
st.download_button(label="📥 Descargar datos filtrados en Excel",
                   data=archivo_excel,
                   file_name='datos_filtrados.xlsx',
                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

st.subheader("📥 Descargar Datos Colapsados (por Cantón - Curso - Año)")
activar_colapsado = st.checkbox("Quiero descargar los datos colapsados por Cantón - Curso - Año")
if activar_colapsado:
    if df_filtrado.empty:
        st.warning("No hay datos para colapsar con los filtros actuales.")
    else:
        df_temp = df_filtrado.copy()
        df_temp['CURSO_AÑO'] = df_temp['CURSO_NORMALIZADO'].map(nombre_amigable).fillna(df_temp['CURSO_NORMALIZADO'].str.title()) + " " + df_temp['AÑO'].astype(str)
        df_pivot = df_temp.pivot_table(index='CANTON_DEF', columns='CURSO_AÑO', values='CERTIFICADO', aggfunc='count', fill_value=0).reset_index()
        df_pivot['TOTAL'] = df_pivot.drop(columns='CANTON_DEF').sum(axis=1)
        columnas_ordenadas = ['CANTON_DEF'] + sorted([c for c in df_pivot.columns if c not in ['CANTON_DEF', 'TOTAL']]) + ['TOTAL']
        df_pivot = df_pivot[columnas_ordenadas]
        archivo_excel_colapsado = convertir_a_excel(df_pivot)
        st.download_button(label="📥 Descargar datos colapsados en Excel",
                           data=archivo_excel_colapsado,
                           file_name='datos_colapsados.xlsx',
                           mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
