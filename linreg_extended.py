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
from tqdm import tqdm
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

# --- YARDIMCI FONKSİYONLAR ---
def load_stock_df(file_path):
    try:
        df = pd.read_excel(file_path)
        df.columns = [str(c).strip().upper() for c in df.columns]
        col_map = {
            "DATE": ["DATE", "TARIH", "TARİH"], 
            "CLOSING_TL": ["CLOSING_TL", "CLOSE", "KAPANIS", "KAPANIŞ"],
            "VOLUME_TL": ["VOLUME_TL", "VOL", "HACIM"]
        }
        for t, aliases in col_map.items():
            if t not in df.columns:
                for a in aliases:
                    if a in df.columns: df.rename(columns={a: t}, inplace=True); break
        
        if "DATE" in df.columns:
            df["DATE"] = pd.to_datetime(df["DATE"], errors='coerce')
            df.dropna(subset=["DATE", "CLOSING_TL"], inplace=True)
            df.sort_values("DATE", inplace=True)
            
        if "CLOSING_TL" not in df.columns or len(df) < 55: return None
        return df
    except: return None

def calculate_ema(data, period): return data.ewm(span=period, adjust=False).mean()

def autofit(ws):
    for column in ws.columns:
        length = 0
        col_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > length: length = len(str(cell.value))
            except: pass
        ws.column_dimensions[col_letter].width = min(length + 2, 50)

def add_report_info(sheet, total, filtered, max_row, report_date, report_duration):
    start = max_row + 2
    font = Font(size=9, color='666666', bold=True)
    info = [
        ("Rapor Tarihi:", report_date),
        ("Süre:", report_duration),
        ("Taranan:", total),
        ("Filtrelenen:", f"{filtered}/{total}")
    ]
    for i, (k, v) in enumerate(info):
        sheet.cell(row=start+i, column=1, value=k).font = font
        sheet.cell(row=start+i, column=2, value=v).font = font

# --- İŞLEM FONKSİYONLARI ---

def process_stocks(data_folder, output_folder):
    start_time = time.time()
    
    # Dosya ismi
    ts = datetime.now().strftime('%d-%m-%Y-%H-%M')
    excel_path = os.path.join(output_folder, f'Ema_ve_Pearson_Sonuclari-{ts}.xlsx')
    
    files = [f for f in os.listdir(data_folder) if f.endswith('.xlsx')]
    
    results = []
    all_results = {} # Pearson verileri için
    
    periods = [55, 144, 233, 377, 610, 987]
    ema_list = [8, 13, 21, 34, 55, 89, 144, 233]
    total_scanned = 0

    print("Hisseler taranıyor...")
    for f in tqdm(files):
        df = load_stock_df(os.path.join(data_folder, f))
        if df is None: continue
        total_scanned += 1
        
        hisse = f.replace('.xlsx', '')
        close = df['CLOSING_TL']
        curr = close.iloc[-1]
        
        # EMA Hesapla
        emas = {p: calculate_ema(close, p).iloc[-1] for p in ema_list}
        
        # Durum Analizi
        vals = list(emas.values())
        # Ideal Up: Fiyat > 8 > 13 ... > 233
        is_ideal = (curr > vals[0]) and all(vals[i] > vals[i+1] for i in range(len(vals)-1))
        # Up: Fiyat tüm ortalamaların üstünde
        is_up = all(curr > v for v in vals)
        
        status = ""
        if is_ideal: status = "IDEAL UP"
        elif is_up: status = "UP"
        
        # Pearson Analizi
        p_res = {}
        for p in periods:
            if len(df) >= p:
                y = close.tail(p).values
                X = np.arange(p).reshape(-1, 1)
                p_res[f'{p} Gün'] = np.corrcoef(X.flatten(), y)[0, 1]
            else:
                p_res[f'{p} Gün'] = np.nan
        all_results[hisse] = p_res
        
        # Listeye Ekle
        row = {'Stock Name': hisse, 'Closing Price': curr, 'Status': 'UP' if is_up else '', 'Ideal Status': status}
        for p in ema_list: row[f'EMA{p}'] = emas[p]
        results.append(row)

    # DataFrame Oluştur
    df_res = pd.DataFrame(results)
    
    elapsed = time.time() - start_time
    dur_str = f"{int(elapsed//60):02d}:{int(elapsed%60):02d}"
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Excel'e Yazma
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        # SHEET 1: EMA SONUÇLARI
        df_res.to_excel(writer, index=False, sheet_name='EMA_Sonuclari')
        ws = writer.sheets['EMA_Sonuclari']
        ws.freeze_panes = 'A2'
        
        # Renkler
        header_fill = PatternFill(start_color='BFBFBF', fill_type='solid')
        blue_fill = PatternFill(start_color='0000FF', fill_type='solid')
        orange_fill = PatternFill(start_color='FFA500', fill_type='solid')
        white_font = Font(color='FFFFFF', bold=True)
        
        # Başlık Rengi
        for cell in ws[1]: 
            cell.fill = header_fill; cell.font = Font(bold=True)
            
        # Satır Boyama
        for row in ws.iter_rows(min_row=2):
            # UP ise Mavi
            if row[10].value == 'UP': # Status kolonu
                for cell in row: cell.fill = blue_fill; cell.font = white_font
            
            # Ideal UP ise Turuncu (Son kolon)
            if row[11].value == 'IDEAL UP':
                row[11].fill = orange_fill; row[11].font = white_font
                
        autofit(ws)
        add_report_info(ws, total_scanned, len(df_res), ws.max_row, date_str, dur_str)
        
        # SHEET 2: PEARSON TÜMÜ
        pd.DataFrame(all_results).T.to_excel(writer, sheet_name='Pearson_Sonuclari')
        autofit(writer.sheets['Pearson_Sonuclari'])
        
        # SHEET 3: POZİTİF PEARSON (Hata veren kısım düzeltildi)
        pos_pearson = {}
        for h, vals in all_results.items():
            # Tüm değerler pozitif mi?
            if all((pd.notna(v) and v > 0) for v in vals.values()):
                pos_pearson[h] = vals
                
        if pos_pearson:
            pd.DataFrame(pos_pearson).T.to_excel(writer, sheet_name='Pozitif_Pearson')
            autofit(writer.sheets['Pozitif_Pearson'])
            
        # SHEET 4: RAPOR UPD (Bulut için basitleştirildi)
        ws_upd = writer.book.create_sheet("Rapor_Upd")
        ws_upd.cell(row=1, column=1, value="Bulut versiyonunda geçmiş kıyaslama kapalıdır.").font = Font(bold=True)

    return excel_path

