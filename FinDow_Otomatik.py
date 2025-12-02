import yfinance as yf
import pandas as pd
import os
import time
from datetime import datetime, timedelta, time as dt_time

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_FOLDER = os.path.join(BASE_DIR, 'DATAson')

if not os.path.exists(TARGET_FOLDER):
    os.makedirs(TARGET_FOLDER)

# HİSSE LİSTESİ
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
    print("--- YFINANCE İLE VERİ İNDİRME (GMT+3 Türkiye Saati) ---")
    
    basarili = 0
    hatali = 0
    total = len(hisseler)
    
    # Zaman Kontrolü (Türkiye Saatine Göre)
    # Sunucu UTC'dir, bu yüzden +3 saat ekliyoruz.
    su_an_tr = datetime.now() + timedelta(hours=3)
    bugun = su_an_tr.date()
    su_an_saat = su_an_tr.time()
    
    piyasa_kapanis_saati = dt_time(18, 15)
    
    piyasa_kapali_mi = su_an_saat > piyasa_kapanis_saati
    
    print(f"📅 TR Tarih: {bugun}")
    print(f"⏰ TR Saat: {su_an_saat.strftime('%H:%M')} | Piyasa: {'KAPALI' if piyasa_kapali_mi else 'AÇIK'}")
    
    if not piyasa_kapali_mi:
        print("⚠️ Piyasa henüz kapanmadı. Bugünün (tamamlanmamış) mumları silinecek.")

    for i, sembol in enumerate(hisseler):
        try:
            if sembol == "ALTIN.IN" or sembol == "ALTIN": yf_sembol = "GC=F"
            elif sembol.startswith("X"): yf_sembol = f"{sembol}.IS"
            elif sembol in ["GLDTR", "GMSTR"]: yf_sembol = f"{sembol}.IS"
            else: yf_sembol = f"{sembol}.IS"
            
            df = yf.download(yf_sembol, period="10y", interval="1d", progress=False, auto_adjust=True)
            
            if df.empty:
                print(f"❌ {sembol}: Veri boş.")
                hatali += 1
                continue
            
            df.reset_index(inplace=True)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            df.rename(columns={'Date':'DATE', 'Open':'OPEN_TL', 'High':'HIGH_TL', 'Low':'LOW_TL', 'Close':'CLOSING_TL', 'Volume':'VOLUME_TL'}, inplace=True)
            df['DATE'] = pd.to_datetime(df['DATE'])
            
            # --- SON MUM KONTROLÜ (TR Saatine Göre) ---
            if not df.empty:
                son_tarih = df['DATE'].iloc[-1].date()
                if son_tarih == bugun and not piyasa_kapali_mi:
                    df = df[:-1] 
            
            filename = os.path.join(TARGET_FOLDER, f"{sembol.replace('.IN','')}.xlsx")
            df.to_excel(filename, index=False)
            basarili += 1
            
            if i % 10 == 0: print(f"⬇️ {sembol} indirildi... ({i}/{total})")
                
        except:
            hatali += 1
            continue

    print("-" * 30)
    print(f"✅ İŞLEM TAMAMLANDI. (Başarılı: {basarili})")

if __name__ == "__main__":
    main()
