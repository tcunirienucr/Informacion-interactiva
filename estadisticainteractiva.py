import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
import io

#Establecer conexión con el Google Sheets
#Establecer la conexión con Google Sheets 
conn = st.connection("gsheets", type=GSheetsConnection) 
df = conn.read(worksheet="mapa_v1", usecols=list(range(18)), ttl=120) # Ajusta usecols y ttl según tus necesidades



# Título de la app
st.title("📊 Mapa y Estadísticas de las personas beneficiarias: TCU Nirien - Habilidades para la Vida - UCR")

# Cargar datos con caché
@st.cache_data
def cargar_geojson():
    return gpd.read_file("costaricacantonesv10.geojson")

# Cargar datasets
try:
    gdf = cargar_geojson()
except Exception as e:
    st.error(f"Ocurrió un error cargando los archivos: {e}")
    st.stop()

#FILTROS PARA EL MAPA
# Sidebar para filtros
st.sidebar.title("Filtros 📌")

# Filtros por curso y año
cursos_disponibles = sorted(df['CURSO'].dropna().unique())
cursos_seleccionados = st.sidebar.multiselect("Selecciona cursos", cursos_disponibles, default=cursos_disponibles)

anios_disponibles = sorted(df['AÑO'].dropna().unique())
anios_seleccionados = st.sidebar.multiselect("Selecciona años", anios_disponibles, default=anios_disponibles)

# Validaciones para evitar filtros vacíos
if not cursos_seleccionados:
    st.error("Debe seleccionar al menos un curso.")
    st.stop()
if not anios_seleccionados:
    st.error("Debe seleccionar al menos un año.")
    st.stop()

# Filtrar el dataframe original
df_filtrado = df[(df['CURSO'].isin(cursos_seleccionados)) & (df['AÑO'].isin(anios_seleccionados))]

# Agrupar por cantón y contar observaciones (beneficiarios)
df_cantonal = df_filtrado.groupby('CANTON_DEF').size().reset_index(name='cantidad_beneficiarios')

# Unir con el GeoDataFrame
gdf_merged = gdf.merge(df_cantonal, how="left", left_on="NAME_2", right_on="CANTON_DEF")

# ===============================
# MAPA INTERACTIVO
# ===============================

st.subheader("🗺️ Mapa Interactivo")

# Crear mapa base
m = folium.Map(location=[9.7489, -83.7534], zoom_start=8)

# Función para colorear según cantidad
def color_por_cantidad(cantidad):
    if pd.isnull(cantidad):
        return 'gray'
    elif cantidad == 0:
        return 'green'
    elif cantidad < 20:
        return 'orange'
    else:
        return 'red'

# Añadir polígonos al mapa
for _, row in gdf_merged.iterrows():
    color = color_por_cantidad(row['cantidad_beneficiarios'])
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
            <strong>Cantidad de Beneficiarios:</strong> {row['cantidad_beneficiarios']}
        """)
    ).add_to(m)

# Mostrar el mapa
st_folium(m, width=800, height=600)

#Leyendas para los códigos de color

st.markdown("""
**🟢 0 beneficiarios**  
**🟠 Menos de 20 beneficiarios**  
**🔴 20 o más beneficiarios**  
**⚪ Sin dato**
""")


# ===============================
# ESTADÍSTICA DESCRIPTIVA
# ===============================
