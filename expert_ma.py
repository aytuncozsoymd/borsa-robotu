import pandas as pd
import numpy as np
import os
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from datetime import datetime, timedelta 

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(BASE_DIR, 'DATAson')
output_file = os.path.join(BASE_DIR, f'ExpertMaDash-{datetime.today().strftime("%Y-%m-%d")}.xlsx')

if not os.path.exists(data_folder):
    os.makedirs(data_folder)

# Basitleştirilmiş ExpertMA Fonksiyonları
def calculate_ema(data, period): return data.ewm(span=period, adjust=False).mean()
def calculate_ma_type(data, period):
    e1 = calculate_ema(data, period); e2 = calculate_ema(e1, period); e3 = calculate_ema(e2, period)
    return 3*e1 - 3*e2 + e3

def main():
    files = [f for f in os.listdir(data_folder) if f.endswith('.xlsx')]
    results = []
    
    print(f"ExpertMA taraması başlıyor... {len(files)} dosya.")

    for file in files:
        try:
            df = pd.read_excel(os.path.join(data_folder, file))
            if len(df) < 200: continue
            
            close = df['CLOSING_TL']
            curr = close.iloc[-1]
            score = 0
            
            # Basitleştirilmiş Puanlama (Hız ve uyumluluk için)
            indicators = [
                close.rolling(173).mean().iloc[-1], # ZLSMA Simüle
                close.rolling(120).mean().iloc[-1], # SMMA Simüle
                calculate_ma_type(close, 107).iloc[-1], # MA1
                calculate_ma_type(close, 120).iloc[-1], # MA2
                close.ewm(alpha=0.023).mean().iloc[-1], # M1 Simüle
                calculate_ma_type(close, 144).iloc[-1], # TEMA
                calculate_ema(close, 50).iloc[-1] # JMA Simüle
            ]
            
            for val in indicators:
                if not pd.isna(val) and curr > val: score += 1
            
            # Skor 5 üzerinden normalize edildi (Cloud hızı için)
            final_score = int((score / len(indicators)) * 14) 
            
            if final_score >= 10:
                results.append({'Hisse': file.replace('.xlsx',''), 'Fiyat': curr, 'Puan': final_score})
                
        except: continue

    if results:
        df_res = pd.DataFrame(results).sort_values(by='Puan', ascending=False)
        df_res.to_excel(output_file, index=False)
        print(f"ExpertMA Raporu kaydedildi: {output_file}")
    else:
        print("Sonuç bulunamadı.")

if __name__ == "__main__":
    main()