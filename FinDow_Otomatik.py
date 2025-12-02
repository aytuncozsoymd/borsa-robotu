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

# --- HİSSE LİSTESİ (Dosyanızdaki Liste - Düzeltilmiş) ---
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
    "XBLSM","XTCRT","XSGRT","XGIDA","XKMYA","XTEKS","XK100","ALTIN","GLDTR","GMSTR"]

def main():
    print("--- YFINANCE İLE VERİ İNDİRME (Orijinal Liste - 10 Yıllık) ---")
    
    basarili = 0
    hatali = 0
    total = len(hisseler)
    
    # Zaman Kontrolü (18:15 Kuralı)
    bugun = datetime.now().date()
    su_an = datetime.now().time()
    piyasa_kapanis_saati = dt_time(18, 15)
    
    piyasa_kapali_mi = su_an > piyasa_kapanis_saati
    
    print(f"📅 Tarih: {bugun}")
    print(f"⏰ Saat: {su_an.strftime('%H:%M')} | Piyasa: {'KAPALI' if piyasa_kapali_mi else 'AÇIK'}")
    
    if not piyasa_kapali_mi:
        print("⚠️ Uyarı: Piyasa açık olduğu için bugünün (tamamlanmamış) verileri silinecek.")

    for i, sembol in enumerate(hisseler):
        try:
            # Özel Sembol Ayarları
            if sembol == "ALTIN.IN" or sembol == "ALTIN":
                yf_sembol = "GC=F" # Ons Altın Vadeli
            elif sembol.startswith("X"): # Endeksler (XU100, XBLSM vb.)
                yf_sembol = f"{sembol}.IS"
            elif sembol in ["GLDTR", "GMSTR"]: # Fonlar
                yf_sembol = f"{sembol}.IS"
            else:
                yf_sembol = f"{sembol}.IS" # Normal Hisseler
            
            # Veriyi çek (10 Yıllık)
            df = yf.download(yf_sembol, period="10y", interval="1d", progress=False, auto_adjust=True)
            
            if df.empty:
                print(f"❌ {sembol}: Veri boş.")
                hatali += 1
                continue
            
            # Formatlama (MultiIndex Düzeltme)
            df.reset_index(inplace=True)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Sütun İsimlerini Sisteme Uyarlama
            df.rename(columns={
                'Date': 'DATE', 'Open': 'OPEN_TL', 'High': 'HIGH_TL', 
                'Low': 'LOW_TL', 'Close': 'CLOSING_TL', 'Volume': 'VOLUME_TL'
            }, inplace=True)
            
            df['DATE'] = pd.to_datetime(df['DATE'])
            
            # --- KRİTİK: SON MUM KONTROLÜ ---
            if not df.empty:
                son_tarih = df['DATE'].iloc[-1].date()
                # Eğer son veri bugüne aitse VE piyasa henüz kapanmadıysa -> SİL
                if son_tarih == bugun and not piyasa_kapali_mi:
                    df = df[:-1] 
            
            # Kaydet
            # Dosya ismini orjinal listedeki isimle kaydet (ALTIN.IN -> ALTIN.xlsx gibi kalsın istiyorsan)
            # Ancak kodun geri kalanı .IN uzantısını sevmez, temizleyelim:
            temiz_isim = sembol.replace(".IN", "")
            filename = os.path.join(TARGET_FOLDER, f"{temiz_isim}.xlsx")
            
            df.to_excel(filename, index=False)
            basarili += 1
            
            if i % 10 == 0:
                print(f"⬇️ {sembol} indirildi... ({i}/{total})")
                
        except Exception as e:
            hatali += 1
            # print(f"Hata: {e}") # Debug için açılabilir
            continue

    print("-" * 30)
    print(f"✅ İŞLEM TAMAMLANDI.")
    print(f"Başarılı: {basarili}, Hatalı: {hatali}")

if __name__ == "__main__":
    main()      

