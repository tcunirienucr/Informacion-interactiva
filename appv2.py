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
            # casos especiales que tenías
            elif v == 98 or v == 102 or v == 109:
                return "19 a 35"
            elif v == 99 or v == 105 or v == 106:
                return "36 a 64"
            elif v == 103:
                return "30 a 39"
            else:
                return 'Sin dato'
        v = str(valor).strip()
        if v == '' or v.lower() == 'información incompleta':
            return 'Sin dato'
        # correspondencias en texto
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
    # normalizar minúsculas para comparación
    low = v.lower()
    if low in ['femenino', 'f', 'mujer', 'female']:
        return 'Femenino'
    if low in ['masculino', 'm', 'hombre', 'male']:
        return 'Masculino'
    if low in ['no indica', 'no responde', 'no contesta', 'nr', 'sin dato', 'ns']:
        return 'NR' if low in ['no indica', 'no responde', 'no contesta', 'nr'] else 'Sin dato'
    # Otros valores los marcamos como 'Sin dato' para que no influyan
    return 'Sin dato'

def strip_accents(s: str) -> str:
    return unicodedata.normalize('NFKD', s).encode('ascii', errors='ignore').decode('utf-8') if isinstance(s, str) else s

def safe_get_column(df, candidates):
    """
    Busca la primera columna disponible en df entre candidates y devuelve su nombre.
    """
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
# Cargar datos (cacheados)
# ---------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    df = conn.read(worksheet="mapa_más_reciente")

    # Asegurar tipos y columnas mínimas
    # Normalizar CURSO sin romper si es NaN
    df['CURSO'] = df.get('CURSO', '').fillna('').astype(str)
    df['CURSO_NORMALIZADO'] = df['CURSO'].str.lower().apply(strip_accents).str.strip()

    # AÑO: convertir a entero (si no se puede -> NaN)
    df['AÑO'] = pd.to_numeric(df.get('AÑO'), errors='coerce').astype('Int64')

    # CERTIFICADO / DESERCION / INTERMITENTE -> convertir a enteros (0/1)
    for col in ['CERTIFICADO', 'DESERCION', 'INTERMITENTE']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        else:
            df[col] = 0

    # Normalizar CANTON_DEF si existe, y crear si no
    if 'CANTON_DEF' not in df.columns:
        # intentar otras columnas típicas
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

