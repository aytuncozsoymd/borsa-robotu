import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font
from openpyxl.utils import get_column_letter
from sklearn.linear_model import LinearRegression
from scipy.stats import pearsonr
from tqdm import tqdm

# ==================== BULUT UYUMLU AYARLAR ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_DIR = BASE_DIR

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
# ==============================================================

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    if df.index.name and str(df.index.name).strip().upper() in {"DATE", "TARIH", "TARİH", "TIME"}:
        df = df.reset_index()
    col_aliases = {
        "DATE": ["DATE", "TARIH", "TARİH"],
        "CLOSING_TL": ["CLOSING_TL", "CLOSE", "KAPANIS"],
        "VOLUME_TL": ["VOLUME_TL", "VOLUME", "HACIM"]
    }
    for target, aliases in col_aliases.items():
        if target not in df.columns:
            for c in aliases:
                if c in df.columns: df.rename(columns={c: target}, inplace=True); break
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce", dayfirst=True)
        df = df.dropna(subset=["DATE"]).sort_values("DATE")
    return df

def load_stock_df(file_path: str) -> pd.DataFrame | None:
    try:
        df = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
    except: return None
    df = _normalize_columns(df)
    if "DATE" not in df.columns or "CLOSING_TL" not in df.columns or len(df) < 233: return None
    return df

def calculate_ema(data, period): return data.ewm(span=period, adjust=False).mean()
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).fillna(50)

def process_stocks(data_folder, output_folder):
    start_time = time.time()
    current_timestamp_str = datetime.now().strftime('%d-%m-%Y-%H-%M')
    excel_path = os.path.join(output_folder, f'Guclu_Trend_{current_timestamp_str}.xlsx')
    
    files = [f for f in os.listdir(data_folder) if f.lower().endswith(('.xlsx', '.csv'))]
    results = []
    
    for filename in tqdm(files, desc="Analiz", leave=False):
        df = load_stock_df(os.path.join(data_folder, filename))
        if df is None: continue

        ema_periods = [8, 13, 21, 34, 55, 89, 144, 233]
        for p in ema_periods: df[f'EMA{p}'] = calculate_ema(df['CLOSING_TL'], p)

        last_row = df.iloc[-1]
        closing = last_row['CLOSING_TL']
        
        # IDEAL UP KONTROL
        vals = [last_row[f'EMA{p}'] for p in ema_periods]
        is_ideal_up = (closing > vals[0]) and all(vals[i] > vals[i+1] for i in range(len(vals)-1))
        
        if is_ideal_up:
            # PEARSON HESABI
            y = df['CLOSING_TL'].tail(233)
            X = np.arange(len(y)).reshape(-1, 1)
            pearson = np.corrcoef(X.flatten(), y)[0, 1] if len(y)>1 else 0
            
            # RSI ve HACİM
            rsi = calculate_rsi(df['CLOSING_TL']).iloc[-1]
            vol_surge = False
            if 'VOLUME_TL' in df.columns:
                vol_surge = df['VOLUME_TL'].iloc[-1] > (df['VOLUME_TL'].rolling(10).mean().iloc[-1] * 1.2)
            
            # STRATEJİ ETİKETİ
            label = ""
            if pearson > 0.90 and rsi < 55: label = "🏆 TAM PUANLI"
            elif rsi < 35 and vol_surge: label = "🚀 TEPKİ ADAYI"
            elif pearson > 0.85 and rsi < 70: label = "💪 GÜÇLÜ TREND"
            
            if label:
                results.append({
                    'Hisse': os.path.splitext(filename)[0],
                    'Strateji': label,
                    'Fiyat': closing,
                    'Pearson (233)': round(pearson, 2),
                    'RSI': round(rsi, 2),
                    'Hacim Artışı': 'EVET' if vol_surge else 'HAYIR'
                })

    if results:
        df_res = pd.DataFrame(results).sort_values(by='Pearson (233)', ascending=False)
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_res.to_excel(writer, index=False, sheet_name='Guclu_Trend')
        print(f"Analiz Tamamlandı: {excel_path}")
    else:
        print("Uygun hisse bulunamadı.")

if __name__ == "__main__":
    process_stocks(DATA_DIR, OUTPUT_DIR)