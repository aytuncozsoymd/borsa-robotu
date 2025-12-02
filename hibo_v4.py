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

OUTPUT_FILE = os.path.join(OUTPUT_DIR, f'Hybrid_Scanner_V3_{datetime.now().strftime("%Y-%m-%d-%H-%M")}.xlsx')

def main():
    print("Hibrit V4 Taraması...")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx')]
    results = []
    
    for f in files:
        try:
            df = pd.read_excel(os.path.join(DATA_DIR, f))
            if len(df) < 233: continue
            
            close = df['CLOSING_TL']
            
            # EMA IDEAL UP
            emas = [close.ewm(span=p).mean().iloc[-1] for p in [8,13,21,34,55]]
            is_ideal = all(emas[i] > emas[i+1] for i in range(len(emas)-1))
            
            if is_ideal:
                results.append({
                    'Hisse': f.replace('.xlsx',''),
                    'Statü': 'IDEAL UP',
                    'Fiyat': close.iloc[-1]
                })
        except: continue
        
    if results:
        df_res = pd.DataFrame(results)
        df_res.to_excel(OUTPUT_FILE, index=False)
        print(f"Hibrit Raporu: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()