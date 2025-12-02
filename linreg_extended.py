import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
from sklearn.linear_model import LinearRegression
from zipfile import BadZipFile
from scipy.stats import pearsonr
from tqdm import tqdm

# ==================== BULUT UYUMLU AYARLAR ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'DATAson')
OUTPUT_DIR = BASE_DIR

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
# ==============================================================

# ==================== YARDIMCI FONKSİYONLAR ====================
def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().upper() for c in df.columns]
    if df.index.name and str(df.index.name).strip().upper() in {"DATE", "TARIH", "TARİH", "TIME", "ZAMAN"}:
        df = df.reset_index()
    
    col_aliases = {
        "DATE": ["DATE", "TARIH", "TARİH", "TIME", "ZAMAN"],
        "CLOSING_TL": ["CLOSING_TL", "CLOSE_TL", "KAPANIS_TL", "KAPANIŞ_TL", "KAPANIS", "KAPANIŞ", "CLOSE", "CLOSING"]
    }
    
    def ensure_col(target_name, candidates):
        nonlocal df
        if target_name not in df.columns:
            for c in candidates:
                c_up = str(c).strip().upper()
                if c_up in df.columns:
                    df = df.rename(columns={c_up: target_name})
                    return

    ensure_col("DATE", col_aliases["DATE"])
    ensure_col("CLOSING_TL", col_aliases["CLOSING_TL"])

    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce", dayfirst=True)
        df = df.dropna(subset=["DATE"])
    if "DATE" in df.columns:
        df = df.sort_values("DATE")
    return df

def load_stock_df(file_path: str) -> pd.DataFrame | None:
    try:
        if file_path.lower().endswith(".xlsx"):
            df = pd.read_excel(file_path, engine="openpyxl")
        elif file_path.lower().endswith(".csv"):
            df = pd.read_csv(file_path)
        else: return None
    except: return None

    df = _normalize_columns(df)
    if "DATE" not in df.columns or "CLOSING_TL" not in df.columns: return None
    if len(df) < 2: return None
    return df

def autofit_columns(worksheet, df_data, start_row=1, end_row=None, start_col=1, end_col=None):
    if df_data.empty: return
    columns_to_process = df_data.columns[start_col-1:end_col if end_col else len(df_data.columns)]
    for idx, col_name in enumerate(columns_to_process, start_col):
        max_length = len(str(col_name))
        column_values = df_data[col_name].astype(str)
        if not column_values.empty:
            max_length = max(max_length, column_values.apply(len).max())
        worksheet.column_dimensions[get_column_letter(idx)].width = max_length + 2

def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def add_report_info(sheet, total, filtered, max_row, report_date, report_duration):
    start_row = max_row + 2
    ratio_text = f"{filtered}/{total}"
    ratio_percent = f"({(filtered/total):.2%})" if total > 0 else "(0.00%)"
    info_data = [("Rapor Tarihi:", report_date), ("Rapor Süresi (dk:sn):", report_duration),
                 ("Taranan Hisse Sayısı:", total), ("Tablodaki Hisse Sayısı / Toplam:", ratio_text), ("Oran:", ratio_percent)]
    font = Font(size=9, color='666666', bold=True)
    for idx, (label, value) in enumerate(info_data):
        sheet.cell(row=start_row + idx, column=1, value=label).font = font
        sheet.cell(row=start_row + idx, column=2, value=value).font = font
    return sheet.max_row

def add_comparison_report_info(sheet, total, filtered, current_max_row, report_date, report_duration):
    start_row = current_max_row + 1
    ratio_text = f"{filtered}/{total}" if total > 0 else f"{filtered}/0"
    ratio_percent = f"({(filtered/total):.2%})" if total > 0 else "(0.00%)"
    info_data = [("Tablodaki Hisse Sayısı / Toplam:", ratio_text), ("Oran:", ratio_percent),
                 ("Rapor Tarihi:", report_date), ("Rapor Süresi (dk:sn):", report_duration), ("Taranan Hisse Sayısı:", total)]
    font = Font(size=9, color='666666', bold=True)
    for idx, (label, value) in enumerate(info_data):
        sheet.cell(row=start_row + idx, column=1, value=label).font = font
        sheet.cell(row=start_row + idx, column=2, value=value).font = font
    return sheet.max_row + 2

# ==================== ANA İŞLEM FONKSİYONLARI ====================

