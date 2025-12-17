import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import json
import datetime

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Health Risk Monitor", 
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

            # 3. Simulate Live Occupancy & Health Risk
            # Health Pivot: Overcrowding = High Disease Risk
            occ = np.random.randint(0, int(real_cap * 1.5)) # Allow severe overcrowding
            
            status = "Safe"
            if occ > real_cap:
                status = "High Health Risk (Overcrowded)"
            elif occ >= (real_cap * 0.8):
                status = "Warning (High Density)"
            else:
                status = "Optimal"

            # 4. Estimated Date (Last Sensor Ping)
            days_ago = np.random.randint(0, 3) # Frequent updates for Health monitoring
            date_upd = datetime.date.today() - datetime.timedelta(days=days_ago)
            
            geo_rows.append({
                'Center_Name': props.get('name') or "Unnamed Facility",
                'Type': props.get('type') or "Unknown",
                'Province': props.get('province') or "Unspecified",
                'Capacity': real_cap,
                'Current_Evacuees': occ,
                'Health_Status': status,
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

        # Estimated Verification Date (Quarterly Health Audit)
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

# --- SIDEBAR: MULTIPLE FILTERS (RUBRIC REQUIREMENT) ---
st.sidebar.header("🔍 Filter Dashboard")

# 1. Province Filter
provinces = ["All"] + sorted(df_geo["Province"].unique().tolist())
selected_prov = st.sidebar.selectbox("1. Select Province:", provinces)

# 2. Type Filter (Cascading - Updates based on Province)
if selected_prov != "All":
    filtered_types = sorted(df_geo[df_geo["Province"] == selected_prov]["Type"].unique())
    df_filtered = df_geo[df_geo["Province"] == selected_prov]
else:
    filtered_types = sorted(df_geo["Type"].unique())
    df_filtered = df_geo

selected_type = st.sidebar.multiselect("2. Facility Type:", options=filtered_types, default=filtered_types)

# Apply Type Filter
if selected_type:
    df_selection = df_filtered[df_filtered["Type"].isin(selected_type)]
else:
    df_selection = df_filtered

# --- MAIN HEADER (HEALTH INFORMATICS CONTEXT) ---
st.title("🏥 Health Risk & Evacuation Monitor")
st.markdown(f"**Objective:** Monitor overcrowding and disease transmission risk in **{len(df_selection):,}** active facilities.")
st.caption("Subject: Health Informatics (ITE3) | Final Requirement")
st.markdown("---")

# --- TOP METRICS ---
total_cap = df_selection["Capacity"].sum()
total_evac = df_selection["Current_Evacuees"].sum()
occupancy_rate = (total_evac / total_cap * 100) if total_cap > 0 else 0

# Health-based coloring for metrics
risk_color = "normal"
if occupancy_rate > 100: risk_color = "inverse" # Red if overcrowded

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Facilities", f"{len(df_selection):,}")
c2.metric("Total Capacity", f"{total_cap:,}")
c3.metric("Current Evacuees (Sim)", f"{total_evac:,}")
c4.metric("Avg Occupancy Rate", f"{occupancy_rate:.1f}%", delta="Transmission Risk", delta_color=risk_color)

st.markdown("---")

# --- ROW 1: INTERACTIVE MAP (UI/UX REQUIREMENT) ---
st.subheader("📍 Real-time Disease Risk Map")

# Dynamic Center Point
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
    color="Health_Status",
    size="Capacity", # Larger dots = Larger centers
    hover_name="Center_Name",
    hover_data={"Province": True, "Type": True, "Current_Evacuees": True, "lat": False, "lon": False},
    color_discrete_map={
        "High Health Risk (Overcrowded)": "#FF0000", # Red
        "Warning (High Density)": "#FFA500",         # Orange
        "Optimal": "#008000"                         # Green
    },
    zoom=zoom_level,
    center={"lat": center_lat, "lon": center_lon},
    mapbox_style="open-street-map",
    height=500
)
st.plotly_chart(fig_map, use_container_width=True)

# --- ROW 2: CHARTS ---
c5, c6 = st.columns(2)

with c5:
    st.subheader("📊 Overcrowding by Facility Type")
    # Sort to show highest risk first
    type_risk = df_selection.groupby("Type")[["Capacity", "Current_Evacuees"]].sum().reset_index()
    fig_bar = px.bar(type_risk, x="Type", y=["Capacity", "Current_Evacuees"], 
                     barmode="overlay", title="Capacity vs. Actual Load")
    st.plotly_chart(fig_bar, use_container_width=True)

with c6:
    st.subheader("⚠️ Health Risk Distribution")
    fig_pie = px.pie(df_selection, names="Health_Status", hole=0.4, 
                     color="Health_Status",
                     color_discrete_map={
                        "High Health Risk (Overcrowded)": "#FF0000",
                        "Warning (High Density)": "#FFA500",
                        "Optimal": "#008000"
                     })
    st.plotly_chart(fig_pie, use_container_width=True)

# --- ROW 3: INTEGRATED DATA ---
st.subheader("💾 Data Registry & Audit")
tab1, tab2 = st.tabs(["🌍 Live Sensor Data (GeoJSON)", "📑 LGU Registry (Excel)"])

with tab1:
    st.markdown("**Source:** `ph_evacs_cleaned.geojson` | **Update Frequency:** Real-time (Simulated)")
    cols = ['Center_Name', 'Province', 'Type', 'Health_Status', 'Current_Evacuees', 'Capacity', 'Last_Sensor_Ping']
    st.dataframe(df_selection[cols], use_container_width=True)

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