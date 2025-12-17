import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import json
import datetime

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Integrated Evac Monitor", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATA LOADING FUNCTION ---
@st.cache_data
def load_data():
    try:
        # ==========================================
        # SOURCE 1: GEOJSON (Live Map)
        # ==========================================
        geo_path = 'ph_evacs_cleaned.geojson'
        with open(geo_path, 'r') as f:
            geo_data = json.load(f)
        
        geo_rows = []
        for feature in geo_data['features']:
            props = feature['properties']
            geom = feature['geometry']
            
            # 1. Geometry Engine
            lon, lat = None, None
            if geom['type'] == 'Point': lon, lat = geom['coordinates']
            elif geom['type'] == 'Polygon':
                coords = np.array(geom['coordinates'][0])
                lon, lat = coords[:, 0].mean(), coords[:, 1].mean()
            elif geom['type'] == 'MultiPolygon':
                coords = np.array(geom['coordinates'][0][0])
                lon, lat = coords[:, 0].mean(), coords[:, 1].mean()

            # 2. Capacity Logic
            raw_cap = props.get('capacity')
            real_cap = 100 
            if raw_cap:
                if str(raw_cap).isdigit(): real_cap = int(raw_cap)
                elif '-' in str(raw_cap):
                    try: real_cap = (int(raw_cap.split('-')[0]) + int(raw_cap.split('-')[1])) // 2
                    except: pass
                elif '>500' in str(raw_cap): real_cap = 600

            # 3. Simulate Live Occupancy
            occ = np.random.randint(0, int(real_cap * 1.5)) 
            
            # --- DUAL STATUS LOGIC (THE MERGE) ---
            # Status A: Logistics (Capacity)
            cap_status = "Available"
            if occ > real_cap: cap_status = "Overcrowded (>100%)"
            elif occ >= (real_cap * 0.8): cap_status = "Near Full (80-99%)"
            else: cap_status = "Available (<80%)"
            
            # Status B: Health (Risk Assessment)
            # Overcrowding = High Transmission Risk
            health_risk = "Low Risk"
            if occ > real_cap: health_risk = "CRITICAL: High Infection Risk"
            elif occ >= (real_cap * 0.8): health_risk = "WARNING: Elevated Density"
            else: health_risk = "SAFE: Social Distancing Possible"

            # 4. Estimated Date
            days_ago = np.random.randint(0, 3) 
            date_upd = datetime.date.today() - datetime.timedelta(days=days_ago)
            
            geo_rows.append({
                'Center_Name': props.get('name') or "Unnamed Facility",
                'Type': props.get('type') or "Unknown",
                'Province': props.get('province') or "Unspecified",
                'Capacity': real_cap,
                'Current_Evacuees': occ,
                'Capacity_Status': cap_status,   # For Logicstics View
                'Health_Risk': health_risk,      # For Health View
                'Last_Sensor_Ping': date_upd,
                'lat': lat,
                'lon': lon,
                'Source': 'GeoJSON'
            })
            
        df_geo = pd.DataFrame(geo_rows)
        df_geo = df_geo.dropna(subset=['lat', 'lon'])
        df_geo = df_geo.sort_values(by="Province")

        # ==========================================
        # SOURCE 2: EXCEL (Admin Registry)
        # ==========================================
        excel_path = 'evaccenter.xlsx'
        df_excel = pd.read_excel(excel_path, sheet_name=0)
        
        if 'Number of Evacuation Center' in df_excel.columns:
            df_excel = df_excel.rename(columns={'Number of Evacuation Center': 'Official_Count'})

        random_days = np.random.randint(0, 90, size=len(df_excel))
        df_excel['Last_Audit'] = [
            (datetime.date.today() - datetime.timedelta(days=int(d))) for d in random_days
        ]

        return df_geo, df_excel

    except Exception as e:
        st.error(f"Critical Data Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Load Data
df_geo, df_admin = load_data()

# --- SIDEBAR: VIEW SWITCHER (THE MERGE CONTROL) ---
st.sidebar.header("🎛️ Dashboard Controls")

# 1. VIEW MODE
view_mode = st.sidebar.radio(
    "Select Monitor Mode:",
    ["📦 Capacity & Logistics", "🏥 Health Risk Assessment"]
)

st.sidebar.markdown("---")
st.sidebar.header("🔍 Filters")

# 2. Province Filter
provinces = ["All"] + sorted(df_geo["Province"].unique().tolist())
selected_prov = st.sidebar.selectbox("Select Province:", provinces)

# 3. Type Filter
if selected_prov != "All":
    filtered_types = sorted(df_geo[df_geo["Province"] == selected_prov]["Type"].unique())
    df_filtered = df_geo[df_geo["Province"] == selected_prov]
else:
    filtered_types = sorted(df_geo["Type"].unique())
    df_filtered = df_geo

selected_type = st.sidebar.multiselect("Facility Type:", options=filtered_types, default=filtered_types)

if selected_type:
    df_selection = df_filtered[df_filtered["Type"].isin(selected_type)]
else:
    df_selection = df_filtered

# --- MAIN HEADER ---
st.title("🇵🇭 Integrated Evacuation Center & Health Monitor")
if view_mode == "📦 Capacity & Logistics":
    st.markdown(f"**Logistics View:** Monitoring space availability in **{len(df_selection):,}** facilities.")
else:
    st.markdown(f"**Health View:** Assessing disease transmission risk due to overcrowding in **{len(df_selection):,}** facilities.")

st.markdown("---")

# --- DYNAMIC CONFIGURATION BASED ON MODE ---
if view_mode == "📦 Capacity & Logistics":
    # CONFIG FOR CAPACITY
    map_color_col = "Capacity_Status"
    map_colors = {
        "Overcrowded (>100%)": "#FF0000",   # Red
        "Near Full (80-99%)": "#FFA500",    # Orange
        "Available (<80%)": "#008000"       # Green
    }
    chart_metric = "Capacity_Status"
    
else:
    # CONFIG FOR HEALTH RISK
    map_color_col = "Health_Risk"
    map_colors = {
        "CRITICAL: High Infection Risk": "#800080", # Purple (Biohazard feel)
        "WARNING: Elevated Density": "#FF4500",     # Orange-Red
        "SAFE: Social Distancing Possible": "#00BFFF" # Blue (Safe/Clean)
    }
    chart_metric = "Health_Risk"

# --- ROW 1: METRICS ---
total_cap = df_selection["Capacity"].sum()
total_evac = df_selection["Current_Evacuees"].sum()
occupancy_rate = (total_evac / total_cap * 100) if total_cap > 0 else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Sites", f"{len(df_selection):,}")
c2.metric("Total Capacity", f"{total_cap:,}")
c3.metric("Current Evacuees", f"{total_evac:,}")

# Metric Color Logic
if view_mode == "📦 Capacity & Logistics":
    delta_msg = "Utilization Rate"
    delta_col = "inverse" if occupancy_rate > 100 else "normal"
else:
    delta_msg = "Crowding Factor"
    delta_col = "inverse" if occupancy_rate > 80 else "normal" # Stricter for health

c4.metric("Avg Occupancy", f"{occupancy_rate:.1f}%", delta=delta_msg, delta_color=delta_col)

st.markdown("---")

# --- ROW 2: DYNAMIC MAP ---
st.subheader(f"📍 {view_mode} Map")

if not df_selection.empty:
    center_lat = df_selection["lat"].mean()
    center_lon = df_selection["lon"].mean()
    zoom_level = 5 if selected_prov == "All" else 9
else:
    center_lat, center_lon, zoom_level = 12.8, 121.7, 5

fig_map = px.scatter_mapbox(
    df_selection,
    lat="lat",
    lon="lon",
    color=map_color_col, # Dynamic Column
    size="Capacity",
    hover_name="Center_Name",
    hover_data={"Province": True, "Type": True, "Current_Evacuees": True, "lat": False, "lon": False},
    color_discrete_map=map_colors, # Dynamic Colors
    zoom=zoom_level,
    center={"lat": center_lat, "lon": center_lon},
    mapbox_style="open-street-map",
    height=500
)
st.plotly_chart(fig_map, use_container_width=True)

# --- ROW 3: CHARTS ---
c5, c6 = st.columns(2)

with c5:
    st.subheader("📊 Occupancy Levels by Type")
    type_data = df_selection.groupby("Type")[["Capacity", "Current_Evacuees"]].sum().reset_index()
    fig_bar = px.bar(type_data, x="Type", y=["Capacity", "Current_Evacuees"], 
                     barmode="overlay", title="Space vs. Demand")
    st.plotly_chart(fig_bar, use_container_width=True)

with c6:
    st.subheader(f"⚠️ {chart_metric} Distribution")
    fig_pie = px.pie(df_selection, names=chart_metric, hole=0.4, 
                     color=chart_metric,
                     color_discrete_map=map_colors)
    st.plotly_chart(fig_pie, use_container_width=True)

# --- ROW 4: DATA TABS ---
st.subheader("💾 Master Records")
tab1, tab2 = st.tabs(["🌍 Live Sensor Data (GeoJSON)", "📑 LGU Registry (Excel)"])

with tab1:
    st.markdown("**Source:** `ph_evacs_cleaned.geojson` | **Update Frequency:** Real-time (Simulated)")
    # Show different columns based on mode
    common_cols = ['Center_Name', 'Province', 'Type', 'Current_Evacuees', 'Capacity']
    mode_col = [map_color_col] # Shows either Capacity_Status or Health_Risk
    st.dataframe(df_selection[common_cols + mode_col + ['Last_Sensor_Ping']], use_container_width=True)

with tab2:
    st.markdown("**Source:** `evaccenter.xlsx` | **Update Frequency:** Quarterly Audit")
    if not df_admin.empty:
        cols_audit = ["Municipality_City", "Province", "Region", "Official_Count", "Last_Audit"]
        valid_cols = [c for c in cols_audit if c in df_admin.columns]
        st.dataframe(df_admin[valid_cols], use_container_width=True, hide_index=True)

# --- SIDEBAR FOOTER ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📚 Attribution")
st.sidebar.info(
    "**1. Geospatial Data:** [Kaggle/OSM](https://www.kaggle.com/datasets/louislemsic/philippine-evacuation-centers-dataset)"
)
st.sidebar.caption("Note: Github link in Kaggle page for GeoJSON file. \nhttps://github.com/louislemsic/ph-evac-centers/tree/main/src/data")
st.sidebar.info(
    "**2. Admin Data (Excel):**\n"
    "[DILG Pre-Disaster Indicators](https://data.humdata.org/dataset/philippines-pre-disaster-indicators)"
)
st.sidebar.caption("Note: Scroll down until Data and Resource: 9th xlsx file.")
st.sidebar.caption("Note: Occupancy metrics are simulated for academic prototyping.")
st.sidebar.text("Created by: VIZCARRA, CHARLES JUSTIN R.")
st.sidebar.text("Section: BSIT-3A")