# Cargar
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
# Sidebar: filtros con "Seleccionar todos?"
# ---------------------------
with st.sidebar:
    st.title("Filtros Globales")

    # -- Cursos --
    select_all_cursos = st.checkbox("¿Seleccionar todos los cursos?", value=True)
    cursos_disponibles_raw = sorted(df['CURSO_NORMALIZADO'].dropna().unique())
    # Mapear a nombres amigables donde aplique (para mostrar)
    cursos_display = [nombre_amigable.get(c, c.title()) for c in cursos_disponibles_raw]
    if not select_all_cursos:
        seleccion_cursos_display = st.multiselect("Cursos", cursos_display, default=cursos_display[:3])
        # convertir selección visible a valores normalizados (clave de nombre_amigable o el propio normalized)
        cursos_filtrados = []
        for key, friendly in nombre_amigable.items():
            if friendly in seleccion_cursos_display:
                cursos_filtrados.append(key)
        # añadir aquellas seleccionadas que no están en nombre_amigable (comparación por title)
        for raw, disp in zip(cursos_disponibles_raw, cursos_display):
            if disp in seleccion_cursos_display and raw not in cursos_filtrados:
                cursos_filtrados.append(raw)
    else:
        cursos_filtrados = list(cursos_disponibles_raw)

    # -- Años --
    select_all_anios = st.checkbox("¿Seleccionar todos los años?", value=True)
    anios_disponibles = sorted([int(i) for i in df['AÑO'].dropna().unique()])  # convertidos a ints para mostrar
    if not select_all_anios:
        seleccion_anios = st.multiselect("Años", anios_disponibles, default=anios_disponibles)
        anios_seleccionados = seleccion_anios
    else:
        anios_seleccionados = anios_disponibles

    # -- Cantones --
    select_all_cantones = st.checkbox("¿Seleccionar todos los cantones?", value=True)
    cantones_disponibles = sorted(gdf[columna_mapa].dropna().unique())
    if not select_all_cantones:
        seleccion_cantones = st.multiselect("Cantones", cantones_disponibles, default=cantones_disponibles[:5])
        cantones_seleccionados = seleccion_cantones
    else:
        cantones_seleccionados = list(cantones_disponibles)

    # -- Certificados: nuevo enfoque con banderas --
    st.divider()
    st.markdown("**Filtrar por estado (elige 1 o más)**")
    select_all_flags = st.checkbox("¿Seleccionar todos los estados (CERTIFICADO / DESERCION / INTERMITENTE)?", value=True)
    if select_all_flags:
        # si seleccionamos todo, tomamos todo (no requerimos filtro)
        filter_por_flags = False
        certificados_seleccionados_flags = {'CERTIFICADO': True, 'DESERCION': True, 'INTERMITENTE': True}
    else:
        filter_por_flags = True
        certificados_seleccionados_flags = {
            'CERTIFICADO': st.checkbox("CERTIFICADO == 1", value=True),
            'DESERCION': st.checkbox("DESERCION == 1", value=False),
            'INTERMITENTE': st.checkbox("INTERMITENTE == 1", value=False)
        }

    # -- Grupo de edad --
    st.divider()
    select_all_edades = st.checkbox("¿Seleccionar todos los grupos de edad?", value=True)
    edades_disponibles = sorted(df['EDAD_CLASIFICADA'].dropna().unique())
    if not select_all_edades:
        seleccion_edades = st.multiselect("Grupo de Edad", edades_disponibles, default=edades_disponibles)
        edades_seleccionadas = seleccion_edades
    else:
        edades_seleccionadas = list(edades_disponibles)

    # -- Sexo --
    select_all_sexos = st.checkbox("¿Seleccionar todos los sexos?", value=True)
    sexos_disponibles = sorted(df['SEXO_NORMALIZADO'].dropna().unique())
    if not select_all_sexos:
        seleccion_sexos = st.multiselect("Sexo", sexos_disponibles, default=sexos_disponibles)
        sexos_seleccionados = seleccion_sexos
    else:
        sexos_seleccionados = list(sexos_disponibles)

# ---------------------------
# Filtrado principal (aplicar una sola vez)
# ---------------------------
# CURSO_NORMALIZADO already normalized
mask = pd.Series(True, index=df.index)

# Cursos
if cursos_filtrados:
    mask &= df['CURSO_NORMALIZADO'].isin(cursos_filtrados)
# Años
if len(anios_seleccionados) > 0:
    # df['AÑO'] es Int64; comparar ints
    mask &= df['AÑO'].fillna(-1).astype('Int64').isin(anios_seleccionados)
# Cantones
if cantones_seleccionados:
    mask &= df['CANTON_DEF'].isin(cantones_seleccionados)
# Certificados/desercion/intermitente: OR entre seleccionadas
if filter_por_flags:
    mask_flag = pd.Series(False, index=df.index)
    if certificados_seleccionados_flags['CERTIFICADO']:
        mask_flag |= df['CERTIFICADO'] == 1
    if certificados_seleccionados_flags['DESERCION']:
        mask_flag |= df['DESERCION'] == 1
    if certificados_seleccionados_flags['INTERMITENTE']:
        mask_flag |= df['INTERMITENTE'] == 1
    mask &= mask_flag
# Edades
if edades_seleccionadas:
    mask &= df['EDAD_CLASIFICADA'].isin(edades_seleccionadas)
# Sexos
if sexos_seleccionados:
    mask &= df['SEXO_NORMALIZADO'].isin(sexos_seleccionados)

df_filtrado = df[mask].copy()

