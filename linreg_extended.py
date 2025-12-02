import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from sklearn.linear_model import LinearRegression
from scipy.stats import pearsonr
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

# ==================== BULUT UYUMLU AYARLAR ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_DIR = BASE_DIR

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
# ==============================================================

# --- AKILLI VERİ OKUYUCU (Hata Önleyici) ---
def load_stock_df(file_path):
    try:
        df = pd.read_excel(file_path)
        # Sütunları standartlaştır
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        col_map = {
            "DATE": ["DATE", "TARIH", "TARİH", "TIME"],
            "CLOSING_TL": ["CLOSING_TL", "CLOSE", "KAPANIS", "KAPANIŞ", "SON"],
            "VOLUME_TL": ["VOLUME_TL", "VOLUME", "HACIM", "VOL"]
        }
        
        for target, aliases in col_map.items():
            if target not in df.columns:
                for alias in aliases:
                    if alias in df.columns:
                        df.rename(columns={alias: target}, inplace=True)
                        break
        
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
            df.dropna(subset=["DATE", "CLOSING_TL"], inplace=True)
            df.sort_values("DATE", inplace=True)
            
        if "CLOSING_TL" not in df.columns: return None
        if len(df) < 55: return None # Minimum veri kontrolü
        
        return df
    except: return None

# --- MATEMATİKSEL FONKSİYONLAR ---
def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return (100 - (100 / (1 + rs))).fillna(50)

def autofit_columns(worksheet):
    for column in worksheet.columns:
        max_length = 0
        column = [cell for cell in column]
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except: pass
        adjusted_width = (max_length + 2)
        worksheet.column_dimensions[column[0].column_letter].width = adjusted_width

