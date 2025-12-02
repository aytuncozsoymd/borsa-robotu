import streamlit as st
import pandas as pd
import numpy as np
import os
import subprocess
import glob
import time
import sys
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

st.set_page_config(page_title="Borsa Komuta Merkezi Pro", page_icon="🚀", layout="wide")

# ==================== MATEMATİKSEL FONKSİYONLAR ====================

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calculate_hull(series, length=89):
    wma_half = calculate_wma(series, int(length / 2))
    wma_full = calculate_wma(series, length)
    raw_hma = 2 * wma_half - wma_full
    return calculate_wma(raw_hma, int(np.sqrt(length)))

def calculate_atr(df, length=14):
    if 'HIGH_TL' not in df.columns or 'LOW_TL' not in df.columns:
        return df['CLOSING_TL'].diff().abs().ewm(alpha=1/length, adjust=False).mean()
    high = df['HIGH_TL']; low = df['LOW_TL']; close = df['CLOSING_TL']
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def calculate_custom_tema(series, period):
    e1 = series.ewm(span=period, adjust=False).mean()
    e2 = e1.ewm(span=period, adjust=False).mean()
    e3 = e2.ewm(span=period, adjust=False).mean()
    return (3 * e1) - (3 * e2) + e3

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).fillna(50)

def calculate_mfi(df, period=14):
    if 'VOLUME_TL' not in df.columns or 'HIGH_TL' not in df.columns:
        return calculate_rsi(df['CLOSING_TL'], period)
    tp = (df['HIGH_TL'] + df['LOW_TL'] + df['CLOSING_TL']) / 3
    rmf = tp * df['VOLUME_TL']
    pos = np.where(tp > tp.shift(1), rmf, 0); neg = np.where(tp < tp.shift(1), rmf, 0)
    p_sum = pd.Series(pos).rolling(period).sum()
    n_sum = pd.Series(neg).rolling(period).sum()
    mfi = 100 - (100 / (1 + p_sum/n_sum))
    return mfi.fillna(50)

def calculate_bollinger_bands(series, period=20, std_dev=2):
    sma = series.rolling(period).mean()
    std = series.rolling(period).std()
    return sma + (std * std_dev), sma - (std * std_dev)

# ==================== BACKTEST MOTORU (GELİŞMİŞ) ====================

