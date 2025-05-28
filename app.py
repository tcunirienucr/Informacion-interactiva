import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
import io

# Título de la app
st.title("📊 Mapa y Estadísticas de Mortalidad Materna en Costa Rica")

# Cargar datos con caché
@st.cache_data
def cargar_geojson():
    return gpd.read_file("costaricacantonesv10.geojson")

@st.cache_data
def cargar_excel():
    return pd.read_excel("df_merge.xlsx")

# Cargar datasets
try:
    gdf = cargar_geojson()
    df = cargar_excel()
except Exception as e:
    st.error(f"Ocurrió un error cargando los archivos: {e}")
    st.stop()

# Filtrar años desde 2017
df = df[df['year'] >= 2017]

# Sidebar para filtros
st.sidebar.title("Filtros 📌")

# Selección de año para el mapa
anios_disponibles = sorted(df['year'].unique())
anio_seleccionado = st.sidebar.selectbox("Selecciona un año para el mapa", anios_disponibles)

# Selección de cantones y años para estadísticas
cantones_disponibles = sorted(df['canton'].unique())
cantones_seleccionados = st.sidebar.multiselect("Selecciona cantones", cantones_disponibles, default=cantones_disponibles[:5])
anios_seleccionados = st.sidebar.multiselect("Selecciona años", anios_disponibles, default=anios_disponibles)

# ===============================
# MAPA INTERACTIVO
# ===============================

st.subheader("🗺️ Mapa Interactivo")

df_filtrado = df[df['year'] == anio_seleccionado]
gdf_merged = gdf.merge(df_filtrado, how="left", left_on="NAME_2", right_on="canton")

# Crear mapa base
m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

# Función para colorear según tasa
def color_por_tasa(tasa):
    if pd.isnull(tasa):
        return 'gray'
    elif tasa == 0:
        return 'green'
    elif tasa < 20:
        return 'orange'
    else:
        return 'red'

# Añadir polígonos al mapa
for _, row in gdf_merged.iterrows():
    color = color_por_tasa(row['tasa_mortalidad_materna'])
    folium.GeoJson(
        row['geometry'],
        style_function=lambda feature, color=color: {
            'fillColor': color,
            'color': 'black',
            'weight': 1,
            'fillOpacity': 0.5
        },
        tooltip=folium.Tooltip(f"""
            <strong>Cantón:</strong> {row['NAME_2']}<br>
            <strong>Tasa Mortalidad Materna:</strong> {row['tasa_mortalidad_materna']}<br>
            <strong>Defunciones Maternas:</strong> {row['cantidad_defunciones_maternas']}
        """)
    ).add_to(m)

# Mostrar mapa
st_folium(m, width=800, height=600)

# Leyenda
st.markdown("""
**🟢 Tasa = 0**  
**🟠 Tasa entre 0 y 20**  
**🔴 Tasa mayor a 20**  
**⚪ Sin dato**
""")

# ===============================
# ESTADÍSTICA DESCRIPTIVA
# ===============================

st.subheader("📊 Estadística Descriptiva")

# Filtrar datos según selección
df_seleccion = df[(df['canton'].isin(cantones_seleccionados)) & (df['year'].isin(anios_seleccionados))]

# Mostrar tabla con valores absolutos
st.write("### 📋 Tabla de valores")
if not df_seleccion.empty:
    st.dataframe(df_seleccion[['year', 'canton', 'tasa_mortalidad_materna', 'cantidad_defunciones_maternas']].sort_values(['canton', 'year']))
else:
    st.write("No hay datos para la selección actual.")

# Resumen estadístico
st.write("### 📊 Resumen Estadístico")
if not df_seleccion.empty:
    resumen = df_seleccion[['tasa_mortalidad_materna', 'cantidad_defunciones_maternas']].describe()
    st.dataframe(resumen)
else:
    st.write("No hay datos para mostrar resumen.")

# Gráfico de líneas: Tasa Mortalidad Materna
st.write("### 📈 Serie: Tasa de Mortalidad Materna")
if not df_seleccion.empty:
    fig_tasa = px.line(df_seleccion, x='year', y='tasa_mortalidad_materna', color='canton',
                       markers=True, labels={'tasa_mortalidad_materna': 'Tasa'},
                       title='Tasa de Mortalidad Materna por Cantón y Año')
    st.plotly_chart(fig_tasa, use_container_width=True)
else:
    st.write("No hay datos para la selección actual.")

# Gráfico de líneas: Cantidad de Defunciones Maternas
st.write("### 📈 Serie: Cantidad de Defunciones Maternas")
if not df_seleccion.empty:
    fig_def = px.line(df_seleccion, x='year', y='cantidad_defunciones_maternas', color='canton',
                      markers=True, labels={'cantidad_defunciones_maternas': 'Defunciones'},
                      title='Defunciones Maternas por Cantón y Año')
    st.plotly_chart(fig_def, use_container_width=True)
else:
    st.write("No hay datos para la selección actual.")

# ===============================
# DESCARGA DE DATOS
# ===============================

st.write("### 📥 Descargar datos filtrados")
if not df_seleccion.empty:
    buffer = io.StringIO()
    df_seleccion.to_csv(buffer, index=False)
    st.download_button(
        label="📥 Descargar CSV",
        data=buffer.getvalue(),
        file_name="datos_filtrados.csv",
        mime="text/csv"
    )
else:
    st.write("No hay datos para descargar.")
