import streamlit as st
import pandas as pd
import os
import subprocess
import glob
import time
import sys
import plotly.express as px # Isı Haritası İçin
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

st.set_page_config(page_title="Borsa Komuta Merkezi Pro", page_icon="🚀", layout="wide")

# --- FONKSİYONLAR ---
def get_latest_report_file():
    try:
        files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
        if not files: return None
        return max(files, key=os.path.getmtime)
    except: return None

def reset_system():
    d = 0
    for f in glob.glob(os.path.join(DATA_DIR, "*.xlsx")) + glob.glob(os.path.join(BASE_DIR, "*.xlsx")):
        try: os.remove(f); d+=1
        except: pass
    return d

def run_script(script_name, display_name):
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path): st.error("Dosya yok!"); return
    status = st.empty(); status.info(f"⏳ {display_name} çalışıyor...")
    try:
        proc = subprocess.Popen([sys.executable, script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR, encoding='utf-8', errors='ignore')
        out, err = proc.communicate()
        if proc.returncode == 0:
            status.success(f"✅ {display_name} tamamlandı!")
            if "FinDow" not in script_name: # Analizse göster
                latest = get_latest_report_file()
                if latest: 
                    st.divider(); st.subheader(f"📊 Sonuç: {os.path.basename(latest)}")
                    try: st.dataframe(pd.read_excel(latest), use_container_width=True)
                    except: pass
        else: status.error("Hata!"); st.code(err)
    except Exception as e: status.error(f"Hata: {e}")

# --- HEATMAP FONKSİYONU ---
def draw_heatmap():
    temel_file = os.path.join(DATA_DIR, "TEMEL_VERILER.xlsx")
    if not os.path.exists(temel_file):
        st.warning("⚠️ Isı haritası için önce 'Verileri Güncelle' butonuna basmalısınız.")
        return

    try:
        df = pd.read_excel(temel_file)
        # Piyasa değeri olmayanları temizle veya ufak değer ver
        df['Piyasa_Degeri'] = df['Piyasa_Degeri'].fillna(1000000)
        df['Sektor'] = df['Sektor'].fillna('Diğer')
        
        # Treemap
        fig = px.treemap(
            df, 
            path=[px.Constant("BIST"), 'Sektor', 'Hisse'], 
            values='Piyasa_Degeri',
            color='Degisim_Yuzde',
            color_continuous_scale=['red', 'black', 'green'],
            color_continuous_midpoint=0,
            hover_data=['Fiyat', 'Degisim_Yuzde', 'FK', 'PD_DD'],
            title="BIST Sektörel Isı Haritası (Günlük Değişim)"
        )
        fig.update_layout(height=600, margin=dict(t=30, l=10, r=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Harita çizilemedi: {e}")

# --- ARAYÜZ ---
st.title("🎛️ Borsa Komuta Merkezi Pro")

# TAB MENÜSÜ (YENİ TASARIM)
tab_analiz, tab_lab, tab_heatmap = st.tabs(["🚀 Analiz Paneli", "🔬 Hisse Lab", "🔥 Isı Haritası"])

# 1. ANALİZ PANELİ
with tab_analiz:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📊 **Trend**")
        if st.button("Güçlü Trend", use_container_width=True): run_script("guclu_trend.py", "Trend")
        if st.button("Expert MA", use_container_width=True): run_script("expert_ma.py", "ExpertMA")
        if st.button("Hull Trend", use_container_width=True): run_script("hull_analiz.py", "Hull")
    with col2:
        st.info("🎯 **Kombine**")
        if st.button("3+1 Süper", use_container_width=True): run_script("super_3_1.py", "3+1")
        if st.button("3'lü (Temel Analizli)", use_container_width=True): run_script("super_tarama_v2.py", "3'lü")
        if st.button("RUA Trend", use_container_width=True): run_script("rua_trend.py", "RUA")
        if st.button("4'lü Kombine", type="primary", use_container_width=True): run_script("kombine_tarama.py", "4'lü")
    with col3:
        st.info("📈 **Teknik**")
        if st.button("Hacimli EMA", use_container_width=True): run_script("hacimli_ema.py", "EMA")
        if st.button("LinReg Full", use_container_width=True): run_script("linreg_extended.py", "LinReg")
        if st.button("Hibrit V4", use_container_width=True): run_script("hibo_v4.py", "Hibo")
    
    st.divider()
    c_upd, c_reset = st.columns([3, 1])
    with c_upd:
        if st.button("🌍 Verileri Güncelle (Yahoo - 10 Yıl + Temel)", type="primary", use_container_width=True):
            run_script("FinDow_Otomatik.py", "Veri İndirme")
    with c_reset:
        with st.popover("🗑️"):
            if st.button("Sıfırla", type="primary"): reset_system(); st.toast("Temizlendi!"); time.sleep(1); st.rerun()

# 2. HİSSE LAB (GRAFİK)
with tab_lab:
    files = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
    if files:
        stock = st.selectbox("Hisse Seç:", sorted([os.path.basename(f).replace('.xlsx','') for f in files if "TEMEL" not in f]))
        if stock:
            df = pd.read_excel(os.path.join(DATA_DIR, f"{stock}.xlsx"))
            fig = go.Figure(data=[go.Candlestick(x=df['DATE'], open=df['OPEN_TL'], high=df['HIGH_TL'], low=df['LOW_TL'], close=df['CLOSING_TL'])])
            fig.update_layout(height=500, title=f"{stock} Grafiği", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)
    else: st.warning("Veri yok.")

# 3. ISI HARİTASI
with tab_heatmap:
    draw_heatmap()

# YAN MENÜ (Raporlar)
with st.sidebar:
    st.header("📂 Raporlar")
    if st.button("🔄"): st.rerun()
    for f in glob.glob(os.path.join(BASE_DIR, "*.xlsx")):
        with open(f, "rb") as file: st.download_button(f"📥 {os.path.basename(f)}", data=file, file_name=os.path.basename(f))
