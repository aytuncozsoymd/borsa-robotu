import yfinance as yf
import pandas as pd
import numpy as np
import time

print("--- SKYLAR AI: BIST & ENDEKS GENİŞ TARAMA MODU ---")

# ==========================================
# 1. TARANACAK LİSTE (Sizin Verdiğiniz Liste)
# ==========================================
raw_symbols = [
    "A1CAP","A1YEN","AEFES","AGESA","AGHOL","AHGAZ","AHSGY","AKBNK","AKCNS","AKFGY","AKSA","AKSEN","AKSGY","ALARK","ALBRK",
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
    "TAVHL","TBORG","TCELL","TGSAS","THYAO","TLMAN","TNZTP","TRGYO","TRILC","TSKB","TTKOM","TUCLK","TUKAS","TUPRS","TURSG","ULKER","ULUUN",
    "VAKBN","VAKFN","VERTU","YEOTK","YGGYO","YIGIT","YKBNK","YUNSA","YYLGD","ZRGYO","XU100","XBANK","XU030","XUTEK","XTRZM","XINSA",
    "XGMYO","XUHIZ","XTUMY","XU500","XKAGT","XHOLD","XFINK","XUMAL","XELKT","XMANA","XULAS","XAKUR","XUSIN","XILTM","XMADN","XTAST",
    "XBLSM","XTCRT","XSGRT","XGIDA","XKMYA","XTEKS","XK100","ALTIN","TMPOL","TRMET","TRALT","TRENJ","GLDTR","GMSTR"
]

# Sembolleri Yahoo Finance formatına çevirme (.IS ekleme)
formatted_symbols = []
for s in raw_symbols:
    s = s.strip().upper()
    if s == "ALTIN":
        formatted_symbols.append("XAU-USD") # Ons Altın
    elif s in ["GLDTR", "GMSTR"]: # Altın/Gümüş Fonları
        formatted_symbols.append(s + ".IS")
    elif s.startswith("X"): # Endeksler (XU100 vb.)
        formatted_symbols.append(s + ".IS")
    else: # Hisseler
        formatted_symbols.append(s + ".IS")

# ==========================================
# 2. MATEMATİKSEL MOTOR (Expert MA)
# ==========================================
def calculate_ema(data, period):
    return data.ewm(span=period, adjust=False).mean()

def calculate_linreg_value(series, length=144):
    y = series.values if isinstance(series, pd.Series) else series
    y = np.array(y).flatten()
    if len(y) < 2: return np.nan
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    return slope * (len(y) - 1) + intercept

def calculate_zlsma(data, length=173):
    lsma = data.rolling(window=length).apply(lambda x: calculate_linreg_value(x), raw=True)
    lsma2 = lsma.rolling(window=length).apply(lambda x: calculate_linreg_value(x), raw=True)
    eq = lsma - lsma2
    return lsma + eq

def calculate_hma(data, period=196):
    half_length = int(period / 2)
    sqrt_length = int(np.sqrt(period))
    wma_half = data.rolling(half_length).mean()
    wma_full = data.rolling(period).mean()
    diff = 2 * wma_half - wma_full
    return diff.rolling(sqrt_length).mean()

def calculate_tema(data, period=144):
    ema1 = calculate_ema(data, period)
    ema2 = calculate_ema(ema1, period)
    ema3 = calculate_ema(ema2, period)
    return 3 * ema1 - 3 * ema2 + ema3

