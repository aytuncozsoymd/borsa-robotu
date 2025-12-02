from tvDatafeed import TvDatafeed, Interval
import pandas as pd
import os
import time

# --- BULUT UYUMLU AYARLAR ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_FOLDER = os.path.join(BASE_DIR, 'DATAson')

# Klasör yoksa oluştur
if not os.path.exists(TARGET_FOLDER):
    os.makedirs(TARGET_FOLDER)

# Kaç günlük veri indirilsin?
N_BARS = 1500 

# Hisse Listesi
stock_list_fx_idc = ['XAUTRYG', 'XAGTRYG'] 
stock_list_bist = ["A1CAP","A1YEN","AEFES","AGESA","AGHOL","AHGAZ","AHSGY","AKBNK","AKCNS","AKFGY","AKSA","AKSEN","AKSGY","ALARK","ALBRK",
                   "ALCAR","ALGYO","ALKA","ALVES","ANHYT","ANSGR","ARASE","ARDYZ","ARMGD","ASELS","ASTOR","ASUZU","ATATP","AYGAZ","BASGZ","BESLR",
                   "BEYAZ","BFREN","BIGCH","BIMAS","BLUME","BMSCH","BMSTL","BOSSA","BRISA","BRKSN","BRSAN","BVSAN","CCOLA","CEMTS","CIMSA",
                   "CLEBI","CRDFA","CWENE","DAGI","DERIM","DESA","DESPC","DGATE","DOAS","DOFER","DOHOL","EBEBK","ECILC","EDATA","EGEPO",
                   "EGGUB","EGPRO","EKGYO","ELITE","ENERY","ENJSA","ENKAI","EREGL","EUPWR","EUREN","FMIZP","FORTE","FROTO","GARAN","GARFA",
                   "GEDZA","GENIL","GENTS","GEREL","GESAN","GIPTA","GLCVY","GLRMK","GLYHO","GMTAS","GOLTS","GRSEL","GRTHO","GSDHO","GUBRF",
                   "GWIND","HALKB","HLGYO","HTTBT","IMASM","INDES","INFO","INGRM","ISCTR","ISDMR","ISFIN","ISGYO","ISKPL","ISMEN","KATMR",
                   "KCAER","KCHOL","KIMMR","KLKIM","KLMSN","TRALT","KRDMA","KRDMB","KRDMD","KRGYO","KRONT","KRSTL","KTLEV","KUYAS","LIDER",
                   "LIDFA","LILAK","LINK","LKMNH","LMKDC","LOGO","LYDYE","MACKO","MAGEN","MARBL","MEDTR","MEPET","MERIT","MGROS","MNDRS","MOBTL",
                   "MPARK","MTRKS","NTGAZ","NTHOL","NUHCM","OBASE","ODAS","OFSYM","ONCSM","ORGE","OTKAR","OYAKC","OZKGY","OZSUB","OZYSR","PAGYO",
                   "PAPIL","PASEU","PATEK","PENGD","PENTA","PETUN","PGSUS","PINSU","PLTUR","PNLSN","PRKME","RGYAS","RNPOL","RUZYE","RYGYO","RYSAS",
                   "SAHOL","SANEL","SAYAS","SDTTR","SELEC","SISE","SKBNK","SMART","SOKM","SRVGY","SUNTK","SUWEN","TABGD","TARKM","TATEN","TATGD",
                   "TAVHL","TBORG","TCELL","TGSAS","THYAO","TLMAN","TNZTP","TRGYO","TRILC","TSKB","TTKOM","TUCLK","TUKAS","TUPRS","TURSG","ULKER","ULUUN",
                   "VAKBN","VAKFN","VERTU","YEOTK","YGGYO","YIGIT","YKBNK","YUNSA","YYLGD","ZRGYO","XU100"]

def main():
    print("--- OTOMATİK VERİ İNDİRME BAŞLATILIYOR (Cloud Modu) ---")
    
    tv = TvDatafeed() 
    
    # XU100 Verisi
    print("XU100 verisi çekiliyor...")
    xu100_df = tv.get_hist(symbol="XU100", exchange="BIST", interval=Interval.in_daily, n_bars=N_BARS)
    
    if xu100_df is not None and not xu100_df.empty:
        xu100_df = xu100_df[['close']].rename(columns={'close': 'XU100_TL'})
        xu100_df.index = pd.to_datetime(xu100_df.index)
    else:
        xu100_df = pd.DataFrame()

    all_stocks = stock_list_bist + stock_list_fx_idc
    success_count = 0
    fail_count = 0
    
    for stock in all_stocks:
        try:
            exchange = "FX_IDC" if stock in stock_list_fx_idc else "BIST"
            df = tv.get_hist(symbol=stock, exchange=exchange, interval=Interval.in_daily, n_bars=N_BARS)
            
            if df is None or df.empty:
                fail_count += 1
                continue

            df = df[['open', 'high', 'low', 'close', 'volume']].copy()
            df.rename(columns={'open':'OPEN_TL', 'close':'CLOSING_TL', 'low':'LOW_TL', 'high':'HIGH_TL', 'volume':'VOLUME_TL'}, inplace=True)
            df['CODE'] = stock
            df.index.name = 'DATE'
            df.reset_index(inplace=True)

            if not xu100_df.empty:
                 df['DATE'] = pd.to_datetime(df['DATE'])
                 df = df.merge(pd.DataFrame(xu100_df['XU100_TL']), how='left', left_on='DATE', right_index=True)
            
            filename = os.path.join(TARGET_FOLDER, f"{stock}.xlsx")
            df.to_excel(filename, index=False)
            success_count += 1
            
        except Exception:
            fail_count += 1
            continue

    print("-" * 30)
    print(f"TAMAMLANDI. İndirilen: {success_count}, Hatalı: {fail_count}")

if __name__ == "__main__":
    main()