def run_backtest_engine(df, strategy_name):
    close = df['CLOSING_TL']
    high = df['HIGH_TL'] if 'HIGH_TL' in df.columns else close
    low = df['LOW_TL'] if 'LOW_TL' in df.columns else close
    
    trades = []
    in_position = False
    entry_price = 0
    entry_date = None
    equity = [100]
    signals = []
    plot_data = {} # Grafik için ek veriler
    
    # --- STRATEJİ HAZIRLIKLARI ---
    
    if strategy_name == "FRM (Hull + ATR)":
        wma10 = calculate_wma(close, 10)
        hull = calculate_wma(wma10, 89)
        atr = calculate_atr(df, 14)
        plot_data = {'line1': hull, 'name1': 'Hull MA (89)', 'color1': 'orange'}
        
    elif strategy_name == "BUM (TEMA Cross)":
        ma1 = calculate_custom_tema(close, 34)
        ma2 = calculate_custom_tema(close, 68)
        plot_data = {'line1': ma1, 'name1': 'TEMA 34', 'color1': 'cyan',
                     'line2': ma2, 'name2': 'TEMA 68', 'color2': 'magenta'}
        
    elif strategy_name == "TREF (Momentum)":
        rsi = calculate_rsi(close)
        mfi = calculate_mfi(df)
        tref_mom = (rsi + mfi) / 2
        ema5 = calculate_ema(close, 5)
        # Grafik için Momentum (Ayrı panele çizilir normalde ama burada fiyat üstüne EMA5 çizelim)
        plot_data = {'line1': ema5, 'name1': 'EMA 5', 'color1': 'yellow'}
        
    elif strategy_name == "RUA (Dip Avcısı)":
        rsi = calculate_rsi(close)
        mfi = calculate_mfi(df)
        rua = (rsi + mfi) / 2
        bb_up, bb_low = calculate_bollinger_bands(rua)
        # RUA bir osilatördür, fiyat üzerine çizilmez. Grafik kısmında özel işlenmeli.
        # Biz burada referans olarak boş geçelim, sinyalleri işleyelim.
        pass

    # --- SİMÜLASYON DÖNGÜSÜ ---
    
    start_idx = 100 # İndikatörlerin oturması için pay
    
    for i in range(start_idx, len(df)):
        price = close.iloc[i]
        date = df['DATE'].iloc[i]
        
        is_buy = False
        is_sell = False
        
        # --- SİNYAL KONTROLLERİ ---
        
        if strategy_name == "FRM (Hull + ATR)":
            h_val = hull.iloc[i]
            a_val = atr.iloc[i] if atr is not None else 0
            prev_close = close.iloc[i-1]
            
            # FRM Mantığı: Hull üstünde ve ATR kadar kopmuşsa AL
            if price > h_val and price > (prev_close + a_val): is_buy = True
            elif price < h_val and price < (prev_close - a_val): is_sell = True
            
        elif strategy_name == "BUM (TEMA Cross)":
            m1_val = ma1.iloc[i]; m2_val = ma2.iloc[i]
            m1_prev = ma1.iloc[i-1]; m2_prev = ma2.iloc[i-1]
            
            if m1_prev <= m2_prev and m1_val > m2_val: is_buy = True
            elif m1_prev >= m2_prev and m1_val < m2_val: is_sell = True
            
        elif strategy_name == "TREF (Momentum)":
            mom_val = tref_mom.iloc[i]
            mom_prev = tref_mom.iloc[i-1]
            e5_val = ema5.iloc[i]; e5_prev = ema5.iloc[i-1]
            
            # TREF: Momentum 50'yi yukarı kesti ve EMA5 artıyor
            if mom_val > 50 and mom_prev <= 50 and e5_val > e5_prev: is_buy = True
            elif mom_val < 40: is_sell = True
            
        elif strategy_name == "RUA (Dip Avcısı)":
            r_val = rua.iloc[i]; r_prev = rua.iloc[i-1]
            l_val = bb_low.iloc[i]; l_prev = bb_low.iloc[i-1]
            u_val = bb_up.iloc[i]; u_prev = bb_up.iloc[i-1]
            
            # RUA: Alt bandı yukarı kesti (AL), Üst bandı aşağı kesti (SAT)
            if r_prev < l_prev and r_val > l_val: is_buy = True
            elif r_prev > u_prev and r_val < u_val: is_sell = True

        # --- İŞLEM YÖNETİMİ ---
        
        if is_buy and not in_position:
            in_position = True
            entry_price = price
            entry_date = date
            signals.append({'date': date, 'price': price, 'type': 'buy'})
            
        elif is_sell and in_position:
            in_position = False
            exit_price = price
            pnl = ((exit_price - entry_price) / entry_price) * 100
            trades.append({
                'Giriş Tarihi': entry_date,
                'Çıkış Tarihi': date,
                'Giriş Fiyatı': entry_price,
                'Çıkış Fiyatı': exit_price,
                'Kar/Zarar %': pnl
            })
            equity.append(equity[-1] * (1 + pnl/100))
            signals.append({'date': date, 'price': price, 'type': 'sell'})
            
    # Açık Pozisyon Kontrolü
    current_status = "NAKİT"
    if in_position:
        current_status = "POZİSYONDA (AL)"
        pnl = ((close.iloc[-1] - entry_price) / entry_price) * 100
        trades.append({'Giriş Tarihi': entry_date, 'Çıkış Tarihi': 'Devam Ediyor', 
                       'Giriş Fiyatı': entry_price, 'Çıkış Fiyatı': close.iloc[-1], 'Kar/Zarar %': pnl})
        
    return trades, equity, signals, plot_data, current_status

# --- PANEL FONKSİYONLARI ---
def get_latest_report_file():
    try:
        files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
        if not files: return None
        return max(files, key=os.path.getmtime)
    except: return None

def reset_system():
    deleted_count = 0
    for f in glob.glob(os.path.join(DATA_DIR, "*.xlsx")) + glob.glob(os.path.join(BASE_DIR, "*.xlsx")):
        try: os.remove(f); deleted_count += 1
        except: pass
    return deleted_count

