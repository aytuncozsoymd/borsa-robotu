import os
import pandas as pd
import numpy as np
import glob
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

# Basitleştirilmiş Fonksiyonlar (Hız için)
def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calculate_custom_tema(series, period):
    e1 = series.ewm(span=period, adjust=False).mean()
    e2 = e1.ewm(span=period, adjust=False).mean()
    e3 = e2.ewm(span=period, adjust=False).mean()
    return (3 * e1) - (3 * e2) + e3

def main():
    print("3'lü Algo Taraması (Hull+BUM+TREF)...")
    files = glob.glob(os.path.join(ROOT_PROJECT_FOLDER, '*.xlsx'))
    results = []
    
    for file in files:
        try:
            df = pd.read_excel(file)
            if len(df) < 100: continue
            close = df['CLOSING_TL']
            
            # 1. HULL
            wma10 = calculate_wma(close, 10)
            hull = calculate_wma(wma10, 89)
            st_hull = "AL" if close.iloc[-1] > hull.iloc[-1] else "SAT"
            
            # 2. BUM
            ma1 = calculate_custom_tema(close, 34)
            ma2 = calculate_custom_tema(close, 68)
            st_bum = "AL" if ma1.iloc[-1] > ma2.iloc[-1] else "SAT"
            
            # 3. TREF (Basit EMA Cross Simülasyonu)
            e5 = close.ewm(span=5).mean()
            e20 = close.ewm(span=20).mean()
            st_tref = "AL" if e5.iloc[-1] > e20.iloc[-1] else "SAT"
            
            score = 0
            if st_hull == "AL": score += 1
            if st_bum == "AL": score += 1
            if st_tref == "AL": score += 1
            
            if score > 0:
                results.append({
                    'Hisse': os.path.basename(file).replace('.xlsx',''),
                    'Skor': f"{score}/3",
                    'Hull': st_hull,
                    'Bum': st_bum,
                    'Tref': st_tref,
                    'Raw_Score': score
                })
        except: continue
        
    if results:
        df_final = pd.DataFrame(results).sort_values(by='Raw_Score', ascending=False).drop(columns=['Raw_Score'])
        fname = os.path.join(OUTPUT_FOLDER, f'SUPER_TARAMA_SURELI_{datetime.now().strftime("%Y%m%d")}.xlsx')
        df_final.to_excel(fname, index=False)
        print(f"Rapor Kaydedildi: {fname}")

if __name__ == "__main__":
    main()