# ---------------------------
# Preparar datos para mapa (no cacheado: más estable)
# ---------------------------
def preparar_datos_mapa(df_filtrado_local, gdf_local):
    # agrupar por cantón
    df_filtrado_local['CANTON_DEF'] = df_filtrado_local['CANTON_DEF'].fillna('Sin dato')
    df_cantonal = df_filtrado_local.groupby('CANTON_DEF').size().reset_index(name='cantidad_beneficiarios')
    df_detalle = df_filtrado_local.groupby(['CANTON_DEF', 'CURSO_NORMALIZADO', 'AÑO']).size().reset_index(name='conteo')
    # hacer merge con geojson (solo cantones presentes en geojson mantendrán geometría)
    gdf_merged = gdf_local.merge(df_cantonal, how="left", left_on=columna_mapa, right_on="CANTON_DEF")
    gdf_merged['cantidad_color'] = gdf_merged['cantidad_beneficiarios'].fillna(0).astype(int)
    return gdf_merged, df_detalle

gdf_merged, df_detalle = preparar_datos_mapa(df_filtrado, gdf)

# ---------------------------
# Mapa interactivo
# ---------------------------
st.subheader("🗺️ Mapa Interactivo")
m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

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

colormap = cm.StepColormap(colors=colores_escala, index=pasos, vmin=1, vmax=max_beneficiarios, caption='Cantidad de Beneficiarios (Escala por pasos)')

for _, row in gdf_merged.iterrows():
    canton = row.get(columna_mapa, "Sin nombre")
    cantidad_real_popup = row.get('cantidad_beneficiarios', np.nan)
    cantidad_para_color = int(row.get('cantidad_color', 0))

    if canton not in cantones_seleccionados:
        color = color_no_seleccionado
        fill_opacity = 0.3
    elif cantidad_para_color == 0:
        color = color_cero
        fill_opacity = 0.7
    else:
        color = colormap(cantidad_para_color)
        fill_opacity = 0.7

    detalles = df_detalle[df_detalle['CANTON_DEF'] == canton]
    if detalles.empty:
        detalle_html = "<i>0 beneficiarios (según filtros)</i>" if canton in cantones_seleccionados else "<i>Cantón no seleccionado</i>"
    else:
        detalle_html = "<ul>"
        for _, d in detalles.iterrows():
            curso_nombre = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
            detalle_html += f"<li>{curso_nombre} ({int(d['AÑO']) if not pd.isna(d['AÑO']) else 'ND'}): {d['conteo']} personas</li>"
        detalle_html += "</ul>"

    popup_html = f"""
        <strong>Cantón:</strong> {canton}<br>
        <strong>Total de beneficiarios:</strong> {int(cantidad_real_popup) if not pd.isnull(cantidad_real_popup) else 0}<br>
        <strong>Detalle:</strong> {detalle_html}
    """

    try:
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
    except Exception:
        # Evitar que un polígono corrupto haga colapsar todo el mapa
        continue

m.add_child(colormap)
st_folium(m, width=900, height=600, returned_objects=[])

# ---------------------------
# Observaciones "Sin dato" (fuera del mapa)
# ---------------------------
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

# ---------------------------
# Estadísticas descriptivas
# ---------------------------
st.subheader("📊 Estadísticas Descriptivas")

# Resumen por Curso
st.subheader("Resumen por Curso")
if df_filtrado.empty:
    st.info("No hay datos con los filtros seleccionados.")
else:
    resumen_curso = df_filtrado.groupby(['CURSO_NORMALIZADO', 'CERTIFICADO']).size().unstack(fill_value=0)
    if 1 in resumen_curso.columns:
        resumen_curso['Total'] = resumen_curso.sum(axis=1)
        resumen_curso['% Certificado'] = (resumen_curso.get(1, 0) / resumen_curso['Total']) * 100
    else:
        resumen_curso['Total'] = resumen_curso.sum(axis=1)
        resumen_curso['% Certificado'] = 0.0
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
    # ordenar por año (index puede ser Int64)
    df_anual = df_anual.sort_index()
    fig_linea = px.line(df_anual.reset_index(), x='AÑO', y='% Certificado',
                        title='Evolución de la Participación y Aprobación por Año',
                        labels={'AÑO': 'Año', '% Certificado': '% Certificado'})
    st.plotly_chart(fig_linea, use_container_width=True)
else:
    st.info("No hay datos para graficar por año con los filtros actuales.")

# ---------------------------
# Descargas
# ---------------------------
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
