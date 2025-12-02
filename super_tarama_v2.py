import os
import pandas as pd
import numpy as np
import glob
from datetime import datetime
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

# --- AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_PROJECT_FOLDER = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_FOLDER = BASE_DIR
TEMEL_FILE = os.path.join(ROOT_PROJECT_FOLDER, "TEMEL_VERILER.xlsx") # Temel Veri Dosyası

if not os.path.exists(ROOT_PROJECT_FOLDER): os.makedirs(ROOT_PROJECT_FOLDER)

# --- YÜKLEYİCİLER ---
def load_fundamental_data():
    """Temel Analiz verilerini yükler (FK, PD/DD)"""
    try:
        if os.path.exists(TEMEL_FILE):
            df = pd.read_excel(TEMEL_FILE)
            # Hızlı erişim için Hisse adını index yapalım
            df.set_index('Hisse', inplace=True)
            return df
        return None
    except: return None

def load_stock_df(file_path):
    try:
        df = pd.read_excel(file_path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        col_map = {"DATE": ["DATE","TARIH"], "CLOSING_TL": ["CLOSING_TL","CLOSE","KAPANIS"], "HIGH_TL": ["HIGH_TL","HIGH"], "LOW_TL": ["LOW_TL","LOW"], "VOLUME_TL": ["VOLUME_TL","VOL"]}
        for t, a in col_map.items():
            if t not in df.columns:
                for alias in a:
                    if alias in df.columns: df.rename(columns={alias: t}, inplace=True); break
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
            df.dropna(subset=["DATE", "CLOSING_TL"], inplace=True)
            df.sort_values("DATE", inplace=True)
        if "CLOSING_TL" not in df.columns: return None
        return df
    except: return None

# --- TEKNİK FONKSİYONLAR (Aynı Kalıyor) ---
def calculate_wma(s, l): weights=np.arange(1,l+1); return s.rolling(l).apply(lambda x: np.dot(x, weights)/weights.sum(), raw=True)
def calculate_custom_tema(s, p): e1=s.ewm(span=p).mean(); e2=e1.ewm(span=p).mean(); e3=e2.ewm(span=p).mean(); return 3*e1-3*e2+e3
def calculate_rma(s, l): alpha=1/l; rma=np.zeros_like(s); rma[0]=s[0]; [rma.__setitem__(i, alpha*s[i]+(1-alpha)*rma[i-1]) for i in range(1,len(s))]; return rma
def calculate_rsi_mfi_combined(df, l=13):
    close=df['CLOSING_TL'].values; change=np.diff(close, prepend=close[0])
    up=calculate_rma(np.maximum(change,0),l); down=calculate_rma(-np.minimum(change,0),l)
    with np.errstate(divide='ignore'): rsi=100-(100/(1+up/down))
    rsi=np.nan_to_num(rsi, nan=50.0)
    if 'VOLUME_TL' in df:
        tp=(df['HIGH_TL'].values+df['LOW_TL'].values+close)/3; mf=tp*df['VOLUME_TL'].values
        pos=np.where(tp>np.roll(tp,1),mf,0); neg=np.where(tp<np.roll(tp,1),mf,0); pos[0]=neg[0]=0
        pos_s=pd.Series(pos).rolling(l).sum().values; neg_s=pd.Series(neg).rolling(l).sum().values
        with np.errstate(divide='ignore'): mfi=100-(100/(1+pos_s/neg_s))
        return (rsi + np.nan_to_num(mfi, nan=50.0)) / 2
    return rsi

# --- ANALİZLER ---
def analiz_hull(df):
    if len(df)<100: return "YETERSIZ",0
    c=df['CLOSING_TL']; h=calculate_wma(calculate_wma(c,10),89)
    if c.iloc[-1]>h.iloc[-1]: return "AL", 1
    return "SAT", 0

def analiz_bum(df):
    if len(df)<80: return "YETERSIZ",0
    m1=calculate_custom_tema(df['CLOSING_TL'],34); m2=calculate_custom_tema(df['CLOSING_TL'],68)
    if m1.iloc[-1]>m2.iloc[-1]: return "AL", 1
    return "SAT", 0

def analiz_tref(df):
    if len(df)<60: return "YETERSIZ",0
    rm=calculate_rsi_mfi_combined(df); e5=df['CLOSING_TL'].ewm(span=5).mean().diff()
    if rm[-1]>50 and e5.iloc[-1]>0: return "AL", 1
    return "SAT", 0

def main():
    print(f"\n🔬 SUPER TARAMA V3 (Temel Analiz Destekli)...")
    files = glob.glob(os.path.join(ROOT_PROJECT_FOLDER, '*.xlsx'))
    sonuclar = []
    
    # Temel Verileri Yükle
    df_temel = load_fundamental_data()
    
    for file in files:
        try:
            if "TEMEL_VERILER" in file: continue # Özet dosyasını atla
            df = load_stock_df(file)
            hisse = os.path.basename(file).replace('.xlsx', '')
            
            if df is None: continue
            
            h, _ = analiz_hull(df)
            b, _ = analiz_bum(df)
            t, _ = analiz_tref(df)
            
            score = 0
            if h=="AL": score+=1
            if b=="AL": score+=1
            if t=="AL": score+=1
            
            # Temel Verileri Çek
            fk, pddd = "-", "-"
            if df_temel is not None and hisse in df_temel.index:
                fk = df_temel.loc[hisse, 'FK']
                pddd = df_temel.loc[hisse, 'PD_DD']
            
            sonuclar.append({
                'Hisse': hisse,
                'Skor': f"{score}/3",
                'Hull': h, 'Bum': b, 'Tref': t,
                'F/K': fk, 'PD/DD': pddd, # Yeni Sütunlar
                'Raw_Score': score
            })
        except: continue
        
    if sonuclar:
        df_fin = pd.DataFrame(sonuclar).sort_values(by='Raw_Score', ascending=False).drop(columns=['Raw_Score'])
        fname = os.path.join(OUTPUT_FOLDER, f'SUPER_TARAMA_TEMEL_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx')
        df_fin.to_excel(fname, index=False)
        print(f"✅ Rapor Hazır: {fname}")

if __name__ == "__main__":
    main()
