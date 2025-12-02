import os
import pandas as pd
import numpy as np
import glob
import platform
from datetime import datetime
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_PROJECT_FOLDER = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_FOLDER = BASE_DIR

if not os.path.exists(ROOT_PROJECT_FOLDER):
    os.makedirs(ROOT_PROJECT_FOLDER)

# --- MATEMATİKSEL FONKSİYONLAR ---
def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calculate_atr(df, length=14):
    high = df['HIGH_TL']
    low = df['LOW_TL']
    close = df['CLOSING_TL']
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def calculate_custom_tema(series, period):
    ema1 = series.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    return (3 * ema1) - (3 * ema2) + e3

def calculate_rma(series, length):
    alpha = 1/length
    rma = np.zeros_like(series)
    rma[0] = series[0]
    for i in range(1, len(series)):
        rma[i] = alpha * series[i] + (1 - alpha) * rma[i-1]
    return rma

def calculate_rsi_mfi_combined(df, length=13):
    close = df['CLOSING_TL'].values
    high = df['HIGH_TL'].values
    low = df['LOW_TL'].values
    volume = df['VOLUME_TL'].values
    
    change = np.diff(close, prepend=close[0])
    up_rma = calculate_rma(np.maximum(change, 0), length)
    down_rma = calculate_rma(-np.minimum(change, 0), length)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        rsi = 100 - (100 / (1 + up_rma / down_rma))
    rsi = np.nan_to_num(rsi, nan=50.0)

    tp = (high + low + close) / 3
    mf = tp * volume
    pos = np.where(tp > np.roll(tp, 1), mf, 0)
    neg = np.where(tp < np.roll(tp, 1), mf, 0)
    pos[0]=0; neg[0]=0
    
    pos_sum = pd.Series(pos).rolling(length).sum().fillna(0).values
    neg_sum = pd.Series(neg).rolling(length).sum().fillna(0).values
    
    with np.errstate(divide='ignore', invalid='ignore'):
        mfi = 100 - (100 / (1 + pos_sum / neg_sum))
    mfi = np.nan_to_num(mfi, nan=50.0)
    
    return (rsi + mfi) / 2

# --- ANALİZ FONKSİYONLARI (SÜRE HESAPLAMALI) ---

def analiz_hull_atr(df):
    if len(df) < 100: return "YETERSIZ", 0
    close = df['CLOSING_TL']
    prev = close.shift(1)
    wma10 = calculate_wma(close, 10)
    hull = calculate_wma(wma10, 89)
    atr = calculate_atr(df, 14)
    std = close.rolling(20).std()
    
    cond_buy = (close > hull) & (close > (prev + atr)) & (atr > (0.5 * std))
    cond_sell = (close < hull) & (close < (prev - atr)) & (atr > (0.5 * std))
    
    status = "NAKIT"; days = 0
    curr_st = 0 # 0:Nakit, 1:Al
    last_idx = 0
    
    for i in range(len(df)):
        if cond_buy.iloc[i]:
            if curr_st != 1: curr_st=1; last_idx=i
        elif cond_sell.iloc[i]:
            if curr_st != 0: curr_st=0
            
    if curr_st == 1:
        status = "AL"
        days = len(df) - last_idx
        
    return status, days

def analiz_bum(df):
    if len(df) < 80: return "YETERSIZ", 0
    close = df['CLOSING_TL']
    ma1 = calculate_custom_tema(close, 34)
    ma2 = calculate_custom_tema(close, 68)
    
    status = "SAT"; days = 0
    if ma1.iloc[-1] > ma2.iloc[-1]:
        status = "AL"
        # Geriye doğru say
        vals1 = ma1.values; vals2 = ma2.values
        for i in range(len(df)-1, -1, -1):
            if vals1[i] > vals2[i]: days += 1
            else: break
            
    return status, days

def analiz_tref(df):
    if len(df) < 60: return "YETERSIZ", 0
    rsi_mfi = calculate_rsi_mfi_combined(df)
    e5 = df['CLOSING_TL'].ewm(span=5).mean()
    e5_diff = e5.diff()
    
    status = "SAT"; days = 0
    in_pos = False; entry_idx = 0
    
    # Hız için son 200 bar
    start = max(1, len(df)-200)
    
    for i in range(start, len(df)):
        buy = (rsi_mfi[i-1]<58 and rsi_mfi[i]>58 and rsi_mfi[i]>30 and e5_diff.iloc[i]>0)
        sell = (rsi_mfi[i]<30 and e5_diff.iloc[i]<0)
        
        if buy and not in_pos: in_pos=True; entry_idx=i
        elif sell and in_pos: in_pos=False
        
    if in_pos:
        status = "AL"
        days = len(df) - entry_idx
        
    return status, days

def format_durum(st, days):
    if st == "AL":
        return f"AL ({days} gün)"
    return st

def main():
    print(f"\n🔬 SUPER TARAMA V2 (Süre Analizli) Başlıyor...")
    files = glob.glob(os.path.join(ROOT_PROJECT_FOLDER, '*.xlsx'))
    sonuclar = []
    
    for file in files:
        try:
            df = pd.read_excel(file)
            hisse = os.path.basename(file).replace('.xlsx', '')
            
            st_h, d_h = analiz_hull_atr(df)
            st_b, d_b = analiz_bum(df)
            st_t, d_t = analiz_tref(df)
            
            score = 0
            if st_h == "AL": score += 1
            if st_b == "AL": score += 1
            if st_t == "AL": score += 1
            
            if score > 0:
                sonuclar.append({
                    'Hisse': hisse,
                    'Skor': f"{score}/3",
                    # BURASI ÖNEMLİ: Durum ve Süreyi Birleştirdik
                    'Hull': format_durum(st_h, d_h),
                    'Bum': format_durum(st_b, d_b),
                    'Tref': format_durum(st_t, d_t),
                    'Raw_Score': score # Sıralama için gizli kolon
                })
        except: continue
        
    if sonuclar:
        df_final = pd.DataFrame(sonuclar).sort_values(by='Raw_Score', ascending=False).drop(columns=['Raw_Score'])
        fname = os.path.join(OUTPUT_FOLDER, f'SUPER_TARAMA_SURELI_{datetime.now().strftime("%Y%m%d")}.xlsx')
        df_final.to_excel(fname, index=False)
        print(f"\n✅ Rapor Kaydedildi: {fname}")
        print("Not: Excel dosyasında 'AL (X gün)' formatında görebilirsiniz.")
    else:
        print("AL sinyali bulunamadı.")

if __name__ == "__main__":
    main()
