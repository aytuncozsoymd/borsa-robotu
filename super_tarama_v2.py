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

# --- AKILLI VERİ YÜKLEYİCİ (Sorunu Çözen Kısım) ---
def load_stock_df(file_path):
    """Excel dosyasını okur ve sütun isimlerini standartlaştırır."""
    try:
        df = pd.read_excel(file_path)
        
        # Sütun isimlerini BÜYÜK HARF yap ve boşlukları sil
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Olası sütun isimlerini haritala
        col_map = {
            "DATE": ["DATE", "TARIH", "TARİH", "TIME", "DATE"],
            "CLOSING_TL": ["CLOSING_TL", "CLOSE", "KAPANIS", "KAPANIŞ", "SON"],
            "HIGH_TL": ["HIGH_TL", "HIGH", "YUKSEK", "YÜKSEK"],
            "LOW_TL": ["LOW_TL", "LOW", "DUSUK", "DÜŞÜK"],
            "VOLUME_TL": ["VOLUME_TL", "VOLUME", "HACIM", "VOL"]
        }
        
        # Sütunları standart isme çevir (CLOSING_TL vb.)
        for target, aliases in col_map.items():
            if target not in df.columns:
                for alias in aliases:
                    if alias in df.columns:
                        df.rename(columns={alias: target}, inplace=True)
                        break
        
        # Tarih formatını düzelt
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
            df = df.dropna(subset=["DATE"])
            df = df.sort_values("DATE")
            
        # Kritik sütun kontrolü
        if "CLOSING_TL" not in df.columns:
            return None
            
        return df
    except Exception as e:
        # Hata varsa (dosya bozuksa) None dön
        return None

# --- MATEMATİKSEL FONKSİYONLAR ---
def calculate_wma(series, length):
    weights = np.arange(1, length + 1)
    return series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)

def calculate_atr(df, length=14):
    # Eğer High/Low yoksa sadece Close kullan (Hata vermemesi için)
    if 'HIGH_TL' not in df.columns or 'LOW_TL' not in df.columns:
        return df['CLOSING_TL'].diff().abs().ewm(alpha=1/length, adjust=False).mean()
        
    high = df['HIGH_TL']
    low = df['LOW_TL']
    close = df['CLOSING_TL']
    tr = pd.concat([high - low, abs(high - close.shift(1)), abs(low - close.shift(1))], axis=1).max(axis=1)
    return tr.ewm(alpha=1/length, adjust=False).mean()

def calculate_custom_tema(series, period):
    ema1 = series.ewm(span=period, adjust=False).mean()
    ema2 = ema1.ewm(span=period, adjust=False).mean()
    ema3 = ema2.ewm(span=period, adjust=False).mean()
    return (3 * ema1) - (3 * ema2) + ema3

def calculate_rma(series, length):
    alpha = 1/length
    rma = np.zeros_like(series)
    rma[0] = series[0]
    for i in range(1, len(series)):
        rma[i] = alpha * series[i] + (1 - alpha) * rma[i-1]
    return rma

def calculate_rsi_mfi_combined(df, length=13):
    close = df['CLOSING_TL'].values
    
    # MFI için Volume lazım, yoksa sadece RSI kullan
    has_volume = 'VOLUME_TL' in df.columns and 'HIGH_TL' in df.columns
    
    change = np.diff(close, prepend=close[0])
    up_rma = calculate_rma(np.maximum(change, 0), length)
    down_rma = calculate_rma(-np.minimum(change, 0), length)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        rsi = 100 - (100 / (1 + up_rma / down_rma))
    rsi = np.nan_to_num(rsi, nan=50.0)

    if has_volume:
        high = df['HIGH_TL'].values
        low = df['LOW_TL'].values
        volume = df['VOLUME_TL'].values
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
    else:
        return rsi # Sadece RSI döndür

# --- ANALİZ FONKSİYONLARI ---

def analiz_hull_atr(df):
    if len(df) < 100: return "YETERSIZ", 0
    close = df['CLOSING_TL']
    prev = close.shift(1)
    wma10 = calculate_wma(close, 10)
    hull = calculate_wma(wma10, 89)
    atr = calculate_atr(df, 14)
    std = close.rolling(20).std()
    
    # is_sideways kontrolünü ATR varsa yap
    is_sideways = False
    if atr is not None:
        is_sideways = atr < (0.5 * std)

    # Basitleştirilmiş Koşul
    cond_buy = (close > hull) 
    if atr is not None:
        cond_buy = cond_buy & (close > (prev + atr)) & (~is_sideways)
        
    status = "NAKIT"; days = 0
    curr_st = 0 # 0:Nakit, 1:Al
    last_idx = 0
    
    # Son durum tespiti
    for i in range(len(df)):
        if cond_buy.iloc[i]:
            if curr_st != 1: curr_st=1; last_idx=i
        else:
            # Hull altına inerse sat
            if close.iloc[i] < hull.iloc[i]:
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
    
    start = max(1, len(df)-200)
    
    for i in range(start, len(df)):
        # TREF Basitleştirilmiş Mantık
        # RSI+MFI Trendi yukarı kesti ve EMA5 artıyor
        buy = (rsi_mfi[i]>50 and rsi_mfi[i-1]<=50 and e5_diff.iloc[i]>0)
        sell = (rsi_mfi[i]<40)
        
        if buy: in_pos=True; entry_idx=i
        elif sell: in_pos=False
        
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
    
    print(f"Toplam {len(files)} dosya bulundu. Analiz ediliyor...")
    
    for file in files:
        try:
            # YENİ YÜKLEYİCİYİ KULLAN
            df = load_stock_df(file)
            
            if df is None:
                # Dosya bozuksa veya veri yoksa atla
                continue
                
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
                    'Hull': format_durum(st_h, d_h),
                    'Bum': format_durum(st_b, d_b),
                    'Tref': format_durum(st_t, d_t),
                    'Raw_Score': score
                })
        except Exception as e:
            # Hata olsa bile durma, sonraki hisseye geç
            print(f"Hata ({file}): {e}")
            continue
        
    if sonuclar:
        df_final = pd.DataFrame(sonuclar).sort_values(by='Raw_Score', ascending=False).drop(columns=['Raw_Score'])
        
        # Dosya ismi
        fname = os.path.join(OUTPUT_FOLDER, f'SUPER_TARAMA_SURELI_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx')
        df_final.to_excel(fname, index=False)
        
        print(f"\n✅ Rapor Kaydedildi: {fname}")
        print(f"Toplam {len(df_final)} hisse AL sinyali üretti.")
    else:
        print("\n⚠️ Tarama bitti ancak hiçbir hissede AL sinyali bulunamadı.")
        print("Verilerin güncel olduğundan emin olun.")

if __name__ == "__main__":
    main()