# --- ANA ANALİZ MANTIĞI ---
def main():
    print(f"\n📏 LinReg Extended (Full Detay) Analizi Başlıyor...")
    
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx')]
    
    # 1. EMA ve PEARSON ANALİZİ
    results_ema = []
    ema_periods = [8, 13, 21, 34, 55, 89, 144, 233]
    pearson_periods = [55, 89, 144, 233, 377, 610, 987]
    all_pearson_data = {} # Strateji için sakla

    print(f"Toplam {len(files)} hisse taranıyor...")

    for file in files:
        df = load_stock_df(os.path.join(DATA_DIR, file))
        if df is None: continue
        
        hisse = file.replace('.xlsx', '')
        close = df['CLOSING_TL']
        curr_price = close.iloc[-1]
        
        # EMA Hesapla
        ema_vals = {}
        for p in ema_periods:
            df[f'EMA{p}'] = calculate_ema(close, p)
            ema_vals[p] = df[f'EMA{p}'].iloc[-1]
            
        # UP ve IDEAL UP Kontrolü
        is_up = all(curr_price > ema_vals[p] for p in ema_periods)
        
        # EMA'ların sıralı olması (8>13>21...)
        ema_ordered = True
        sorted_keys = sorted(ema_periods)
        for i in range(len(sorted_keys)-1):
            if ema_vals[sorted_keys[i]] <= ema_vals[sorted_keys[i+1]]:
                ema_ordered = False
                break
        
        is_ideal_up = (curr_price > ema_vals[8]) and ema_ordered
        
        status = ""
        if is_ideal_up: status = "IDEAL UP"
        elif is_up: status = "UP"
        
        # Pearson Hesapla
        stock_pearson = {}
        for p in pearson_periods:
            if len(df) >= p:
                y = close.tail(p).values
                X = np.arange(len(y)).reshape(-1, 1)
                corr = np.corrcoef(X.flatten(), y)[0, 1]
                stock_pearson[p] = corr
            else:
                stock_pearson[p] = np.nan
        
        all_pearson_data[hisse] = stock_pearson
        
        # Kayıt
        row = {
            'Hisse': hisse,
            'Fiyat': curr_price,
            'Durum': status,
        }
        # EMA Değerlerini Ekle
        for p in ema_periods: row[f'EMA{p}'] = round(ema_vals[p], 2)
        # Pearson Değerlerini Ekle
        for p in pearson_periods: row[f'Pearson_{p}'] = round(stock_pearson[p], 2) if not np.isnan(stock_pearson[p]) else "-"
            
        results_ema.append(row)

    # 2. KANAL ve STRATEJİ ANALİZİ
    results_strategy = []
    
    for file in files:
        df = load_stock_df(os.path.join(DATA_DIR, file))
        if df is None: continue
        hisse = file.replace('.xlsx', '')
        
        # Gerekli veriler
        close = df['CLOSING_TL']
        last_close = close.iloc[-1]
        
        # RSI
        rsi = calculate_rsi(close).iloc[-1]
        
        # Hacim Artışı
        vol_surge = False
        if 'VOLUME_TL' in df.columns:
            vol_avg = df['VOLUME_TL'].rolling(10).mean().iloc[-1]
            if df['VOLUME_TL'].iloc[-1] > vol_avg * 1.2:
                vol_surge = True
        
        # Kanal Analizi (En uzun vadeye bak - 233 gün)
        vade = 233
        if len(df) < vade: continue
        
        y = close.tail(vade).values
        X = np.arange(len(y)).reshape(-1, 1)
        model = LinearRegression().fit(X, y)
        pred = model.predict(X)
        
        std_dev = np.std(y - pred)
        upper = pred[-1] + (2 * std_dev)
        lower = pred[-1] - (2 * std_dev)
        
        # Kanal Konumu
        dist_up = (upper - last_close) / last_close * 100
        dist_down = (last_close - lower) / last_close * 100
        
        # Strateji Etiketi Belirle
        label = ""
        score = 0
        
        # Mevcut Pearson verisi
        p_val = all_pearson_data.get(hisse, {}).get(233, 0)
        if pd.isna(p_val): p_val = 0
        
        # EMA Durumu (Az önce hesaplamıştık ama buradan tekrar bakalım veya basitleştirelim)
        # Hız için tekrar EMA hesaplamak yerine results_ema listesinden çekmek daha doğru ama
        # kod karmaşası olmasın diye buradaki hisse için tekrar IDEAL UP var mı bakalım.
        # Basitçe:
        ema8 = calculate_ema(close, 8).iloc[-1]
        ema13 = calculate_ema(close, 13).iloc[-1]
        is_trend = (last_close > ema8 > ema13)
        
        # --- STRATEJİLER ---
        # 1. TAM PUANLI: Trend Var + Pearson Yüksek + RSI Düşük + Kanal Dibinde
        if is_trend and p_val > 0.90 and rsi < 55 and dist_down < 3:
            label = "🏆 TAM PUANLI"
            score = 3
            
        # 2. TEPKİ ADAYI: RSI Çok Düşük + Hacim Var
        elif rsi < 35 and vol_surge:
            label = "🚀 TEPKİ ADAYI"
            score = 2
            
        # 3. GÜÇLÜ TREND: Trend Var + Pearson Yüksek
        elif is_trend and p_val > 0.85 and rsi < 70:
            label = "💪 GÜÇLÜ TREND"
            score = 1
            
        if label:
            results_strategy.append({
                'Hisse': hisse,
                'STRATEJİ': label,
                'Fiyat': last_close,
                'Pearson (233)': round(p_val, 2),
                'RSI': round(rsi, 2),
                'Hacim Artışı': "EVET" if vol_surge else "-",
                'Alt Banda Uzaklık %': round(dist_down, 2),
                'Üst Banda Uzaklık %': round(dist_up, 2),
                'Skor': score
            })

    # 3. EXCEL KAYIT (Renkli ve Formatlı)
    if results_ema or results_strategy:
        fname = os.path.join(OUTPUT_DIR, f'LinReg_FULL_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx')
        
        with pd.ExcelWriter(fname, engine='openpyxl') as writer:
            # SAYFA 1: GÜÇLÜ TREND TAKİP (Stratejiler)
            if results_strategy:
                df_strat = pd.DataFrame(results_strategy).sort_values(by=['Skor', 'Pearson (233)'], ascending=False).drop(columns=['Skor'])
                df_strat.to_excel(writer, sheet_name='Guclu_Trend_Takip', index=False)
                
                ws = writer.sheets['Guclu_Trend_Takip']
                
                # Renklendirme
                gold_fill = PatternFill(start_color='FFD700', end_color='FFD700', fill_type='solid')
                green_fill = PatternFill(start_color='00B050', end_color='00B050', fill_type='solid')
                purple_fill = PatternFill(start_color='7030A0', end_color='7030A0', fill_type='solid')
                white_font = Font(color='FFFFFF', bold=True)
                black_font = Font(color='000000', bold=True)
                
                for row in ws.iter_rows(min_row=2):
                    cell_strat = row[1] # B Sütunu (STRATEJİ)
                    val = str(cell_strat.value)
                    
                    if "TAM PUANLI" in val:
                        cell_strat.fill = gold_fill
                        cell_strat.font = black_font
                    elif "TEPKİ" in val:
                        cell_strat.fill = green_fill
                        cell_strat.font = white_font
                    elif "GÜÇLÜ TREND" in val:
                        cell_strat.fill = purple_fill
                        cell_strat.font = white_font
                        
                autofit_columns(ws)

            # SAYFA 2: EMA ve PEARSON DETAY
            if results_ema:
                df_ema = pd.DataFrame(results_ema)
                df_ema.to_excel(writer, sheet_name='EMA_Pearson_Detay', index=False)
                
                ws2 = writer.sheets['EMA_Pearson_Detay']
                
                # IDEAL UP Renklendirme
                orange_fill = PatternFill(start_color='FFA500', end_color='FFA500', fill_type='solid')
                
                for row in ws2.iter_rows(min_row=2):
                    cell_status = row[2] # C Sütunu (Durum)
                    if cell_status.value == "IDEAL UP":
                        cell_status.fill = orange_fill
                        cell_status.font = white_font
                
                autofit_columns(ws2)
                
        print(f"✅ Detaylı Rapor Kaydedildi: {fname}")
        print("İçerik: 'Guclu_Trend_Takip' ve 'EMA_Pearson_Detay' sayfaları oluşturuldu.")
        
    else:
        print("Veri yetersizliğinden sonuç üretilemedi.")

if __name__ == "__main__":
    main()