def analyze_symbol(symbol):
    try:
        # Veri Çekme (Hataları gizle, sadece sonucu ver)
        df = yf.download(symbol, period="2y", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.loc[:, ~df.columns.duplicated()]
        
        if len(df) < 200:
            return None

        # --- İNDİKATÖRLER ---
        close = df['Close']
        zlsma = calculate_zlsma(close)
        hma = calculate_hma(close)
        tema = calculate_tema(close)
        
        # EMA Trend
        ema8 = calculate_ema(close, 8)
        ema21 = calculate_ema(close, 21)
        ema55 = calculate_ema(close, 55)
        ema89 = calculate_ema(close, 89)
        ema233 = calculate_ema(close, 233)
        
        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # --- PUANLAMA ---
        last_price = close.iloc[-1]
        
        checks = {
            "Fiyat > ZLSMA": last_price > zlsma.iloc[-1],
            "Fiyat > HMA": last_price > hma.iloc[-1],
            "Fiyat > TEMA": last_price > tema.iloc[-1],
            "Fiyat > EMA21": last_price > ema21.iloc[-1],
            "EMA8 > EMA21": ema8.iloc[-1] > ema21.iloc[-1],
            "EMA21 > EMA55": ema21.iloc[-1] > ema55.iloc[-1],
            "EMA55 > EMA89": ema55.iloc[-1] > ema89.iloc[-1],
            "EMA89 > EMA233": ema89.iloc[-1] > ema233.iloc[-1],
            "MACD Al (Pozitif)": macd.iloc[-1] > signal.iloc[-1],
            "RSI Güçlü (>50)": rsi.iloc[-1] > 50
        }
        
        score = sum(checks.values())
        
        # KARAR MEKANİZMASI
        decision = "BELİRSİZ"
        color_code = ""
        sort_order = 0 # Sıralama için
        
        if score >= 8:
            decision = "GÜÇLÜ AL"
            color_code = "\033[92m" # Yeşil
            sort_order = 3
        elif score >= 5:
            decision = "TUT / İZLE"
            color_code = "\033[93m" # Sarı
            sort_order = 2
        else:
            decision = "SAT / NAKİT"
            color_code = "\033[91m" # Kırmızı
            sort_order = 1
            
        return {
            "symbol": symbol.replace(".IS", ""), # Raporlarken .IS'i kaldır temiz görünsün
            "price": last_price,
            "score": score,
            "decision": decision,
            "color": color_code,
            "rsi": rsi.iloc[-1],
            "sort_order": sort_order
        }

    except Exception:
        return None

# ==========================================
# 3. TARAMA BAŞLATIYOR
# ==========================================

print(f"Toplam {len(formatted_symbols)} adet enstrüman taranıyor... Lütfen bekleyin.")
print("Bu işlem 2-3 dakika sürebilir.\n")

results = []
counter = 0

for sym in formatted_symbols:
    counter += 1
    # İlerleme çubuğu (Basit)
    print(f"\rİşleniyor: {counter}/{len(formatted_symbols)} - {sym:<10}", end="")
    
    res = analyze_symbol(sym)
    if res: results.append(res)

print("\n\n" + "="*85)
print(f"{'SEMBOL':<12} | {'FİYAT':<10} | {'PUAN':<6} | {'KARAR':<20} | {'RSI'}")
print("="*85)

# Sonuçları önce Karara (Güçlü Al en üstte), sonra Puana göre sırala
results.sort(key=lambda x: (x['sort_order'], x['score']), reverse=True)

for r in results:
    price_str = f"{r['price']:.2f}"
    score_str = f"{r['score']}/10"
    rsi_str = f"{r['rsi']:.1f}"
    
    print(f"{r['symbol']:<12} | {price_str:<10} | {score_str:<6} | {r['color']}{r['decision']:<20}\033[0m | {rsi_str}")

print("="*85)

# ÖZET TABLOSU
buy_signals = [r['symbol'] for r in results if r['sort_order'] == 3]
sell_signals = [r['symbol'] for r in results if r['sort_order'] == 1]

print("\n--- ÖZET RAPOR ---")
print(f"🟢 GÜÇLÜ AL SİNYALİ VERENLER ({len(buy_signals)}):")
print(", ".join(buy_signals))
print("\n🔴 GÜÇLÜ SAT SİNYALİ VERENLER ({len(sell_signals)}):")
print(", ".join(sell_signals))
print("\n" + "="*85)