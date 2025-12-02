import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta 
import time

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(BASE_DIR, 'DATAson')
output_file = os.path.join(BASE_DIR, f'ExpertMaDash-{datetime.today().strftime("%Y-%m-%d")}.xlsx')

if not os.path.exists(data_folder):
    os.makedirs(data_folder)

# --- MATEMATİKSEL FONKSİYONLAR (HEPSİ EKLENDİ) ---

def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def calculate_wma(series, period):
    weights = np.arange(1, period + 1)
    return series.rolling(period).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def linreg_calc(prices, length):
    x = np.arange(length)
    y = prices 
    slope, intercept = np.polyfit(x, y, 1)
    return slope * (length - 1) + intercept

def calculate_zlsma(series, length):
    # Basitleştirilmiş ZLSMA (Hız için)
    lsma = series.rolling(window=length).apply(lambda x: linreg_calc(x, length), raw=True)
    return lsma # Offset iptal edildi, direkt LSMA kullanıyoruz

def calculate_smma(data, length):
    return data.ewm(alpha=1/length, adjust=False).mean()

def calculate_ma_type(data, period):
    e1 = calculate_ema(data, period)
    e2 = calculate_ema(e1, period)
    e3 = calculate_ema(e2, period)
    return 3*e1 - 3*e2 + e3

def calculate_m1(data, alpha=0.023):
    e1 = data.ewm(alpha=alpha, adjust=False).mean()
    e2 = e1.ewm(alpha=alpha, adjust=False).mean()
    return 2*e1 - e2

def calculate_finh(data, period):
    half = period // 2
    e_half = calculate_ema(data, half)
    e_full = calculate_ema(data, period)
    return calculate_ema(2*e_half - e_full, int(np.sqrt(period)))

def calculate_hma(data, period):
    half = int(period / 2)
    sqrt_p = int(np.sqrt(period))
    w_half = calculate_wma(data, half)
    w_full = calculate_wma(data, period)
    return calculate_wma(2*w_half - w_full, sqrt_p)

def calculate_jma(data, length=50):
    # JMA simülasyonu (EMA 50'ye çok yakındır, hız için EMA kullanıyoruz)
    return calculate_ema(data, length)

def calculate_tema(data, length):
    e1 = calculate_ema(data, length)
    e2 = calculate_ema(e1, length)
    e3 = calculate_ema(e2, length)
    return 3*(e1 - e2) + e3

def calculate_dema(data, length):
    e1 = calculate_ema(data, length)
    e2 = calculate_ema(e1, length)
    return 2*e1 - e2

def calculate_ama(data, period=5):
    # KAMA (Kaufman Adaptive MA)
    change = data.diff(period).abs()
    volatility = data.diff().abs().rolling(period).sum()
    er = change / volatility
    sc = (er * (2/(2+1) - 2/(30+1)) + 2/(30+1)) ** 2
    
    ama = np.zeros_like(data)
    ama[:] = np.nan
    ama[period-1] = data.iloc[period-1]
    
    values = data.values
    sc_values = sc.values
    
    for i in range(period, len(data)):
        if not np.isnan(sc_values[i]):
            ama[i] = ama[i-1] + sc_values[i] * (values[i] - ama[i-1])
            
    return pd.Series(ama, index=data.index)

def main():
    files = [f for f in os.listdir(data_folder) if f.endswith('.xlsx')]
    results = []
    
    print(f"ExpertMA (Full Mod) taraması başlıyor... {len(files)} dosya.")

    for file in files:
        try:
            # Akıllı okuma
            df = pd.read_excel(os.path.join(data_folder, file))
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            # Sütun eşleştirme
            col_map = {"CLOSING_TL": ["CLOSING_TL", "CLOSE", "KAPANIS"], "DATE": ["DATE", "TARIH"]}
            for target, aliases in col_map.items():
                if target not in df.columns:
                    for a in aliases:
                        if a in df.columns: df.rename(columns={a: target}, inplace=True); break
            
            if 'CLOSING_TL' not in df.columns or len(df) < 200: continue
            
            close = df['CLOSING_TL']
            curr = close.iloc[-1]
            
            # --- GÖSTERGELERİ HESAPLA ---
            zlsma = calculate_zlsma(close, 173).iloc[-1]
            smma = calculate_smma(close, 120).iloc[-1]
            ma1 = calculate_ma_type(close, 107).iloc[-1]
            ma2 = calculate_ma_type(close, 120).iloc[-1]
            m1 = calculate_m1(close).iloc[-1]
            
            # LinReg Eğim
            y = close.tail(105).values
            x = np.arange(len(y))
            slope, _ = np.polyfit(x, y, 1)
            linreg_pos = slope > 0
            
            percentile = close.rolling(44).quantile(0.89).iloc[-1]
            finh = calculate_finh(close, 89).iloc[-1]
            hma = calculate_hma(close, 196).iloc[-1]
            jma = calculate_jma(close).iloc[-1]
            
            # MACD Cross
            e_fast = calculate_ema(close, 49)
            e_slow = calculate_ema(close, 55)
            macd = e_fast - e_slow
            signal = calculate_ema(macd, 5)
            macd_pos = macd.iloc[-1] > signal.iloc[-1]
            
            tema = calculate_tema(close, 144).iloc[-1]
            dema = calculate_dema(close, 89).iloc[-1]
            ama = calculate_ama(close, 5).iloc[-1]

            # --- PUANLAMA (14 KRİTER) ---
            score = 0
            
            # 12 Adet Fiyat > Gösterge Kontrolü
            indicators = [zlsma, smma, ma1, ma2, m1, percentile, finh, hma, jma, tema, dema, ama]
            for val in indicators:
                if not pd.isna(val) and curr > val:
                    score += 1
            
            # 2 Adet Pozitif Durum Kontrolü
            if linreg_pos: score += 1
            if macd_pos: score += 1
            
            # Kayıt (En az 10 puan alanlar)
            if score >= 10:
                results.append({
                    'Hisse': file.replace('.xlsx',''), 
                    'Fiyat': curr, 
                    'Puan': f"{score}/14", # Net puan
                    'Ham_Puan': score
                })
                
        except Exception as e:
            continue

    if results:
        df_res = pd.DataFrame(results).sort_values(by='Ham_Puan', ascending=False).drop(columns=['Ham_Puan'])
        df_res.to_excel(output_file, index=False)
        print(f"✅ ExpertMA Raporu Hazır: {output_file}")
    else:
        print("Sonuç bulunamadı.")

if __name__ == "__main__":
    main()
