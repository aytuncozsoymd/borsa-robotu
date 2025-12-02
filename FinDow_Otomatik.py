import yfinance as yf
import pandas as pd
import os
import time
from datetime import datetime, time as dt_time

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_FOLDER = os.path.join(BASE_DIR, 'DATAson')

if not os.path.exists(TARGET_FOLDER):
    os.makedirs(TARGET_FOLDER)

# HİSSE LİSTESİ (Özet)
hisseler = [
    "A1CAP","A1YEN","AEFES","AGESA","AGHOL","AGYO","AHGAZ","AKBNK","AKFGY","AKGRT","AKMGY",
    "AKSEN","AKSUE","ALBRK","ALCAR","ALKA","ALTIN.IN","ANHYT","ANSGR","ARASE","ARDYZ","ASELS","ASTOR","ATAGY","ATATP","AVGYO",
    "AYDEM","AYEN","AYGAZ","BAGFS","BAKAB","BASGZ","BESLR","BEYAZ","BIGCH","BIMAS","BNTAS","BOSSA","BRKSN","BRLSM","BRSAN",
    "BRYAT","CCOLA","CEMTS","CIMSA","CLEBI","CRDFA","CWENE","DAPGM","DERIM","DESA","DESPC","DGATE","DOCO","DOFER","DOHOL",
    "EBEBK","ECZYT","EDATA","EGEPO","EGGUB","EGPRO","EKGYO","ELITE","EMKEL","ENERY","ENJSA","ENKAI","EREGL","EUPWR","EUREN",
    "FMIZP","FORTE","FROTO","FZLGY","GARAN","GARFA","GEDZA","GENIL","GENTS","GESAN","GIPTA","GLCVY","GLDTR","GLRMK","GLYHO",
    "GMSTR","GMTAS","GOKNR","GRSEL","GRTHO","GUBRF","GWIND","HALKB","HLGYO","HTTBT","HUNER","INDES","ISCTR","ISDMR","ISFIN",
    "ISGSY","ISGYO","ISKPL","ISMEN","KATMR","KCAER","KCHOL","KLKIM","KLMSN","KLSYN","KOZAA","KOZAL","KRDMA","KRDMD","KRONT",
    "KRPLS","KRSTL","LIDER","LIDFA","LILAK","LINK","LKMNH","LOGO","LYDYE","MACKO","MAGEN","MAKTK","MARBL","MAVI","MERIT",
    "METUR","MGROS","MIATK","MNDRS","MOBTL","MPARK","MRGYO","MTRKS","NTGAZ","NTHOL","NUHCM","OBASE","ODAS","OFSYM","ONCSM",
    "ORGE","OTKAR","OYAKC","OYYAT","OZGYO","OZSUB","PAGYO","PAPIL","PASEU","PATEK","PETUN","PGSUS","PINSU","PLTUR","PNLSN",
    "PRKME","PSDTC","QUAGR","RNPOL","RYGYO","RYSAS","SAHOL","SANEL","SAYAS","SDTTR","SELGD","SISE","SKBNK","SMART","SRVGY",
    "SUNTK","SUWEN","TABGD","TARKM","TATGD","TAVHL","TBORG","TCELL","TEZOL","THYAO","TLMAN","TMPOL","TNZTP","TRCAS","TRGYO",
    "TSKB","TTKOM","TUKAS","TUPRS","TURSG","ULKER","ULUUN","VAKBN","VERUS","YGGYO","YKBNK","YUNSA","YYLGD","ZRGYO",
    "XU100", "XBLSM", "XTCRT", "XSGRT", "XGIDA", "XKMYA", "XTEKS", "XK100"
]

def main():
    print("--- VERİ İNDİRME + TEMEL ANALİZ (10 Yıllık) ---")
    
    basarili = 0
    total = len(hisseler)
    temel_veriler = [] # F/K, PD/DD verilerini tutacak liste
    
    bugun = datetime.now().date()
    su_an = datetime.now().time()
    piyasa_kapanis_saati = dt_time(18, 15)
    piyasa_kapali_mi = su_an > piyasa_kapanis_saati
    
    print(f"Piyasa Durumu: {'KAPALI (Son Veri Dahil)' if piyasa_kapali_mi else 'AÇIK (Son Veri Silinecek)'}")

    for i, sembol in enumerate(hisseler):
        try:
            # Sembol Ayarı
            if sembol == "ALTIN.IN": yf_sembol = "GC=F"
            elif sembol.startswith("X"): yf_sembol = f"{sembol}.IS"
            elif sembol in ["GLDTR", "GMSTR"]: yf_sembol = f"{sembol}.IS"
            else: yf_sembol = f"{sembol}.IS"
            
            # 1. GEÇMİŞ VERİ (MUM) ÇEKME
            ticker = yf.Ticker(yf_sembol)
            df = ticker.history(period="10y", interval="1d", auto_adjust=True)
            
            if df.empty:
                print(f"❌ {sembol}: Veri boş.")
                continue
            
            # 2. TEMEL ANALİZ VERİSİ ÇEKME (Info)
            try:
                info = ticker.info
                # Verileri güvenli çek (yoksa 0 veya Tire koy)
                fk = info.get('trailingPE', 0)
                pddd = info.get('priceToBook', 0)
                sector = info.get('sector', 'Diğer')
                market_cap = info.get('marketCap', 0)
                daily_change = 0
                
                # Son gün kapanış ve değişim
                if len(df) >= 2:
                    close_now = df['Close'].iloc[-1]
                    close_prev = df['Close'].iloc[-2]
                    daily_change = ((close_now - close_prev) / close_prev) * 100
                
                temel_veriler.append({
                    'Hisse': sembol,
                    'Fiyat': round(df['Close'].iloc[-1], 2),
                    'FK': round(fk, 2) if fk else 0,
                    'PD_DD': round(pddd, 2) if pddd else 0,
                    'Sektor': sector,
                    'Piyasa_Degeri': market_cap,
                    'Degisim_Yuzde': round(daily_change, 2)
                })
            except:
                pass # Temel veri yoksa da devam et

            # 3. KAYDETME İŞLEMLERİ
            df.reset_index(inplace=True)
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None) # Saat dilimini temizle
            
            df.rename(columns={'Date': 'DATE', 'Open': 'OPEN_TL', 'High': 'HIGH_TL', 
                               'Low': 'LOW_TL', 'Close': 'CLOSING_TL', 'Volume': 'VOLUME_TL'}, inplace=True)
            
            # Son mum kontrolü
            if not df.empty:
                son_tarih = df['DATE'].iloc[-1].date()
                if son_tarih == bugun and not piyasa_kapali_mi:
                    df = df[:-1]
            
            filename = os.path.join(TARGET_FOLDER, f"{sembol.replace('.IN','')}.xlsx")
            df.to_excel(filename, index=False)
            basarili += 1
            
            if i % 10 == 0: print(f"⬇️ {sembol} işlendi... ({i}/{total})")
                
        except Exception as e:
            continue

    # --- TEMEL VERİLERİ ÖZET OLARAK KAYDET ---
    if temel_veriler:
        df_temel = pd.DataFrame(temel_veriler)
        summary_path = os.path.join(TARGET_FOLDER, "TEMEL_VERILER.xlsx")
        df_temel.to_excel(summary_path, index=False)
        print(f"📊 Temel Analiz Dosyası Oluşturuldu: {summary_path}")

    print("-" * 30)
    print(f"✅ İŞLEM TAMAMLANDI. Başarılı: {basarili}")

if __name__ == "__main__":
    main()
