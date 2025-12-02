import streamlit as st
import pandas as pd
import os
import subprocess
import glob
import time
import sys  # <--- HATA GİDERİCİ KİLİT KÜTÜPHANE

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

st.set_page_config(page_title="Borsa Komuta Merkezi", page_icon="🚀", layout="wide")

# --- FONKSİYONLAR ---

def get_latest_report_file():
    """Ana dizindeki en son oluşturulan Excel raporunu bulur."""
    try:
        # Sadece ana dizindeki raporları al (DATAson içindekileri değil)
        files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
        if not files:
            return None
        # En yeni dosyayı bul
        latest_file = max(files, key=os.path.getmtime)
        return latest_file
    except:
        return None

def run_script(script_name, display_name):
    """Harici Python dosyasını çalıştırır ve sonuçları ekrana basar."""
    script_path = os.path.join(BASE_DIR, script_name)
    
    if not os.path.exists(script_path):
        st.error(f"❌ Dosya bulunamadı: {script_name}")
        return

    # Başlangıçtaki en son dosyayı kaydet (Yeni dosya oluştu mu kontrolü için)
    file_before = get_latest_report_file()
    
    status_area = st.empty()
    output_area = st.empty()
    result_area = st.container() # Sonuç tablosu için alan
    
    status_area.info(f"⏳ {display_name} çalıştırılıyor... Lütfen bekleyin.")
    
    try:
        # --- HATA DÜZELTME NOKTASI ---
        # 'python' yerine sys.executable kullanarak sistemin kendi Python'unu zorluyoruz.
        # Bu sayede tvDatafeed kütüphanesini görmemezlik yapamaz.
        process = subprocess.Popen(
            [sys.executable, script_path], 
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
            
            # --- EKRANDA GÖSTERME ÖZELLİĞİ ---
            # Eğer bu bir analiz scriptiyse (Veri indirme değilse) sonucu göster
            if "FinDow" not in script_name:
                file_after = get_latest_report_file()
                
                # Yeni bir dosya oluştuysa veya güncellendiyse
                if file_after and (file_before != file_after or os.path.getmtime(file_after) > time.time() - 60):
                    try:
                        df_result = pd.read_excel(file_after)
                        with result_area:
                            st.subheader(f"📊 Analiz Sonucu: {os.path.basename(file_after)}")
                            st.dataframe(df_result, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Tablo gösterilemedi (Dosya formatı uyumsuz olabilir): {e}")

            with output_area.expander("İşlem Kayıtlarını Gör (Log)", expanded=False):
                st.code(stdout)
        else:
            status_area.error("⚠️ Bir hata oluştu!")
            with output_area.expander("Hata Detayları"):
                st.code(stderr)
                
    except Exception as e:
        status_area.error(f"Beklenmedik hata: {e}")

def get_latest_files_list():
    files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
    files.sort(key=os.path.getmtime, reverse=True)
    return files

# --- ARAYÜZ (UI) ---

st.title("🎛️ Borsa Algoritmik Komuta Paneli (V2)")
st.caption(f"Sistem Yolu: `{sys.executable}`") # Debug bilgisi
st.markdown("---")

# YAN MENÜ
with st.sidebar:
    st.header("📂 Rapor Geçmişi")
    if st.button("🔄 Listeyi Yenile"):
        time.sleep(0.5)
        st.rerun()
    
    latest_files = get_latest_files_list()
    if latest_files:
        for f in latest_files:
            fname = os.path.basename(f)
            with open(f, "rb") as file:
                st.download_button(
                    label=f"📥 {fname}",
                    data=file,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

# ANA BUTONLAR
st.subheader("🛠️ Analiz Araçları")
col1, col2, col3 = st.columns(3)

with col1:
    st.info("📊 **Trend Analizleri**")
    if st.button("🚀 Güçlü Trend & Kanal", use_container_width=True):
        run_script("guclu_trend.py", "Güçlü Trend Analizi")
    if st.button("🏆 Expert MA Dashboard", use_container_width=True):
        run_script("expert_ma.py", "ExpertMA Puanlama")

with col2:
    st.info("🎯 **Kombine Sistemler**")
    if st.button("💎 3+1 Süper Tarama", use_container_width=True):
        run_script("super_3_1.py", "3+1 Süper Tarama")
    if st.button("⚡ 3'lü Algo (Süre)", use_container_width=True):
        run_script("super_tarama_v2.py", "Hull+BUM+TREF")
    if st.button("🧬 Hibrit Tarama V4", use_container_width=True):
        run_script("hibo_v4.py", "Hibo V4")

with col3:
    st.info("📈 **Teknik Göstergeler**")
    if st.button("📢 Hacimli EMA Cross", use_container_width=True):
        run_script("hacimli_ema.py", "Hacimli EMA Cross")
    if st.button("📏 LinReg & EMA", use_container_width=True):
        run_script("linreg_extended.py", "LinReg Extended")

st.markdown("---")
st.subheader("🔄 Veri Tabanı")

if st.button("🌍 Verileri Güncelle (TradingView)", type="primary", use_container_width=True):
    run_script("FinDow_Otomatik.py", "Veri İndirme Robotu")
