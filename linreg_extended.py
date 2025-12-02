import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from openpyxl import Workbook
from sklearn.linear_model import LinearRegression

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_DIR = BASE_DIR

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def main():
    print("LinReg Extended Analizi...")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx')]
    results = []
    
    for f in files:
        try:
            df = pd.read_excel(os.path.join(DATA_DIR, f))
            if len(df) < 100: continue
            
            # Basit Pearson Kontrolü
            y = df['CLOSING_TL'].tail(100).values
            X = np.arange(len(y)).reshape(-1, 1)
            model = LinearRegression().fit(X, y)
            r_sq = model.score(X, y)
            
            if r_sq > 0.8:
                results.append({
                    'Hisse': f.replace('.xlsx',''),
                    'R-Kare (Trend Gücü)': round(r_sq, 2),
                    'Fiyat': df['CLOSING_TL'].iloc[-1]
                })
        except: continue
        
    if results:
        df_res = pd.DataFrame(results).sort_values(by='R-Kare (Trend Gücü)', ascending=False)
        fname = os.path.join(OUTPUT_DIR, 'LinReg_Results.xlsx')
        df_res.to_excel(fname, index=False)
        print(f"LinReg Kaydedildi: {fname}")

if __name__ == "__main__":
    main()