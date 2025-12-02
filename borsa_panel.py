import streamlit as st
import pandas as pd
import os
import subprocess
import glob
import time

# --- BULUT UYUMLU AYARLAR ---
# Bu dosyanın bulunduğu klasörü kök dizin yap
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')

# Klasör yoksa oluştur
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

st.set_page_config(page_title="Borsa Komuta Merkezi", page_icon="🚀", layout="wide")

# --- FONKSİYONLAR ---

def run_script(script_name, display_name):
    """Harici Python dosyasını çalıştırır."""
    script_path = os.path.join(BASE_DIR, script_name)
    
    if not os.path.exists(script_path):
        st.error(f"❌ Dosya bulunamadı: {script_name}")
        return

    status_area = st.empty()
    output_area = st.empty()
    
    status_area.info(f"⏳ {display_name} çalıştırılıyor... (Bu işlem veri boyutuna göre zaman alabilir)")
    
    try:
        # Scripti çalıştır
        process = subprocess.Popen(
            ['python', script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=BASE_DIR, 
            encoding='utf-8',
            errors='ignore'
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            status_area.success(f"✅ {display_name} tamamlandı!")
            with output_area.expander("İşlem Kayıtlarını Gör", expanded=False):
                st.code(stdout)
        else:
            status_area.error("⚠️ Bir hata oluştu!")
            with output_area.expander("Hata Detayları"):
                st.code(stderr)
                
    except Exception as e:
        status_area.error(f"Beklenmedik hata: {e}")

def get_latest_files():
    """Klasördeki Excel dosyalarını tarihe göre sıralar."""
    files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
    # Tarihe göre tersten sırala (en yeni en üstte)
    files.sort(key=os.path.getmtime, reverse=True)
    return files

# --- ARAYÜZ (UI) ---

st.title("🎛️ Borsa Algoritmik Komuta Paneli (Cloud)")
st.info(f"Çalışma Dizini: `{BASE_DIR}`")
st.markdown("---")

# YAN MENÜ: DOSYA İNDİRME MERKEZİ
with st.sidebar:
    st.header("📂 Rapor İndirme Merkezi")
    if st.button("🔄 Listeyi Yenile"):
        time.sleep(0.5)
        st.rerun()
    
    st.write("---")
    
    latest_files = get_latest_files()
    if latest_files:
        for f in latest_files:
            fname = os.path.basename(f)
            # İndirme Butonu
            with open(f, "rb") as file:
                st.download_button(
                    label=f"📥 İndir: {fname}",
                    data=file,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("Henüz hiç rapor oluşturulmadı.")

# ANA EKRAN: BUTONLAR
st.subheader("🛠️ Tarama Algoritmaları")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 Trend & Skor")
    if st.button("🚀 Güçlü Trend & Kanal", use_container_width=True):
        run_script("guclu_trend.py", "Güçlü Trend Analizi")
    if st.button("🏆 Expert MA Dashboard", use_container_width=True):
        run_script("expert_ma.py", "ExpertMA Puanlama")

with col2:
    st.markdown("### 🎯 Kombine Taramalar")
    if st.button("💎 3+1 Süper Tarama", use_container_width=True):
        run_script("super_3_1.py", "3+1 Süper Tarama")
    if st.button("⚡ 3'lü Algo (Süre Analizli)", use_container_width=True):
        run_script("super_tarama_v2.py", "Hull+BUM+TREF")
    if st.button("🧬 Hibrit Tarama V4", use_container_width=True):
        run_script("hibo_v4.py", "Hibo V4")

with col3:
    st.markdown("### 📈 Teknik & Hacim")
    if st.button("📢 Hacimli EMA Cross", use_container_width=True):
        run_script("hacimli_ema.py", "Hacimli EMA Cross")
    if st.button("📏 LinReg & EMA Extended", use_container_width=True):
        run_script("linreg_extended.py", "LinReg Extended")

st.markdown("---")
st.subheader("🔄 Veri Yönetimi")
st.caption("Bulut sunucusu her yeniden başladığında veriler silinebilir. Analizden önce mutlaka verileri güncelleyin.")

if st.button("🌍 Verileri Güncelle (TradingView)", type="primary", use_container_width=True):
    run_script("FinDow_Otomatik.py", "Veri İndirme Robotu")