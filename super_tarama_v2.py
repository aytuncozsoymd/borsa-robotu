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

# --- VERİ YÜKLEYİCİ ---
def load_stock_df(file_path):
    try:
        df = pd.read_excel(file_path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        col_map = {
            "DATE": ["DATE", "TARIH", "TARİH", "TIME"],
            "CLOSING_TL": ["CLOSING_TL", "CLOSE", "KAPANIS", "KAPANIŞ"],
            "HIGH_TL": ["HIGH_TL", "HIGH"], "LOW_TL": ["LOW_TL", "LOW"],
            "VOLUME_TL": ["VOLUME_TL", "VOLUME", "VOL"]
        }
        for target, aliases in col_map.items():
            if target not in df.columns:
                for alias in aliases:
                    if alias in df.columns: df.rename(columns={alias: target}, inplace=True); break
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
            df.dropna(subset=["DATE"], inplace=True)
            df.sort_values("DATE", inplace=True)
        if "CLOSING_TL" not in df.columns: return None
        return df
    except: return None

# --- MATEMATİKSEL FONKSİYONLAR ---
def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calculate_atr(df, length=14):
    if 'HIGH_TL' not in df.columns or 'LOW_TL' not in df.columns:
        return df['CLOSING_TL'].diff().abs().ewm(alpha=1/length, adjust=False).mean()
    high = df['HIGH_TL']; low = df['LOW_TL']; close = df['CLOSING_TL']
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def calculate_custom_tema(series, period):
    e1 = series.ewm(span=period, adjust=False).mean()
    e2 = e1.ewm(span=period, adjust=False).mean()
    e3 = e2.ewm(span=period, adjust=False).mean()
    return (3 * e1) - (3 * e2) + e3

def calculate_rma(series, length):
    alpha = 1/length
    rma = np.zeros_like(series); rma[0] = series[0]
    for i in range(1, len(series)): rma[i] = alpha * series[i] + (1 - alpha) * rma[i-1]
    return rma

def calculate_rsi_mfi_combined(df, length=13):
    close = df['CLOSING_TL'].values
    has_volume = 'VOLUME_TL' in df.columns and 'HIGH_TL' in df.columns
    change = np.diff(close, prepend=close[0])
    up_rma = calculate_rma(np.maximum(change, 0), length)
    down_rma = calculate_rma(-np.minimum(change, 0), length)
    with np.errstate(divide='ignore', invalid='ignore'):
        rsi = 100 - (100 / (1 + up_rma / down_rma))
    rsi = np.nan_to_num(rsi, nan=50.0)

    if has_volume:
        tp = (df['HIGH_TL'].values + df['LOW_TL'].values + close) / 3
        mf = tp * df['VOLUME_TL'].values
        pos = np.where(tp > np.roll(tp, 1), mf, 0); neg = np.where(tp < np.roll(tp, 1), mf, 0); pos[0]=0; neg[0]=0
        pos_sum = pd.Series(pos).rolling(length).sum().fillna(0).values
        neg_sum = pd.Series(neg).rolling(length).sum().fillna(0).values
        with np.errstate(divide='ignore', invalid='ignore'): mfi = 100 - (100 / (1 + pos_sum / neg_sum))
        mfi = np.nan_to_num(mfi, nan=50.0)
        return (rsi + mfi) / 2
    return rsi

# --- ANALİZ FONKSİYONLARI ---

def analiz_hull_atr(df):
    if len(df) < 100: return "YETERSIZ", 0
    close = df['CLOSING_TL']
    prev = close.shift(1)
    
    # Göstergeler
    wma10 = calculate_wma(close, 10)
    hull = calculate_wma(wma10, 89)
    atr = calculate_atr(df, 14)
    std = close.rolling(20).std()
    
    is_sideways = False
    if atr is not None: is_sideways = atr < (0.5 * std)

    # AL Koşulu (Katı Kurallar)
    cond_buy = (close > hull) 
    if atr is not None:
        cond_buy = cond_buy & (close > (prev + atr)) & (~is_sideways)
    
    in_position = False
    last_entry_idx = 0
    
    # Sinyal Taraması
    for i in range(len(df)):
        if cond_buy.iloc[i]:
            if not in_position:
                in_position = True
                last_entry_idx = i
        elif close.iloc[i] < hull.iloc[i]: # Hull altına inince SAT (Pozisyondan çık)
            if in_position:
                in_position = False
                
    # --- SONUÇ MANTIĞI (GÜNCELLENDİ) ---
    if in_position:
        return "AL", len(df) - last_entry_idx
    else:
        # AL pozisyonunda değilsek Hull'a göre durumu belirle
        last_price = close.iloc[-1]
        last_hull = hull.iloc[-1]
        
        if last_price > last_hull:
            return "NAKIT", 0 # Fiyat Hull üstünde ama AL kriterleri (ATR vb.) oluşmamış
        else:
            return "SAT", 0   # Fiyat Hull altında

def analiz_bum(df):
    if len(df) < 80: return "YETERSIZ", 0
    ma1 = calculate_custom_tema(df['CLOSING_TL'], 34)
    ma2 = calculate_custom_tema(df['CLOSING_TL'], 68)
    if ma1.iloc[-1] > ma2.iloc[-1]:
        days = 0
        v1=ma1.values; v2=ma2.values
        for i in range(len(df)-1, -1, -1):
            if v1[i]>v2[i]: days+=1
            else: break
        return "AL", days
    return "SAT", 0

def analiz_tref(df):
    if len(df) < 60: return "YETERSIZ", 0
    rsi_mfi = calculate_rsi_mfi_combined(df)
    e5 = df['CLOSING_TL'].ewm(span=5).mean()
    diff = e5.diff()
    
    in_pos = False; idx = 0
    for i in range(max(1, len(df)-200), len(df)):
        if (rsi_mfi[i]>50 and rsi_mfi[i-1]<=50 and diff.iloc[i]>0): in_pos=True; idx=i
        elif (rsi_mfi[i]<40): in_pos=False
        
    if in_pos: return "AL", len(df)-idx
    return "SAT", 0

def format_durum(st, days):
    return f"AL ({days} gün)" if st == "AL" else st

def main():
    print(f"\n🔬 SUPER TARAMA V2 (Güncel Hull Mantığı)...")
    files = glob.glob(os.path.join(ROOT_PROJECT_FOLDER, '*.xlsx'))
    sonuclar = []
    
    for file in files:
        try:
            df = load_stock_df(file)
            if df is None: continue
            hisse = os.path.basename(file).replace('.xlsx', '')
            
            st_h, d_h = analiz_hull_atr(df)
            st_b, d_b = analiz_bum(df)
            st_t, d_t = analiz_tref(df)
            
            score = 0
            if st_h == "AL": score += 1
            if st_b == "AL": score += 1
            if st_t == "AL": score += 1
            
            # Hull durumuna göre 'NAKIT' veya 'SAT' yazması için hepsini kaydediyoruz
            # Ancak raporun çok şişmemesi için en azından 1 tane AL veya NAKIT (potansiyel) olanları alalım
            # Veya senin isteğin 'AL sinyali olanları görmek' ise score > 0 filtre kalsın.
            
            if score > 0 or st_h == "NAKIT": 
                sonuclar.append({
                    'Hisse': hisse,
                    'Skor': f"{score}/3",
                    'Hull': format_durum(st_h, d_h),
                    'Bum': format_durum(st_b, d_b),
                    'Tref': format_durum(st_t, d_t),
                    'Raw_Score': score
                })
        except: continue
        
    if sonuclar:
        df_final = pd.DataFrame(sonuclar).sort_values(by=['Raw_Score', 'Hull'], ascending=[False, True]).drop(columns=['Raw_Score'])
        fname = os.path.join(OUTPUT_FOLDER, f'SUPER_TARAMA_SURELI_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx')
        df_final.to_excel(fname, index=False)
        print(f"\n✅ Rapor Kaydedildi: {fname}")
    else:
        print("Kriterlere uyan hisse bulunamadı.")

if __name__ == "__main__":
    main()
