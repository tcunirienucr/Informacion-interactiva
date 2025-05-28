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
df = conn.read(worksheet="mapa_v1", ttl=120) # Ajusta usecols y ttl según tus necesidades

#Nombres amigables de los cantones
# Diccionario para mostrar nombres amigables
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

# Lista de cursos únicos en los datos, normalizados

# Filtros por curso y año

#Cursos

# Lista de cursos únicos en los datos, normalizados
cursos_unicos = df["CURSO"].str.lower().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
cursos_unicos = cursos_unicos.replace(nombre_amigable).unique()
cursos_unicos_amigables = sorted(set(nombre_amigable[c] for c in cursos_unicos if c in nombre_amigable))

opciones_display = ["Todos"] + cursos_unicos_amigables
seleccionados = st.multiselect("Selecciona cursos", opciones_display, default=["Todos"])

# Manejar selección
if "Todos" in seleccionados:
    cursos_filtrados = [k for k, v in nombre_amigable.items()]
else:
    cursos_filtrados = [k for k, v in nombre_amigable.items() if v in seleccionados]

#Años
anios_disponibles = sorted(df['AÑO'].dropna().unique())
anios_seleccionados = st.sidebar.multiselect("Selecciona años", anios_disponibles, default=anios_disponibles)

# Validaciones para evitar filtros vacíos
if not cursos_filtrados:
    st.error("Debe seleccionar al menos un curso.")
    st.stop()
if not anios_seleccionados:
    st.error("Debe seleccionar al menos un año.")
    st.stop()

# Filtrar el dataframe original
df_filtrado = df[(df['CURSO'].str.lower().isin(cursos_filtrados)) & (df['AÑO'].isin(anios_seleccionados))]

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