def process_stocks(data_folder, output_folder):
    start_time = time.time()
    current_timestamp_str = datetime.now().strftime('%d-%m-%Y-%H-%M')
    new_excel_filename = f'Ema_ve_Pearson_Sonuclari-{current_timestamp_str}.xlsx'
    excel_path = os.path.join(output_folder, new_excel_filename)
    
    results = []
    periods = [55, 144, 233, 377, 610, 987]
    all_results = {}
    total_scanned_stocks = 0
    
    # Stiller
    light_blue = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
    light_green = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
    header_fill = PatternFill(start_color='BFBFBF', end_color='BFBFBF', fill_type='solid')
    navy_fill = PatternFill(start_color='000080', end_color='000080', fill_type='solid')
    blue_fill = PatternFill(start_color='0000FF', end_color='0000FF', fill_type='solid')
    orange_fill = PatternFill(start_color='FFA500', end_color='FFA500', fill_type='solid')
    green_font = Font(color='008000', bold=True)
    red_font = Font(color='FF0000', bold=True)
    dark_orange_font = Font(color='FF8C00', bold=True)
    white_font = Font(color='FFFFFF', bold=True)

    # Önceki raporu bul (Kıyaslama için)
    prev_excel_path = None
    most_recent_prev = None
    for fname in os.listdir(output_folder):
        if fname.startswith('Ema_ve_Pearson_Sonuclari-') and fname.endswith('.xlsx') and fname != new_excel_filename:
            try:
                t_part = fname.replace('Ema_ve_Pearson_Sonuclari-', '').replace('.xlsx', '')
                f_time = datetime.strptime(t_part, '%d-%m-%Y-%H-%M')
                if (most_recent_prev is None or f_time > most_recent_prev):
                    most_recent_prev = f_time
                    prev_excel_path = os.path.join(output_folder, fname)
            except: continue

    prev_ideal_up_status = pd.DataFrame()
    prev_positive_pearson = pd.DataFrame()
    prev_com_data = pd.DataFrame()
    prev_results_full = pd.DataFrame()

    if prev_excel_path:
        try:
            prev_results_full = pd.read_excel(prev_excel_path, sheet_name='EMA_Sonuclari', engine='openpyxl')
            prev_ideal = prev_results_full[prev_results_full['Ideal Status'] == 'IDEAL UP'][['Stock Name', 'Ideal Status']].copy()
            prev_up = prev_results_full[(prev_results_full['Status'] == 'UP') & (prev_results_full['Ideal Status'] != 'IDEAL UP')][['Stock Name', 'Status']].rename(columns={'Status': 'Ideal Status'}).copy()
            prev_ideal_up_status = pd.concat([prev_ideal, prev_up], ignore_index=True)
            prev_ideal_up_status['Current_Status'] = prev_ideal_up_status['Ideal Status']
            prev_ideal_up_status = prev_ideal_up_status.drop(columns=['Ideal Status']).set_index('Stock Name')
            
            # Diğer sayfaları okumayı dene
            try: prev_positive_pearson = pd.read_excel(prev_excel_path, sheet_name='Pozitif_Pearson', index_col=0, engine='openpyxl')
            except: pass
            try: prev_com_data = pd.read_excel(prev_excel_path, sheet_name='Com144-233-377', engine='openpyxl')
            except: pass
        except: pass

    # ANALİZ DÖNGÜSÜ
    files = [f for f in os.listdir(data_folder) if f.lower().endswith(('.xlsx', '.csv'))]
    for filename in tqdm(files, desc="Analiz Yapılıyor", leave=False):
        total_scanned_stocks += 1
        df = load_stock_df(os.path.join(data_folder, filename))
        if df is None or len(df) < 233: continue

        for p in [8, 13, 21, 34, 55, 89, 144, 233]:
            df[f'EMA{p}'] = calculate_ema(df['CLOSING_TL'], p)
        
        last = df.iloc[-1]
        close = last['CLOSING_TL']
        
        all_above = all(close > last[f'EMA{p}'] for p in [8, 13, 21, 34, 55, 89, 144, 233])
        ideal_up = (close > last['EMA8'] > last['EMA13'] > last['EMA21'] > last['EMA34'] > last['EMA55'] > last['EMA89'] > last['EMA144'] > last['EMA233'])
        
        results.append({
            'Stock Name': os.path.splitext(filename)[0], 'Closing Price': close,
            'EMA8': last['EMA8'], 'EMA13': last['EMA13'], 'EMA21': last['EMA21'],
            'EMA34': last['EMA34'], 'EMA55': last['EMA55'], 'EMA89': last['EMA89'],
            'EMA144': last['EMA144'], 'EMA233': last['EMA233'],
            'Status': 'UP' if all_above else '', 'Ideal Status': 'IDEAL UP' if ideal_up else ''
        })
        
        # Pearson
        p_res = {}
        for p in periods:
            if len(df) >= p:
                y = df['CLOSING_TL'].tail(p)
                X = np.arange(p).reshape(-1, 1)
                p_res[f'{p} Gün'] = np.corrcoef(X.flatten(), y)[0, 1] if len(y)>1 else np.nan
            else: p_res[f'{p} Gün'] = np.nan
        all_results[os.path.splitext(filename)[0]] = p_res

    results_df = pd.DataFrame(results)
    
    # Rapor Süresi
    elapsed = time.time() - start_time
    report_duration = f"{int(elapsed//60):02d}:{int(elapsed%60):02d}"
    report_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # EXCEL YAZMA
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        # 1. EMA Sonuclari
        results_df.to_excel(writer, index=False, sheet_name='EMA_Sonuclari')
        ws = writer.sheets['EMA_Sonuclari']
        ws.freeze_panes = 'A2'
        
        for col in range(1, len(results_df.columns) + 1):
            ws.cell(row=1, column=col).fill = header_fill
            ws.cell(row=1