def run_script(script_name, display_name):
    script_path = os.path.join(BASE_DIR, script_name)
    if not os.path.exists(script_path):
        st.error(f"❌ Dosya bulunamadı: {script_name}"); return

    status_area = st.empty()
    status_area.info(f"⏳ {display_name} çalıştırılıyor...")
    
    try:
        process = subprocess.Popen([sys.executable, script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=BASE_DIR, encoding='utf-8', errors='ignore')
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            status_area.success(f"✅ {display_name} tamamlandı! Sonuçlar aşağıdadır.")
            with st.expander("Log Kayıtları"): st.code(stdout)
        else:
            status_area.error("⚠️ Hata oluştu!"); st.code(stderr)
    except Exception as e: status_area.error(f"Hata: {e}")

def get_latest_files_list():
    files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
    files.sort(key=os.path.getmtime, reverse=True)
    return files

# --- ARAYÜZ (UI) ---

st.title("🎛️ Borsa Komuta Merkezi Pro")

# 1. DURUM PANELİ
excel_files_data = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
file_count = len(excel_files_data)
c1, c2 = st.columns([3, 1])
with c1:
    if file_count > 10: st.success(f"✅ **SİSTEM HAZIR:** {file_count} hisse verisi mevcut.")
    elif file_count > 0: st.warning(f"⚠️ **EKSİK VERİ:** {file_count} adet veri var.")
    else: st.error("🛑 **VERİ YOK:** Lütfen verileri güncelleyin.")
with c2:
    if file_count > 0:
        latest = max(excel_files_data, key=os.path.getmtime)
        last_update = datetime.fromtimestamp(os.path.getmtime(latest)) + timedelta(hours=3)
        st.info(f"🕒 Veri: **{last_update.strftime('%H:%M')}**")

st.markdown("---")

# 2. YAN MENÜ
with st.sidebar:
    st.header("📂 Raporlar")
    if st.button("🔄 Yenile"): time.sleep(0.5); st.rerun()
    st.write("---")
    for f in get_latest_files_list():
        with open(f, "rb") as file:
            st.download_button(f"📥 {os.path.basename(f)}", data=file, file_name=os.path.basename(f))
    
    st.markdown("---")
    st.header("🗑️ Temizlik")
    with st.popover("⚠️ Verileri Sil"):
        if st.button("EVET, SİL", type="primary"):
            d = reset_system(); st.toast(f"{d} dosya silindi!"); time.sleep(1); st.rerun()

# 3. HİSSE LABORATUVARI (BACKTEST)
st.subheader("🔬 Hisse Laboratuvarı (Grafik & Backtest)")

if file_count > 0:
    col_sel1, col_sel2 = st.columns([1, 1])
    
    with col_sel1:
        stock_options = sorted([os.path.basename(f).replace('.xlsx','') for f in excel_files_data])
        selected_stock = st.selectbox("Analiz edilecek hisseyi seçin:", stock_options)
        
    with col_sel2:
        strategies = ["FRM (Hull + ATR)", "BUM (TEMA Cross)", "TREF (Momentum)", "RUA (Dip Avcısı)"]
        selected_strategy = st.selectbox("Uygulanacak Strateji:", strategies)
    
    if selected_stock and selected_strategy:
        file_path = os.path.join(DATA_DIR, f"{selected_stock}.xlsx")
        try:
            df = pd.read_excel(file_path)
            # Sütun düzeltme
            df.columns = [str(c).strip().upper() for c in df.columns]
            col_map = {"DATE":["DATE","TARIH"], "CLOSING_TL":["CLOSING_TL","CLOSE"]}
            for t, a in col_map.items():
                for alias in a: 
                    if alias in df.columns: df.rename(columns={alias:t}, inplace=True)
            df['DATE'] = pd.to_datetime(df['DATE'])
            
            # --- BACKTEST ÇALIŞTIR ---
            trades, equity, signals, plot_data, status = run_backtest_engine(df, selected_strategy)
            
            # --- METRİKLER ---
            total_trades = len(trades)
            win_trades = sum(1 for t in trades if t['Kar/Zarar %'] > 0)
            win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0
            total_return = equity[-1] - 100
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Son Fiyat", f"{df['CLOSING_TL'].iloc[-1]:.2f}", delta=None)
            m2.metric("Mevcut Durum", status, delta_color="normal" if "AL" in status else "off")
            m3.metric("Toplam Getiri", f"%{total_return:.1f}")
            m4.metric("Başarı Oranı", f"%{win_rate:.1f} ({total_trades} İşlem)")
            
            # --- GRAFİK ÇİZİMİ (PLOTLY) ---
            tab1, tab2 = st.tabs(["📈 İnteraktif Grafik", "📋 İşlem Geçmişi"])
            
            with tab1:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.03, row_heights=[0.7, 0.3])

                # Mum Grafiği
                fig.add_trace(go.Candlestick(x=df['DATE'],
                                open=df['OPEN_TL'] if 'OPEN_TL' in df else df['CLOSING_TL'],
                                high=df['HIGH_TL'] if 'HIGH_TL' in df else df['CLOSING_TL'],
                                low=df['LOW_TL'] if 'LOW_TL' in df else df['CLOSING_TL'],
                                close=df['CLOSING_TL'], name='Fiyat'), row=1, col=1)
                
                # Strateji İndikatörleri (Varsa)
                if 'line1' in plot_data:
                    fig.add_trace(go.Scatter(x=df['DATE'], y=plot_data['line1'], 
                                             line=dict(color=plot_data.get('color1', 'orange'), width=2), 
                                             name=plot_data.get('name1', 'Ind 1')), row=1, col=1)
                if 'line2' in plot_data:
                    fig.add_trace(go.Scatter(x=df['DATE'], y=plot_data['line2'], 
                                             line=dict(color=plot_data.get('color2', 'cyan'), width=2), 
                                             name=plot_data.get('name2', 'Ind 2')), row=1, col=1)

                # AL/SAT İşaretleri
                buys = [s for s in signals if s['type']=='buy']
                sells = [s for s in signals if s['type']=='sell']
                
                fig.add_trace(go.Scatter(
                    x=[s['date'] for s in buys], y=[s['price'] for s in buys],
                    mode='markers', marker=dict(symbol='triangle-up', size=12, color='green'), name='AL'
                ), row=1, col=1)
                
                fig.add_trace(go.Scatter(
                    x=[s['date'] for s in sells], y=[s['price'] for s in sells],
                    mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='SAT'
                ), row=1, col=1)

                # Hacim
                if 'VOLUME_TL' in df:
                    fig.add_trace(go.Bar(x=df['DATE'], y=df['VOLUME_TL'], name='Hacim', marker_color='blue'), row=2, col=1)

                fig.update_layout(height=600, xaxis_rangeslider_visible=False, title=f"{selected_stock} - {selected_strategy}")
                st.plotly_chart(fig, use_container_width=True)
            
            with tab2:
                if trades:
                    trades_df = pd.DataFrame(trades)
                    trades_df['Giriş Tarihi'] = pd.to_datetime(trades_df['Giriş Tarihi']).dt.date
                    trades_df['Çıkış Tarihi'] = trades_df['Çıkış Tarihi'].apply(lambda x: x.date() if isinstance(x, (pd.Timestamp, datetime)) else x)
                    
                    st.dataframe(trades_df.style.format({
                        'Giriş Fiyatı': '{:.2f}', 'Çıkış Fiyatı': '{:.2f}', 'Kar/Zarar %': '{:.2f}%'
                    }).applymap(lambda x: 'color: green' if isinstance(x, (int, float)) and x > 0 else ('color: red' if isinstance(x, (int, float)) and x < 0 else ''), subset=['Kar/Zarar %']), use_container_width=True)
                else:
                    st.info("Bu stratejiyle henüz hiç işlem yapılmamış.")

        except Exception as e: st.error(f"Hata: {e}")
