import streamlit as st
import pandas as pd
import os
import subprocess
import glob
import time
import sys
from datetime import datetime, timedelta

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
        files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
        if not files: return None
        return max(files, key=os.path.getmtime)
    except: return None

def reset_system():
    """Tüm verileri ve raporları temizler."""
    deleted_count = 0
    # 1. Hisse Verilerini Sil
    data_files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    for f in data_files:
        try:
            os.remove(f)
            deleted_count += 1
        except: pass
    # 2. Raporları Sil
    report_files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
    for f in report_files:
        try:
            os.remove(f)
            deleted_count += 1
        except: pass
    return deleted_count

def run_script(script_name, display_name):
    """Harici Python dosyasını çalıştırır."""
    script_path = os.path.join(BASE_DIR, script_name)
    
    if not os.path.exists(script_path):
        st.error(f"❌ Dosya bulunamadı: {script_name}")
        return

    status_area = st.empty()
    status_area.info(f"⏳ {display_name} çalıştırılıyor... Lütfen bekleyin.")
    
    try:
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
            status_area.success(f"✅ {display_name} tamamlandı! Sonuçlar aşağıdadır.")
            with st.expander("İşlem Kayıtlarını Gör (Log)", expanded=False):
                st.code(stdout)
        else:
            status_area.error("⚠️ Bir hata oluştu!")
            with st.expander("Hata Detayları"):
                st.code(stderr)
                
    except Exception as e:
        status_area.error(f"Beklenmedik hata: {e}")

def get_latest_files_list():
    files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
    files.sort(key=os.path.getmtime, reverse=True)
    return files

# --- ARAYÜZ (UI) ---

st.title("🎛️ Borsa Algoritmik Komuta Paneli")

# DURUM GÖSTERGESİ
excel_files_data = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
file_count = len(excel_files_data)
c1, c2 = st.columns([3, 1])
with c1:
    if file_count > 10:
        st.success(f"✅ **SİSTEM HAZIR:** {file_count} adet hisse verisi mevcut.")
    elif file_count > 0:
        st.warning(f"⚠️ **EKSİK VERİ:** Sadece {file_count} adet veri var.")
    else:
        st.error("🛑 **VERİ YOK:** Analiz yapamazsınız. Lütfen en alttan 'Verileri Güncelle' butonuna basın.")

with c2:
    if file_count > 0:
        latest_data = max(excel_files_data, key=os.path.getmtime)
        last_update = datetime.fromtimestamp(os.path.getmtime(latest_data)) + timedelta(hours=3)
        st.info(f"🕒 Veri Saati (TR): **{last_update.strftime('%H:%M')}**")

st.markdown("---")

# YAN MENÜ
with st.sidebar:
    st.header("📂 Rapor Geçmişi")
    if st.button("🔄 Listeyi Yenile"):
        time.sleep(0.5)
        st.rerun()
    st.write("---")
    
    latest_files = get_latest_files_list()
    if latest_files:
        for f in latest_files:
            fname = os.path.basename(f)
            with open(f, "rb") as file:
                st.download_button(
                    label=f"📥 İndir: {fname}",
                    data=file,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.caption("Henüz rapor yok.")
    
    st.markdown("---")
    
    # SIFIRLAMA ALANI
    st.header("🗑️ Temizlik")
    with st.expander("⚠️ Tehlikeli Bölge"):
        st.caption("Tüm hisse verilerini ve raporları siler.")
        confirm_reset = st.checkbox("Evet, her şeyi silmek istiyorum.")
        
        if st.button("💥 SİSTEMİ SIFIRLA", type="primary", disabled=not confirm_reset):
            deleted = reset_system()
            st.toast(f"Toplam {deleted} dosya silindi!", icon="🧹")
            time.sleep(1)
            st.rerun()

# --- VERİ TABANI GÖZLEMCİSİ ---
with st.expander("📂 **VERİ TABANINI İNCELE (Hisse Kontrol)**", expanded=False):
    if file_count > 0:
        # Dosya seçici
        file_options = sorted([os.path.basename(f) for f in excel_files_data])
        selected_file = st.selectbox("İncelemek istediğiniz hisseyi seçin:", file_options)
        
        if selected_file:
            file_path = os.path.join(DATA_DIR, selected_file)
            try:
                df_view = pd.read_excel(file_path)
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Toplam Satır", len(df_view))
                
                if 'DATE' in df_view.columns:
                    last_date = pd.to_datetime(df_view['DATE'].iloc[-1]).strftime('%Y-%m-%d')
                    k2.metric("Son Veri Tarihi", last_date)
                
                if 'CLOSING_TL' in df_view.columns:
                    last_price = df_view['CLOSING_TL'].iloc[-1]
                    k3.metric("Son Fiyat", f"{last_price:.2f}")

                st.caption("Son 10 Günlük Veri:")
                st.dataframe(df_view.tail(10), use_container_width=True)
                
            except Exception as e:
                st.error(f"Dosya okunamadı: {e}")
    else:
        st.info("Henüz veri indirilmemiş.")

st.markdown("---")

# BUTONLAR
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
    if st.button("🧪 RUA v3 + Güçlü Trend", use_container_width=True):
        run_script("rua_trend.py", "RUA Trend Analizi")
    if st.button("👑 4'lü Kombine (RUA+FRM+BUM+TREF)", type="primary", use_container_width=True):
        run_script("kombine_tarama.py", "4'lü Kombine Tarama")

with col3:
    st.info("📈 **Teknik Göstergeler**")
    if st.button("📢 Hacimli EMA Cross", use_container_width=True):
        run_script("hacimli_ema.py", "Hacimli EMA Cross")
    if st.button("📏 LinReg & EMA", use_container_width=True):
        run_script("linreg_extended.py", "LinReg Extended")
    if st.button("🧬 Hibrit Tarama V4", use_container_width=True):
        run_script("hibo_v4.py", "Hibo V4")

st.markdown("---")

# SONUÇ GÖRÜNTÜLEME
latest_result_file = get_latest_report_file()

if latest_result_file:
    st.header("📊 Son Analiz Sonuçları")
    st.caption(f"Dosya: {os.path.basename(latest_result_file)}")
    try:
        xl = pd.ExcelFile(latest_result_file)
        sheet_names = xl.sheet_names
        
        if len(sheet_names) > 1:
            selected_sheet = st.selectbox("Görüntülenecek Sayfa:", sheet_names)
        else:
            selected_sheet = sheet_names[0]
        
        df_sheet = pd.read_excel(latest_result_file, sheet_name=selected_sheet)
        st.dataframe(df_sheet, use_container_width=True)
        
    except Exception as e:
        st.warning(f"Dosya okunamadı. Soldan indirip açmayı deneyin. Hata: {e}")
else:
    st.info("Analiz sonucu bekleniyor...")

st.markdown("---")
st.subheader("🔄 Veri Tabanı")

if st.button("🌍 Verileri Güncelle (Yahoo Finance - 10 Yıllık)", type="primary", use_container_width=True):
    run_script("FinDow_Otomatik.py", "Veri İndirme Robotu")
