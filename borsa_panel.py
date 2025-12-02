import streamlit as st
import pandas as pd
import numpy as np
import os
import subprocess
import glob
import time
import sys
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
if not os.path.exists(DATA_DIR): os.makedirs(DATA_DIR)

st.set_page_config(page_title="Borsa Komuta Merkezi Pro", page_icon="🚀", layout="wide")

# ==================== MATEMATİKSEL FONKSİYONLAR (Backtest) ====================
def calculate_ema(s, p): return s.ewm(span=p, adjust=False).mean()
def calculate_wma(s, l): w=np.arange(1,l+1); return s.rolling(l).apply(lambda x: np.dot(x,w)/w.sum(), raw=True)
def calculate_hull(s, l=89): w1=calculate_wma(s,int(l/2)); w2=calculate_wma(s,l); return calculate_wma(2*w1-w2, int(np.sqrt(l)))
def calculate_atr(df, l=14):
    if 'HIGH_TL' not in df: return df['CLOSING_TL'].diff().abs().ewm(alpha=1/l).mean()
    tr=pd.concat([df['HIGH_TL']-df['LOW_TL'], (df['HIGH_TL']-df['CLOSING_TL'].shift(1)).abs(), (df['LOW_TL']-df['CLOSING_TL'].shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/l).mean()
def calculate_custom_tema(s, p): e1=s.ewm(span=p).mean(); e2=e1.ewm(span=p).mean(); e3=e2.ewm(span=p).mean(); return 3*e1-3*e2+e3
def calculate_rsi(s, p=14): d=s.diff(); g=(d.where(d>0,0)).rolling(p).mean(); l=(-d.where(d<0,0)).rolling(p).mean(); return (100-(100/(1+g/l))).fillna(50)
def calculate_mfi(df, p=14):
    if 'VOLUME_TL' not in df: return calculate_rsi(df['CLOSING_TL'], p)
    tp=(df['HIGH_TL']+df['LOW_TL']+df['CLOSING_TL'])/3; rmf=tp*df['VOLUME_TL']
    pos=np.where(tp>tp.shift(1),rmf,0); neg=np.where(tp<tp.shift(1),rmf,0)
    return (100-(100/(1+pd.Series(pos).rolling(p).sum()/pd.Series(neg).rolling(p).sum()))).fillna(50)
def calculate_bollinger(s, p=20, d=2): sma=s.rolling(p).mean(); std=s.rolling(p).std(); return sma+(std*d), sma-(std*d)

# ==================== BACKTEST MOTORU ====================
def run_backtest_engine(df, strategy_name):
    close = df['CLOSING_TL']; date = df['DATE']
    trades = []; signals = []; equity = [100]
    in_pos = False; entry_price = 0; entry_date = None
    plot_data = {}; status = "NAKİT"

    # İndikatör Hazırlığı
    if "FRM" in strategy_name:
        hull = calculate_hull(close, 89); atr = calculate_atr(df)
        plot_data = {'line1': hull, 'name1': 'Hull 89', 'color1': 'orange'}
    elif "BUM" in strategy_name:
        ma1 = calculate_custom_tema(close, 34); ma2 = calculate_custom_tema(close, 68)
        plot_data = {'line1': ma1, 'name1': 'TEMA 34', 'color1': 'cyan', 'line2': ma2, 'name2': 'TEMA 68', 'color2': 'magenta'}
    elif "TREF" in strategy_name:
        rsi = calculate_rsi(close); mfi = calculate_mfi(df); tref = (rsi+mfi)/2; ema5 = calculate_ema(close, 5)
        plot_data = {'line1': ema5, 'name1': 'EMA 5', 'color1': 'yellow'}
    elif "RUA" in strategy_name:
        rsi = calculate_rsi(close); mfi = calculate_mfi(df); rua = (rsi+mfi)/2
        bb_up, bb_low = calculate_bollinger(rua)

    # Simülasyon
    for i in range(100, len(df)):
        price = close.iloc[i]; dt = date.iloc[i]
        is_buy = False; is_sell = False
        
        if "FRM" in strategy_name:
            if price > hull.iloc[i] and price > (close.iloc[i-1] + (atr.iloc[i] if atr is not None else 0)): is_buy = True
            elif price < hull.iloc[i]: is_sell = True
        elif "BUM" in strategy_name:
            if ma1.iloc[i] > ma2.iloc[i] and ma1.iloc[i-1] <= ma2.iloc[i-1]: is_buy = True
            elif ma1.iloc[i] < ma2.iloc[i]: is_sell = True
        elif "TREF" in strategy_name:
            if tref.iloc[i] > 50 and tref.iloc[i-1] <= 50 and ema5.iloc[i] > ema5.iloc[i-1]: is_buy = True
            elif tref.iloc[i] < 40: is_sell = True
        elif "RUA" in strategy_name:
            if rua.iloc[i] <= bb_low.iloc[i]: is_buy = True
            elif rua.iloc[i-1] < bb_low.iloc[i-1] and rua.iloc[i] > bb_low.iloc[i]: is_buy = True
            elif rua.iloc[i] >= bb_up.iloc[i]: is_sell = True

        if is_buy and not in_pos:
            in_pos = True; entry_price = price; entry_date = dt
            signals.append({'date': dt, 'price': price, 'type': 'buy'})
        elif is_sell and in_pos:
            in_pos = False; pnl = ((price - entry_price) / entry_price) * 100
            trades.append({'Giriş': entry_date, 'Çıkış': dt, 'Giriş Fiyat': entry_price, 'Çıkış Fiyat': price, 'Kar %': pnl})
            equity.append(equity[-1] * (1 + pnl/100))
            signals.append({'date': dt, 'price': price, 'type': 'sell'})

    if in_pos: 
        status = "POZİSYONDA (AL)"
        curr_pnl = ((close.iloc[-1] - entry_price) / entry_price) * 100
        trades.append({'Giriş': entry_date, 'Çıkış': 'Devam', 'Giriş Fiyat': entry_price, 'Çıkış Fiyat': close.iloc[-1], 'Kar %': curr_pnl})

    return trades, equity, signals, plot_data, status

# --- PANEL FONKSİYONLARI ---
def get_latest_report_file():
    try:
        files = glob.glob(os.path.join(BASE_DIR, "*.xlsx"))
        if not files: return None
        return max(files, key=os.path.getmtime)
    except: return None

def reset_system():
    d=0
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
            if "FinDow" not in script_name:
                latest = get_latest_report_file()
                if latest: 
                    st.divider(); st.subheader(f"📊 Sonuç: {os.path.basename(latest)}")
                    try: 
                        xl = pd.ExcelFile(latest)
                        sheet = st.selectbox("Sayfa:", xl.sheet_names, key=f"sel_{int(time.time())}")
                        st.dataframe(pd.read_excel(latest, sheet_name=sheet), use_container_width=True)
                    except: pass
        else: status.error("Hata!"); st.code(err)
    except Exception as e: status.error(f"Hata: {e}")

# --- ISI HARİTASI ---
def draw_heatmap():
    temel_file = os.path.join(DATA_DIR, "TEMEL_VERILER.xlsx")
    if not os.path.exists(temel_file): st.warning("⚠️ Önce verileri güncelleyin."); return
    try:
        df = pd.read_excel(temel_file)
        df['Piyasa_Degeri'] = df['Piyasa_Degeri'].fillna(1000000); df['Sektor'] = df['Sektor'].fillna('Diğer')
        fig = px.treemap(df, path=[px.Constant("BIST"), 'Sektor', 'Hisse'], values='Piyasa_Degeri', color='Degisim_Yuzde',
            color_continuous_scale=['red', 'black', 'green'], color_continuous_midpoint=0, hover_data=['Fiyat', 'Degisim_Yuzde', 'FK', 'PD_DD'],
            title="BIST Sektörel Isı Haritası")
        fig.update_layout(height=600, margin=dict(t=30, l=10, r=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except: st.error("Harita hatası.")

# --- ARAYÜZ BAŞLIYOR ---
st.title("🎛️ Borsa Komuta Merkezi Pro")

# 1. DURUM GÖSTERGESİ (SABİT)
excel_files_data = glob.glob(os.path.join(DATA_DIR, '*.xlsx'))
file_count = len(excel_files_data)
c1, c2 = st.columns([3, 1])
with c1:
    if file_count > 10: st.success(f"✅ **SİSTEM HAZIR:** {file_count} hisse verisi mevcut.")
    elif file_count > 0: st.warning(f"⚠️ **EKSİK VERİ:** {file_count} adet veri var.")
    else: st.error("🛑 **VERİ YOK:** Verileri güncelleyin.")
with c2:
    if file_count > 0:
        latest = max(excel_files_data, key=os.path.getmtime)
        last_update = datetime.fromtimestamp(os.path.getmtime(latest)) + timedelta(hours=3)
        st.info(f"🕒 Veri: **{last_update.strftime('%H:%M')}**")

# TABLAR
tab1, tab2, tab3, tab4 = st.tabs(["🚀 Analiz & Taramalar", "🔬 Hisse Lab (Backtest)", "📂 Veri Tabanı", "🔥 Isı Haritası"])

# TAB 1: ANALİZ
with tab1:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("📊 **Trend**")
        if st.button("Güçlü Trend", use_container_width=True): run_script("guclu_trend.py", "Trend")
        if st.button("Expert MA", use_container_width=True): run_script("expert_ma.py", "ExpertMA")
    with col2:
        st.info("🎯 **Kombine**")
        if st.button("3+1 Süper", use_container_width=True): run_script("super_3_1.py", "3+1")
        if st.button("3'lü (Temel Analizli)", use_container_width=True): run_script("super_tarama_v2.py", "3'lü")
        if st.button("RUA Trend", use_container_width=True): run_script("rua_trend.py", "RUA")
        if st.button("👑 4'lü Kombine", type="primary", use_container_width=True): run_script("kombine_tarama.py", "4'lü Kombine Tarama")
    with col3:
        st.info("📈 **Teknik**")
        if st.button("Hacimli EMA", use_container_width=True): run_script("hacimli_ema.py", "EMA")
        if st.button("LinReg Full", use_container_width=True): run_script("linreg_extended.py", "LinReg")
        if st.button("Hibrit V4", use_container_width=True): run_script("hibo_v4.py", "Hibo")
    
    st.markdown("---")
    if st.button("🌍 Verileri Güncelle (Yahoo - 10 Yıl + Temel)", type="primary", use_container_width=True):
        run_script("FinDow_Otomatik.py", "Veri İndirme")

# TAB 2: HİSSE LAB
with tab2:
    if file_count > 0:
        c_sel1, c_sel2 = st.columns(2)
        with c_sel1: stock = st.selectbox("Hisse Seç:", sorted([os.path.basename(f).replace('.xlsx','') for f in excel_files_data if "TEMEL" not in f]))
        with c_sel2: strat = st.selectbox("Strateji Seç:", ["FRM (Hull + ATR)", "BUM (TEMA Cross)", "TREF (Momentum)", "RUA (Dip Avcısı)"])
        if stock and strat:
            df = pd.read_excel(os.path.join(DATA_DIR, f"{stock}.xlsx"))
            df['DATE'] = pd.to_datetime(df['DATE'])
            trades, equity, signals, plot_data, status = run_backtest_engine(df, strat)
            
            tot_tr = len(trades); win_tr = sum(1 for t in trades if t['Kar %'] > 0)
            rate = (win_tr/tot_tr*100) if tot_tr>0 else 0
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Fiyat", f"{df['CLOSING_TL'].iloc[-1]:.2f}"); m2.metric("Durum", status)
            m3.metric("Getiri", f"%{equity[-1]-100:.1f}"); m4.metric("Başarı", f"%{rate:.1f}")
            
            st_tab1, st_tab2 = st.tabs(["Grafik", "Geçmiş"])
            with st_tab1:
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
                fig.add_trace(go.Candlestick(x=df['DATE'], open=df['OPEN_TL'], high=df['HIGH_TL'], low=df['LOW_TL'], close=df['CLOSING_TL'], name='Fiyat'), row=1, col=1)
                if 'line1' in plot_data: fig.add_trace(go.Scatter(x=df['DATE'], y=plot_data['line1'], line=dict(color=plot_data.get('color1','orange'), width=2), name=plot_data.get('name1','Ind')), row=1, col=1)
                if 'line2' in plot_data: fig.add_trace(go.Scatter(x=df['DATE'], y=plot_data['line2'], line=dict(color=plot_data.get('color2','cyan'), width=2), name=plot_data.get('name2','Ind')), row=1, col=1)
                buys = [s for s in signals if s['type']=='buy']; sells = [s for s in signals if s['type']=='sell']
                fig.add_trace(go.Scatter(x=[x['date'] for x in buys], y=[x['price'] for x in buys], mode='markers', marker=dict(symbol='triangle-up', size=12, color='green'), name='AL'), row=1, col=1)
                fig.add_trace(go.Scatter(x=[x['date'] for x in sells], y=[x['price'] for x in sells], mode='markers', marker=dict(symbol='triangle-down', size=12, color='red'), name='SAT'), row=1, col=1)
                if 'VOLUME_TL' in df: fig.add_trace(go.Bar(x=df['DATE'], y=df['VOLUME_TL'], name='Hacim', marker_color='blue'), row=2, col=1)
                fig.update_layout(height=600, xaxis_rangeslider_visible=False); st.plotly_chart(fig, use_container_width=True)
            with st_tab2:
                if trades:
                    tdf = pd.DataFrame(trades)
                    tdf['Giriş'] = pd.to_datetime(tdf['Giriş']).dt.date
                    st.dataframe(tdf.style.format({'Giriş Fiyat': '{:.2f}', 'Çıkış Fiyat': '{:.2f}', 'Kar %': '{:.2f}%'}).applymap(lambda x: 'color: green' if isinstance(x,(int,float)) and x>0 else 'color: red' if isinstance(x,(int,float)) and x<0 else '', subset=['Kar %']), use_container_width=True)
                else: st.info("İşlem yok.")
    else: st.warning("Veri yok.")

# TAB 3: VERİ TABANI (GERİ GELDİ!)
with tab3:
    if file_count > 0:
        sel_file = st.selectbox("Dosya İncele:", sorted([os.path.basename(f) for f in excel_files_data]))
        if sel_file:
            path = os.path.join(DATA_DIR, sel_file)
            try:
                vdf = pd.read_excel(path)
                k1, k2, k3 = st.columns(3)
                k1.metric("Satır", len(vdf))
                if 'DATE' in vdf: k2.metric("Tarih", pd.to_datetime(vdf['DATE'].iloc[-1]).strftime('%Y-%m-%d'))
                if 'CLOSING_TL' in vdf: k3.metric("Fiyat", f"{vdf['CLOSING_TL'].iloc[-1]:.2f}")
                st.dataframe(vdf.tail(10), use_container_width=True)
            except: st.error("Okunamadı.")
    else: st.info("Veri yok.")

# TAB 4: ISI HARİTASI
with tab4: draw_heatmap()

# YAN MENÜ
with st.sidebar:
    st.header("📂 Raporlar")
    if st.button("🔄"): st.rerun()
    for f in glob.glob(os.path.join(BASE_DIR, "*.xlsx")):
        with open(f, "rb") as file: st.download_button(f"📥 {os.path.basename(f)}", data=file, file_name=os.path.basename(f))
    st.markdown("---")
    st.header("🗑️ Temizlik")
    with st.popover("⚠️ Verileri Sil"):
        if st.button("EVET, SİL", type="primary"):
            d = reset_system(); st.toast(f"{d} dosya silindi!"); time.sleep(1); st.rerun()


