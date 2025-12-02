import os
import pandas as pd
import numpy as np
import glob
from datetime import datetime

# --- BULUT UYUMLU KLASÖR AYARLARI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERI_KLASORU = os.path.join(BASE_DIR, 'DATAson')
KAYIT_KLASORU = BASE_DIR

if not os.path.exists(VERI_KLASORU):
    os.makedirs(VERI_KLASORU)

def calculate_wma(series, period):
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def main():
    print("3+1 Süper Tarama Başlıyor...")
    results = []
    files = glob.glob(os.path.join(VERI_KLASORU, "*.xlsx"))
    
    for f in files:
        try:
            df = pd.read_excel(f)
            if len(df) < 150: continue
            
            close = df['CLOSING_TL']
            
            # 1. HULL MA (144) Trendi
            wma_half = calculate_wma(close, 72)
            wma_full = calculate_wma(close, 144)
            hma = calculate_wma(2 * wma_half - wma_full, 12)
            
            trend_score = 0
            if hma.iloc[-1] > hma.iloc[-2]: trend_score = 1
            elif hma.iloc[-1] < hma.iloc[-2]: trend_score = -1
            
            # 2. Basit Momentum
            mom = 1 if close.iloc[-1] > close.iloc[-20] else -1
            
            total_score = trend_score + mom
            
            if total_score > 0:
                results.append({
                    'Hisse': os.path.basename(f).replace('.xlsx',''),
                    'Fiyat': close.iloc[-1],
                    'Trend': 'YUKARI' if trend_score==1 else 'AŞAĞI',
                    'Skor': total_score
                })
        except: continue
        
    if results:
        df_out = pd.DataFrame(results).sort_values(by='Skor', ascending=False)
        out_path = os.path.join(KAYIT_KLASORU, "Super_Tarama_3_1.xlsx")
        df_out.to_excel(out_path, index=False)
        print(f"Kayıt Tamam: {out_path}")

if __name__ == "__main__":
    main()