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

# HİSSE LİSTESİ (Genişletilebilir)
hisseler = ["A1CAP","A1YEN","AEFES","AGESA","AGHOL","AHGAZ","AHSGY","AKBNK","AKCNS","AKFGY","AKSA","AKSEN","AKSGY","ALARK","ALBRK",
    "ALCAR","ALGYO","ALKA","ALVES","ANHYT","ANSGR","ARASE","ARDYZ","ARMGD","ASELS","ASTOR","ASUZU","ATATP","AYGAZ","BASGZ","BESLR",
    "BEYAZ","BFREN","BIGCH","BIMAS","BLUME","BMSCH","BMSTL","BOSSA","BRISA","BRKSN","BRSAN","BVSAN","CCOLA","CEMTS","CIMSA",
    "CLEBI","CRDFA","CWENE","DAGI","DERIM","DESA","DESPC","DGATE","DOAS","DOFER","DOHOL","EBEBK","ECILC","EDATA","EGEPO",
    "EGGUB","EGPRO","EKGYO","ELITE","ENERY","ENJSA","ENKAI","EREGL","EUPWR","EUREN","FMIZP","FORTE","FROTO","GARAN","GARFA",
    "GEDZA","GENIL","GENTS","GEREL","GESAN","GIPTA","GLCVY","GLRMK","GLYHO","GMTAS","GOLTS","GRSEL","GRTHO","GSDHO","GUBRF",
    "GWIND","HALKB","HLGYO","HTTBT","IMASM","INDES","INFO","INGRM","ISCTR","ISDMR","ISFIN","ISGYO","ISKPL","ISMEN","KATMR",
    "KCAER","KCHOL","KIMMR","KLKIM","KLMSN","KOZAL","KRDMA","KRDMB","KRDMD","KRGYO","KRONT","KRSTL","KTLEV","KUYAS","LIDER",
    "LIDFA","LILAK","LINK","LKMNH","LMKDC","LOGO","LYDYE","MACKO","MAGEN","MARBL","MEDTR","MEPET","MERIT","MGROS","MNDRS","MOBTL",
    "MPARK","MTRKS","NTGAZ","NTHOL","NUHCM","OBASE","ODAS","OFSYM","ONCSM","ORGE","OTKAR","OYAKC","OZKGY","OZSUB","OZYSR","PAGYO",
    "PAPIL","PASEU","PATEK","PENGD","PENTA","PETUN","PGSUS","PINSU","PLTUR","PNLSN","PRKME","RGYAS","RNPOL","RUZYE","RYGYO","RYSAS",
    "SAHOL","SANEL","SAYAS","SDTTR","SELEC","SISE","SKBNK","SMART","SOKM","SRVGY","SUNTK","SUWEN","TABGD","TARKM","TATEN","TATGD",
    "TAVHL","TBORG","TCELL","TGSAS","THYAO","TLMAN","TMPOL","TNZTP","TRGYO","TRILC","TSKB","TTKOM","TUCLK","TUKAS","TUPRS","TURSG","ULKER","ULUUN",
    "VAKBN","VAKFN","VERTU","YEOTK","YGGYO","YIGIT","YKBNK","YUNSA","YYLGD","ZRGYO","XU100","XBANK","XU030","XUTEK","XTRZM","XINSA",
    "XGMYO","XUHIZ","XTUMY","XU500","XKAGT","XHOLD","XFINK","XUMAL","XELKT","XMANA","XULAS","XAKUR","XUSIN","XILTM","XMADN","XTAST",
    "XBLSM","XTCRT","XSGRT","XGIDA","XKMYA","XTEKS","XK100","ALTIN","GLDTR","GMSTR]

def main():
    print("--- YFINANCE İLE VERİ İNDİRME (Kapanış Odaklı) ---")
    
    basarili = 0
    hatali = 0
    total = len(hisseler)
    
    # Zaman Kontrolü
    bugun = datetime.now().date()
    su_an = datetime.now().time()
    piyasa_kapanis_saati = dt_time(18, 15) # BIST Kapanış + 5 dk marj
    
    piyasa_kapali_mi = su_an > piyasa_kapanis_saati
    
    print(f"📅 Tarih: {bugun}")
    print(f"⏰ Saat: {su_an.strftime('%H:%M')}")
    if piyasa_kapali_mi:
        print("✅ Piyasa KAPALI. Bugünün kapanış verileri dahil edilecek.")
    else:
        print("⚠️ Piyasa AÇIK. Bugünün (tamamlanmamış) verileri SİLİNECEK, dünkü kapanış baz alınacak.")
    
    print("-" * 50)

    for i, sembol in enumerate(hisseler):
        try:
            yf_sembol = f"{sembol}.IS"
            
            # Veriyi çek
            df = yf.download(yf_sembol, period="2y", interval="1d", progress=False, auto_adjust=True)
            
            if df.empty:
                print(f"❌ {sembol}: Veri boş.")
                hatali += 1
                continue
            
            # Formatlama
            df.reset_index(inplace=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            df.rename(columns={
                'Date': 'DATE', 'Open': 'OPEN_TL', 'High': 'HIGH_TL', 
                'Low': 'LOW_TL', 'Close': 'CLOSING_TL', 'Volume': 'VOLUME_TL'
            }, inplace=True)
            
            df['DATE'] = pd.to_datetime(df['DATE'])
            
            # --- KRİTİK NOKTA: SON MUM KONTROLÜ ---
            if not df.empty:
                son_tarih = df['DATE'].iloc[-1].date()
                
                # Eğer son veri bugüne aitse VE piyasa henüz kapanmadıysa -> SİL
                if son_tarih == bugun and not piyasa_kapali_mi:
                    df = df[:-1] # Son satırı at
            
            # Kaydet
            filename = os.path.join(TARGET_FOLDER, f"{sembol}.xlsx")
            df.to_excel(filename, index=False)
            basarili += 1
            
            if i % 10 == 0:
                print(f"⬇️ {sembol} indirildi... ({i}/{total})")
                
        except Exception as e:
            hatali += 1
            continue

    print("-" * 30)
    print(f"TAMAMLANDI. İndirilen: {basarili}, Hatalı: {hatali}")

if __name__ == "__main__":
    main()
