import os
import pandas as pd
import numpy as np
import glob
import math
from datetime import datetime
from tqdm import tqdm  # <--- EKSİK OLAN BU SATIR EKLENDİ

# --- BULUT UYUMLU KLASÖR AYARLARI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERI_KLASORU = os.path.join(BASE_DIR, 'DATAson')
KAYIT_KLASORU = BASE_DIR

if not os.path.exists(VERI_KLASORU):
    os.makedirs(VERI_KLASORU)

# --- YARDIMCI FONKSİYONLAR ---
def load_stock_df(file_path):
    try:
        df = pd.read_excel(file_path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        col_map = {"DATE": ["DATE"], "CLOSING_TL": ["CLOSING_TL","CLOSE"], "HIGH_TL": ["HIGH_TL","HIGH"], "LOW_TL": ["LOW_TL","LOW"], "VOLUME_TL": ["VOLUME_TL","VOL"]}
        for t, aliases in col_map.items():
            if t not in df.columns:
                for a in aliases:
                    if a in df.columns: df.rename(columns={a: t}, inplace=True); break
        
        # High/Low yoksa Close kopyala (Hata önlemek için)
        if "CLOSING_TL" in df.columns:
            if "HIGH_TL" not in df.columns: df["HIGH_TL"] = df["CLOSING_TL"]
            if "LOW_TL" not in df.columns: df["LOW_TL"] = df["CLOSING_TL"]
            
        return df
    except: return None

def calculate_wma(series, period):
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

# QnR Kernel Hesabı (Orijinal Mantık)
def get_kernel_point(prices, idx, h, r, x0):
    if idx < x0: return 0.0
    prices_slice = prices.iloc[idx-x0:idx+1].values
    weights = np.array([math.pow(1 + (math.pow(i, 2) / ((math.pow(h, 2) * 2 * r))), -r) for i in range(x0 + 1)])[::-1]
    
    current_weight = np.sum(prices_slice * weights)
    cumulative_weight = np.sum(weights)
    return current_weight / cumulative_weight if cumulative_weight != 0 else 0

# 1. MATLRNS
def calc_matlrns(df):
    try:
        src = (df['HIGH_TL'] + df['LOW_TL'] + df['CLOSING_TL']*2) / 4
        fast = src.ewm(span=8, adjust=False).mean()
        slow = src.ewm(span=21, adjust=False).mean()
        
        f_diff = fast.diff(9)
        s_diff = slow.diff(9)
        
        score = 0
        if f_diff.iloc[-1] > 0: score += 1
        elif f_diff.iloc[-1] < 0: score -= 1
        if s_diff.iloc[-1] > 0: score += 1
        elif s_diff.iloc[-1] < 0: score -= 1
        
        return score, "🟢 AL" if score==2 else ("🔴 SAT" if score==-2 else "NÖTR")
    except: return 0, "HATA"

# 2. TRENDLINER + QnR
def calc_trendliner(df):
    try:
        # Hız için son 20 barı hesapla
        close = df['CLOSING_TL']
        idx = len(df) - 1
        
        # TrendLiner
        atr = (df['HIGH_TL'] - df['LOW_TL']).ewm(alpha=1/2).mean()
        h1 = (df['HIGH_TL'] - (1.7 * atr)).rolling(68).max()
        
        trend_up = close.iloc[idx] > h1.iloc[idx]
        
        # QnR (Kernel)
        qnr_curr = get_kernel_point(close, idx, 23, 23, 23)
        qnr_prev = get_kernel_point(close, idx-1, 23, 23, 23)
        qnr_up = qnr_curr > qnr_prev
        
        if trend_up: return 2, "🟢 AL"
        elif not trend_up and not qnr_up: return -2, "🔴 SAT"
        return 0, "NÖTR"
    except: return 0, "-"

# 3. TREND ORTA VADE (Hull)
def calc_hull(df):
    try:
        close = df['CLOSING_TL']
        w1 = calculate_wma(close, 72)
        w2 = calculate_wma(close, 144)
        hma = calculate_wma(2*w1 - w2, 12)
        
        if hma.iloc[-1] > hma.iloc[-2]: return 1, "✅ Yükseliş"
        else: return -1, "🔻 Düşüş"
    except: return 0, "-"

def main():
    print("3+1 Süper Tarama (Orijinal) Başlıyor...")
    results = []
    files = glob.glob(os.path.join(VERI_KLASORU, "*.xlsx"))
    
    # tqdm burada kullanılıyor, import edildiği için artık hata vermez
    for f in tqdm(files):
        df = load_stock_df(f)
        if df is None or len(df) < 150: continue
        
        hisse = os.path.basename(f).replace('.xlsx','')
        
        s1, d1 = calc_matlrns(df)
        s2, d2 = calc_trendliner(df)
        s3, d3 = calc_hull(df)
        
        total = s1 + s2 + s3
        
        yorum = "NÖTR"
        if total >= 4: yorum = "🔥 SÜPER FIRSAT"
        elif total >= 2: yorum = "✅ GÜÇLÜ AL"
        
        if total > 0:
            results.append({
                'Hisse': hisse, 'SKOR': total, 'Yorum': yorum,
                'MATLRNS': d1, 'TrendLiner': d2, 'Hull_Orta': d3, 'Fiyat': df['CLOSING_TL'].iloc[-1]
            })
            
    if results:
        df_res = pd.DataFrame(results).sort_values(by='SKOR', ascending=False)
        out = os.path.join(KAYIT_KLASORU, f"Super_3_1_{datetime.now().strftime('%Y%m%d')}.xlsx")
        df_res.to_excel(out, index=False)
        print(f"✅ Kaydedildi: {out}")

if __name__ == "__main__":
    main()
