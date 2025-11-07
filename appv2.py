import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

ruta_mapa="limitecantonal_5k.geojson"
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
def cargar_datos():
    df = conn.read(worksheet="mapa_más_reciente")
    df["CURSO_NORMALIZADO"] = df["CURSO"].str.lower().str.normalize('NFKD') \
        .str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

df = cargar_datos()

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

# ===============================
# Sidebar - Filtros globales
# ===============================
with st.sidebar:
    st.title("Filtros Globales")

    # ===== Cursos =====
    cursos_disponibles = df["CURSO_NORMALIZADO"].unique()
    cursos_filtrables = sorted(set(c for c in cursos_disponibles if c in nombre_amigable))
    opciones_cursos = ["Todos"] + [nombre_amigable[c] for c in cursos_filtrables]

    seleccion_cursos = st.multiselect("Cursos", opciones_cursos, default=["Todos"])
    if "Todos" in seleccion_cursos:
        seleccion_cursos = ["Todos"]
    elif len(seleccion_cursos) > 1 and "Todos" in seleccion_cursos:
        seleccion_cursos.remove("Todos")

    if "Todos" in seleccion_cursos:
        cursos_filtrados = cursos_filtrables
    else:
        cursos_filtrados = [k for k, v in nombre_amigable.items() if v in seleccion_cursos]

    # ===== Años =====
    anios_disponibles = sorted(df['AÑO'].dropna().unique())
    opciones_anios = ["Todos"] + list(anios_disponibles)

    seleccion_anios = st.multiselect("Años", opciones_anios, default=["Todos"])
    if "Todos" in seleccion_anios:
        seleccion_anios = ["Todos"]
    elif len(seleccion_anios) > 1 and "Todos" in seleccion_anios:
        seleccion_anios.remove("Todos")

    if "Todos" in seleccion_anios:
        anios_seleccionados = anios_disponibles
    else:
        anios_seleccionados = seleccion_anios

    # ===== Cantones =====
# Usar los 84 cantones desde el geojson
    cantones_disponibles = sorted(gdf[columna_mapa].dropna().unique())
    opciones_cantones = ["Todos"] + list(cantones_disponibles)


    seleccion_cantones = st.multiselect("Cantones", opciones_cantones, default=["Todos"])
    if "Todos" in seleccion_cantones:
        seleccion_cantones = ["Todos"]
    elif len(seleccion_cantones) > 1 and "Todos" in seleccion_cantones:
        seleccion_cantones.remove("Todos")

    if "Todos" in seleccion_cantones:
        cantones_seleccionados = cantones_disponibles
    else:
        cantones_seleccionados = seleccion_cantones

    # ===== Certificados =====
    certificados_disponibles = sorted(df["CERTIFICADO"].dropna().unique())
    certificados_seleccionados = st.multiselect(
        "Certificado",
        certificados_disponibles,
        default=certificados_disponibles,
        help="1: Sí obtuvo certificado y concluyó el curso.\n0: No concluyó el curso, o lo concluyó sin certificarse."
    )



# ===============================
# Filtrar datos una sola vez
# ===============================
df_filtrado = df[
    df["CURSO_NORMALIZADO"].isin(cursos_filtrados) &
    df["AÑO"].isin(anios_seleccionados) &
    df["CANTON_DEF"].isin(cantones_seleccionados) &
    df["CERTIFICADO"].isin(certificados_seleccionados)
]

# ===============================
# Mapa interactivo con folium
# ===============================
st.subheader("🗺️ Mapa Interactivo")

@st.cache_data
def preparar_datos_mapa(df_filtrado, _gdf):
    df_cantonal = df_filtrado.groupby('CANTON_DEF').size().reset_index(name='cantidad_beneficiarios')
    df_detalle = df_filtrado.groupby(['CANTON_DEF', 'CURSO_NORMALIZADO', 'AÑO']).size().reset_index(name='conteo')
    gdf_merged = _gdf.merge(df_cantonal, how="left", left_on=columna_mapa, right_on="CANTON_DEF")
    return gdf_merged, df_detalle

# 👇 CAMBIAR AQUÍ TAMBIÉN
gdf_merged, df_detalle = preparar_datos_mapa(df_filtrado, gdf)


m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

def color_por_cantidad(canton, cantidad, cantones_seleccionados):
    if canton not in cantones_seleccionados:
        return 'gray'
    elif pd.isnull(cantidad) or cantidad == 0:
        return 'red'
    elif cantidad < 20:
        return 'orange'
    else:
        return 'green'


for _, row in gdf_merged.iterrows():
    canton = row[columna_mapa]
    cantidad = row['cantidad_beneficiarios']
    color = color_por_cantidad(canton, cantidad, cantones_seleccionados)

    detalles = df_detalle[df_detalle['CANTON_DEF'] == canton]
    if detalles.empty:
        detalle_html = "<i>Sin datos disponibles</i>"
    else:
        detalle_html = "<ul>"
        for _, d in detalles.iterrows():
            curso = nombre_amigable.get(d['CURSO_NORMALIZADO'], d['CURSO_NORMALIZADO'].title())
            detalle_html += f"<li>{curso} ({int(d['AÑO'])}): {d['conteo']} personas</li>"
        detalle_html += "</ul>"

    popup_html = f"""
        <strong>Cantón:</strong> {canton}<br>
        <strong>Total de beneficiarios:</strong> {cantidad if not pd.isnull(cantidad) else '0'}<br>
        <strong>Detalle:</strong> {detalle_html}
    """

    folium.GeoJson(
        row['geometry'],
        style_function=lambda feature, color=color: {
            'fillColor': color,
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.5
        },
        tooltip=folium.Tooltip(f"{canton}"),
        popup=folium.Popup(popup_html, max_width=300)
    ).add_to(m)

st_folium(m, width=800, height=600)

st.markdown("""
**🟢 20 o más beneficiarios**  
**🟠 Menos de 20 beneficiarios**  
**🔴 0 beneficiarios o sin dato**  
**⚪ Cantón no seleccionado**
""")



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
