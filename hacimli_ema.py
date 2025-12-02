import pandas as pd
import numpy as np
import os
from datetime import datetime
from openpyxl import Workbook

# ==================== BULUT UYUMLU AYARLAR ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_DIR = BASE_DIR

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, f'EMA_Cross_Volume_{datetime.now().strftime("%Y-%m-%d-%H-%M")}.xlsx')

def main():
    print("Hacimli EMA Cross Taraması...")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx')]
    results = []
    ema_periods = [8, 13, 21, 55]
    
    for f in files:
        try:
            df = pd.read_excel(os.path.join(DATA_DIR, f))
            if len(df) < 60: continue
            
            close = df['CLOSING_TL']
            vol = df['VOLUME_TL']
            curr_p = close.iloc[-1]
            prev_p = close.iloc[-2]
            
            cross_count = 0
            for p in ema_periods:
                ema = close.ewm(span=p).mean()
                if prev_p < ema.iloc[-2] and curr_p > ema.iloc[-1]:
                    cross_count += 1
            
            if cross_count > 0:
                avg_vol = vol.rolling(20).mean().iloc[-1]
                vol_note = "HACİMLİ" if vol.iloc[-1] > avg_vol * 1.2 else "-"
                
                results.append({
                    'Hisse': f.replace('.xlsx',''),
                    'Kırılım Sayısı': cross_count,
                    'Hacim': vol_note
                })
        except: continue
        
    if results:
        df_res = pd.DataFrame(results).sort_values(by=['Kırılım Sayısı'], ascending=False)
        df_res.to_excel(OUTPUT_FILE, index=False)
        print(f"Dosya Kaydedildi: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()