def process_channels(data_folder, main_excel_path):
    vades = [144, 233, 377, 610]
    res = []
    
    files = [f for f in os.listdir(data_folder) if f.endswith('.xlsx')]
    for f in tqdm(files, desc="Kanal Analizi"):
        df = load_stock_df(os.path.join(data_folder, f))
        if df is None: continue
        
        for v in vades:
            if len(df) < v: continue
            
            sub = df.tail(v)
            y = sub['CLOSING_TL'].values
            X = np.arange(len(y)).reshape(-1, 1)
            
            model = LinearRegression().fit(X, y)
            pred = model.predict(X)
            std = np.std(y - pred)
            
            last = df['CLOSING_TL'].iloc[-1]
            upper = pred[-1] + 2*std
            lower = pred[-1] - 2*std
            
            diff_up = (upper - last)/last*100
            diff_down = (last - lower)/last*100
            
            pearson = np.corrcoef(sub['CLOSING_TL'], pred)[0, 1]
            if model.coef_[0] < 0: pearson = -pearson
            
            res.append({
                'Hisse': f.replace('.xlsx',''), 'Vade': v,
                'Fiyat': last, 'Pearson': pearson,
                'Üst Fark %': diff_up, 'Alt Fark %': diff_down
            })
            
    df_ch = pd.DataFrame(res)
    
    # Excel'e Ekleme
    with pd.ExcelWriter(main_excel_path, engine='openpyxl', mode='a') as writer:
        df_ch.to_excel(writer, sheet_name='Kanal_Ekstra', index=False)
        
        # ListeBaşı Sayfası (Filtreli)
        lb = df_ch[
            (df_ch['Pearson'] > 0.9) & 
            ((df_ch['Üst Fark %'] <= 2) | (df_ch['Alt Fark %'] <= 2))
        ]
        
        if not lb.empty:
            lb.to_excel(writer, sheet_name='ListeBaşı', index=False)
            ws = writer.sheets['ListeBaşı']
            
            red_fill = PatternFill(start_color='FF0000', fill_type='solid')
            navy_fill = PatternFill(start_color='000080', fill_type='solid')
            white_font = Font(color='FFFFFF', bold=True)
            
            for row in ws.iter_rows(min_row=2):
                # Varsayılan Lacivert
                for cell in row: 
                    cell.fill = navy_fill; cell.font = white_font
                
                # Alt banda yakınsa (Alım Fırsatı) Kırmızı yap
                # 'Alt Fark %' kolonu indeks 6 (G sütunu)
                try:
                    if row[6].value is not None and float(row[6].value) <= 2:
                        for cell in row: cell.fill = red_fill
                except: pass

if __name__ == "__main__":
    print("LinReg Extended Analizi Başlıyor...")
    path = process_stocks(DATA_DIR, OUTPUT_DIR)
    process_channels(DATA_DIR, path)
    print(f"✅ İŞLEM TAMAMLANDI: {path}")
