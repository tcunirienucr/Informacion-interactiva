import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_gsheets import GSheetsConnection
import plotly.express as px

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
    df = conn.read(worksheet="mapa_v1")
    df["CURSO_NORMALIZADO"] = df["CURSO"].str.lower().str.normalize('NFKD') \
        .str.encode('ascii', errors='ignore').str.decode('utf-8')
    return df

df = cargar_datos()

# ===============================
# Cargar geojson con caché
# ===============================
@st.cache_data

def cargar_geojson():
    return gpd.read_file("costaricacantonesv10.geojson")

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

    cursos_disponibles = df["CURSO_NORMALIZADO"].unique()
    cursos_filtrables = sorted(set(c for c in cursos_disponibles if c in nombre_amigable))
    opciones_display = ["Todos"] + [nombre_amigable[c] for c in cursos_filtrables]

    seleccionados = st.multiselect("Cursos", opciones_display, default=["Todos"])
    if "Todos" in seleccionados:
        cursos_filtrados = cursos_filtrables
    else:
        cursos_filtrados = [k for k, v in nombre_amigable.items() if v in seleccionados]

    anios_disponibles = sorted(df['AÑO'].dropna().unique())
    anios_seleccionados = st.multiselect("Años", anios_disponibles, default=anios_disponibles)

    cantones_disponibles = df["CANTON_DEF"].dropna().unique()
    cantones_seleccionados = st.multiselect("Cantones", cantones_disponibles, default=cantones_disponibles)

    certificados_disponibles = df["CERTIFICADO"].dropna().unique()
    certificados_seleccionados = st.multiselect("Certificado", certificados_disponibles, default=certificados_disponibles)

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
    gdf_merged = _gdf.merge(df_cantonal, how="left", left_on="NAME_2", right_on="CANTON_DEF")
    return gdf_merged, df_detalle

# 👇 CAMBIAR AQUÍ TAMBIÉN
gdf_merged, df_detalle = preparar_datos_mapa(df_filtrado, gdf)


m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

def color_por_cantidad(cantidad):
    if pd.isnull(cantidad):
        return 'gray'
    elif cantidad == 0:
        return 'green'
    elif cantidad < 20:
        return 'orange'
    else:
        return 'red'

for _, row in gdf_merged.iterrows():
    canton = row['NAME_2']
    cantidad = row['cantidad_beneficiarios']
    color = color_por_cantidad(cantidad)

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
**🟢 0 beneficiarios**  
**🟠 Menos de 20 beneficiarios**  
**🔴 20 o más beneficiarios**  
**⚪ Sin dato**
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

# Gráfico de barras apiladas
st.subheader("Gráfico de Barras Apiladas por Curso y Certificado")
fig_barras = px.bar(df_filtrado, x='CURSO_NORMALIZADO', color='CERTIFICADO', barmode='stack', 
                    labels={'CURSO_NORMALIZADO': 'Curso', 'CERTIFICADO': 'Certificado'},
                    title='Cantidad de Personas por Curso y Certificado')
fig_barras.update_xaxes(tickangle=45)
st.plotly_chart(fig_barras)

# Gráfico de línea
st.subheader("Gráfico de Línea por Año")
df_anual = df_filtrado.groupby(['AÑO', 'CERTIFICADO']).size().unstack(fill_value=0)
df_anual['Total'] = df_anual.sum(axis=1)
df_anual['% Certificado'] = (df_anual[1] / df_anual['Total']) * 100
fig_linea = px.line(df_anual, x=df_anual.index, y='% Certificado', 
                    title='Evolución de la Participación y Aprobación por Año',
                    labels={'AÑO': 'Año', '% Certificado': '% Certificado'})
st.plotly_chart(fig_linea)