else:
    st.info("Laboratuvarı kullanmak için önce veri indirin.")

st.markdown("---")

# 4. TARAMA BUTONLARI
st.subheader("🚀 Otomatik Taramalar")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Trend**")
    if st.button("Güçlü Trend Analizi", use_container_width=True): run_script("guclu_trend.py", "Trend")
    if st.button("Expert MA Puanlama", use_container_width=True): run_script("expert_ma.py", "ExpertMA")
with c2:
    st.markdown("**Kombine**")
    if st.button("3+1 Süper Tarama", use_container_width=True): run_script("super_3_1.py", "3+1")
    if st.button("3'lü Algo (Süre)", use_container_width=True): run_script("super_tarama_v2.py", "3'lü")
    if st.button("RUA + Trend", use_container_width=True): run_script("rua_trend.py", "RUA Trend")
    if st.button("4'lü Kombine", type="primary", use_container_width=True): run_script("kombine_tarama.py", "4'lü")
with c3:
    st.markdown("**Teknik**")
    if st.button("Hacimli EMA Cross", use_container_width=True): run_script("hacimli_ema.py", "EMA")
    if st.button("LinReg Extended", use_container_width=True): run_script("linreg_extended.py", "LinReg")
    if st.button("Hibrit V4", use_container_width=True): run_script("hibo_v4.py", "Hibo")

st.markdown("---")
# SONUÇ GÖSTERME
latest = get_latest_report_file()
if latest:
    st.subheader(f"📊 Sonuç: {os.path.basename(latest)}")
    try:
        xl = pd.ExcelFile(latest)
        sheet = st.selectbox("Sayfa:", xl.sheet_names)
        st.dataframe(pd.read_excel(latest, sheet_name=sheet), use_container_width=True)
    except: pass

st.markdown("---")
if st.button("🌍 Verileri Güncelle (Yahoo - 10 Yıl)", type="primary", use_container_width=True):
    run_script("FinDow_Otomatik.py", "İndirme")
