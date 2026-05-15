"""
config.py — Zenith 2.0 Central Configuration
Single source of truth for all constants, env vars, and env detection.
RULE: No hardcodes in other files — always import from here.
"""
import os
from datetime import timezone, timedelta

# ── Environment Detection ──────────────────────────────────────────────────────
IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))
IS_LOCAL   = not IS_RAILWAY

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/zenith"
)

# ── Flask ──────────────────────────────────────────────────────────────────────
FLASK_SECRET = os.environ.get("FLASK_SECRET", "zenith-secret-key-dev")

# Session isolation — both 1.0 and 2.0 run on Railway simultaneously
SESSION_TYPE     = "filesystem"
SESSION_DIR      = os.environ.get("SESSION_DIR", "/tmp/zenith_2_0_sessions/")

# ── Caching ────────────────────────────────────────────────────────────────────
CACHE_TTL      = 86400 if IS_RAILWAY else 300   # 24h server | 5min local
FLOW_CACHE_TTL = 60                              # route-level cache, seconds
GAIN_CACHE_TTL = 300                             # price gain cache, seconds

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL = "WARNING" if IS_RAILWAY else "DEBUG"

# ── Timezone ───────────────────────────────────────────────────────────────────
WIB = timezone(timedelta(hours=7))

# ── Telegram Credentials ───────────────────────────────────────────────────────
TG_API_ID   = int(os.environ.get("TG_API_ID", "0") or "0")
TG_API_HASH = os.environ.get("TG_API_HASH", "")

# Session file — Railway persistent volume at /data/
TG_SESSION_PATH = os.environ.get("TG_SESSION_PATH", "/data/session_joker_2")

# Telegram group & topic IDs (BST group)
TG_GROUP_ID       = -1002717915373
TG_TOPIC_SMART    = 192528
TG_TOPIC_BAD      = 219042
TG_TOPIC_MF_PLUS  = 1025256
TG_TOPIC_MF_MINUS = 1025260

# ── Scraper Schedule ───────────────────────────────────────────────────────────
MIDDAY_HOUR      = 12
MIDDAY_MINUTE    = 10
BACKFILL_HOUR    = 15
BACKFILL_MINUTE  = 30
RECOMPUTE_HOUR   = 16
RECOMPUTE_MINUTE = 30

SCRAPER_ENABLED = os.environ.get("SCRAPER_ENABLED", "1") == "1"

# ── Price Fetch ────────────────────────────────────────────────────────────────
YF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://finance.yahoo.com",
}

INTERVAL_MAP = {
    "5m":  {"interval": "5m",  "days": 59},
    "15m": {"interval": "15m", "days": 59},
    "30m": {"interval": "30m", "days": 59},
    "1h":  {"interval": "60m", "days": 720},
    "1d":  {"interval": "1d",  "days": 99999},
}

# ── DataSectors API (Tier 1-4 integration — not yet active) ───────────────────
DS_API_KEY    = os.environ.get("DATASECTORS_API_KEY", "")
DS_BASE_URL   = "https://api.datasectors.com"
DS_ENABLED    = bool(DS_API_KEY)
DS_CACHE_TTL  = 86400  # 1 hari

# ── Sector Mapping ─────────────────────────────────────────────────────────────
SECTORS = {
    "Energy": ['ABMM', 'MEDC', 'SGER', 'AKRA', 'MTFN', 'UNIQ', 'APEX', 'MYOH', 'MCOL', 'ARII', 'PGAS', 'GTSI', 'ARTI', 'PKPK', 'RMKE', 'BBRM', 'PTBA', 'BSML', 'BIPI', 'PTIS', 'ADMR', 'BSSR', 'PTRO', 'SEMA', 'BULL', 'RAJA', 'SICO', 'BUMI', 'RIGS', 'COAL', 'BYAN', 'RUIS', 'SUNI', 'CANI', 'SMMT', 'CBRE', 'CNKO', 'SMRU', 'HILL', 'DEWA', 'SOCI', 'CUAN', 'DOID', 'BUMA', 'SUGI', 'MAHA', 'DSSA', 'TOBA', 'RMKO', 'ELSA', 'TPMA', 'HUMI', 'ENRG', 'TRAM', 'RGAS', 'GEMS', 'WINS', 'ALII', 'GTBO', 'SHIP', 'MKAP', 'HITS', 'TAMU', 'ATLA', 'HRUM', 'FIRE', 'BOAT', 'IATA', 'PSSI', 'AADI', 'INDY', 'DWGL', 'RATU', 'ITMA', 'BOSS', 'PSAT', 'ITMG', 'JSKY', 'BESS', 'KKGI', 'INPS', 'CGAS', 'KOPI', 'TCPI', 'ADRO', 'LEAD', 'SURE', 'AIMS', 'MBAP', 'WOWS', 'MBSS', 'TEBE'],
    "Basic Materials": ['AKPI', 'MDKA', 'ESIP', 'ALDO', 'NIKL', 'IFSH', 'ALKA', 'OKAS', 'IFII', 'ALMI', 'PICO', 'SAMF', 'ANTM', 'PSAB', 'EPAC', 'APLI', 'SIMA', 'BEBS', 'BAJA', 'SMBR', 'NPGF', 'BMSR', 'SMCB', 'ARCI', 'BRMS', 'SMGR', 'NICL', 'BRNA', 'SPMA', 'SBMA', 'BRPT', 'SQMI', 'CMNT', 'BTON', 'SRSN', 'OBMD', 'CITA', 'SULI', 'AVIA', 'CLPI', 'TALF', 'CHEM', 'CTBN', 'TBMS', 'KKES', 'DKFT', 'TINS', 'PDPP', 'DPNS', 'TIRT', 'FWCT', 'EKAD', 'TKIM', 'PACK', 'ESSA', 'TPIA', 'AMMN', 'ETWA', 'TRST', 'PPRI', 'FASW', 'UNIC', 'SMGA', 'FPNI', 'WTON', 'SOLA', 'GDST', 'YPAS', 'BATR', 'IGAR', 'INCF', 'BLES', 'INAI', 'WSBP', 'PTMR', 'INCI', 'KMTR', 'DAAZ', 'INCO', 'MDKI', 'DGWG', 'INKP', 'ZINC', 'MINE', 'INRU', 'PBID', 'ASPR', 'INTD', 'TDPM', 'EMAS', 'INTP', 'SWAT', 'AYLS', 'IPOL', 'MOLI', 'NCKL', 'ISSP', 'HKMU', 'MBMA', 'KBRI', 'KAYU', 'NICE', 'KDSI', 'SMKL', 'SMLE', 'KRAS', 'GGRP', 'ADMG', 'LMSH', 'OPMS', 'AGII', 'LTLS', 'PURE'],
    "Industrials": ['AMFG', 'KIAS', 'ARKA', 'AMIN', 'KOBX', 'SINI', 'APII', 'KOIN', 'HOPE', 'ARNA', 'KONI', 'LABA', 'ASGR', 'LION', 'GPSO', 'ASII', 'MDRN', 'KUAS', 'BHIT', 'MFMI', 'BINO', 'BNBR', 'MLIA', 'NTBK', 'CTTH', 'SCCO', 'PADA', 'DYAN', 'TIRA', 'KING', 'HEXA', 'TOTO', 'PTMP', 'IBFN', 'TRIL', 'SMIL', 'ICON', 'UNTR', 'CRSN', 'IKAI', 'VOKS', 'WIDI', 'IKBI', 'ZBRA', 'FOLK', 'IMPC', 'MARK', 'MUTU', 'INDX', 'SPTO', 'HYGN', 'INTA', 'SKRN', 'VISI', 'JECC', 'CAKK', 'MHKI', 'JTPE', 'SOSS', 'NAIK', 'KBLI', 'CCSI', 'PIPA', 'KBLM', 'BLUE'],
    "Consumer Non-Cyclicals": ['AALI', 'SIPD', 'FLMC', 'ADES', 'SKBM', 'OILS', 'AISA', 'SKLT', 'BOBA', 'ALTO', 'SMAR', 'CMRY', 'AMRT', 'SSMS', 'TAYS', 'ANJT', 'STTP', 'WMPP', 'BISI', 'TBLA', 'IPPE', 'BTEK', 'TCID', 'NASI', 'BUDI', 'TGKA', 'STAA', 'BWPT', 'ULTJ', 'NANO', 'CEKA', 'UNSP', 'TLDN', 'CPIN', 'UNVR', 'IBOS', 'CPRO', 'WAPO', 'ASHA', 'DLTA', 'WICO', 'TRGU', 'DSFI', 'WIIM', 'DEWI', 'DSNG', 'DAYA', 'GULA', 'EPMT', 'DPUM', 'JARR', 'FISH', 'KINO', 'AMMS', 'GGRM', 'CLEO', 'EURO', 'GOLL', 'HOKI', 'BUAH', 'GZCO', 'CAMP', 'CRAB', 'HERO', 'PCAR', 'CBUT', 'HMSP', 'MGRO', 'MKTR', 'ICBP', 'ANDI', 'SOUL', 'INDF', 'GOOD', 'BEER', 'JAWA', 'FOOD', 'WINE', 'JPFA', 'BEEF', 'NAYZ', 'LAPD', 'COCO', 'NSSS', 'LSIP', 'ITIC', 'MAXI', 'MAGP', 'KEJU', 'GRPM', 'MAIN', 'PSGO', 'TGUK', 'MBTO', 'AGAR', 'PTPS', 'MIDI', 'UCID', 'STRK', 'MLBI', 'CSRA', 'UDNG', 'MLPL', 'DMND', 'AYAM', 'MPPA', 'IKAN', 'ISEA', 'MRAT', 'PGUN', 'GUNA', 'MYOR', 'PNGO', 'NEST', 'PSDN', 'KMDS', 'BRRC', 'RANC', 'ENZO', 'RLCO', 'ROTI', 'VICI', 'YUPI', 'SDPC', 'PMMP', 'FORE', 'SGRO', 'WMUU', 'MSJA', 'SIMP', 'TAPG', 'FAPA'],
    "Consumer Cyclicals": ['ABBA', 'PTSP', 'SCNP', 'ACES', 'RALS', 'PLAN', 'AKKU', 'RICY', 'SNLK', 'ARGO', 'SCMA', 'LFLO', 'ARTA', 'SHID', 'LUCY', 'AUTO', 'SMSM', 'MGLV', 'BATA', 'SONA', 'IDEA', 'BAYU', 'SRIL', 'DEPO', 'BIMA', 'SSTM', 'DRMA', 'BLTZ', 'TELE', 'ASLC', 'BMTR', 'TFCO', 'NETV', 'MDTV', 'BOLT', 'TMPO', 'BAUT', 'BRAM', 'TRIO', 'ENAK', 'BUVA', 'TRIS', 'BIKE', 'CINT', 'UNIT', 'OLIV', 'CNTX', 'VIVA', 'SWID', 'CSAP', 'JGLE', 'RAFI', 'ECII', 'MARI', 'KLIN', 'ERAA', 'MKNT', 'TOOL', 'ERTX', 'BOGA', 'KDTN', 'ESTI', 'CARS', 'ZATA', 'FAST', 'MINA', 'ISAP', 'FORU', 'MAPB', 'BMBL', 'GDYR', 'WOOD', 'FUTR', 'GEMA', 'HRTA', 'HAJJ', 'GJTL', 'MABA', 'TYRE', 'GLOB', 'BELL', 'VKTR', 'GWSA', 'DFAM', 'CNMA', 'HOME', 'PZZA', 'ERAL', 'HOTL', 'MSIN', 'LMAX', 'IIKP', 'MAPA', 'BABY', 'IMAS', 'NUSA', 'AEGS', 'INDR', 'FILM', 'GRPH', 'INDS', 'DIGI', 'UNTD', 'JIHD', 'DUCK', 'MEJA', 'JSPT', 'YELO', 'LIVE', 'KICI', 'SOTS', 'BAIK', 'KPIG', 'ZONE', 'SPRE', 'LMPI', 'CLAY', 'PART', 'LPIN', 'NATO', 'GOLF', 'LPPF', 'HRME', 'DOSS', 'MAPI', 'FITT', 'VERN', 'MDIA', 'BOLA', 'MDIY', 'MGNA', 'POLU', 'MERI', 'MICE', 'IPTV', 'PMUI', 'MNCN', 'EAST', 'KAQI', 'MPMX', 'KOTA', 'ESTA', 'MSKY', 'INOV', 'RAAM', 'MYTX', 'SLIS', 'DOOH', 'PANR', 'PMJS', 'ACRO', 'PBRX', 'SBAT', 'UFOE', 'PDES', 'CBMF', 'PNSE', 'PGLI', 'CSMI', 'POLY', 'PJAA', 'SOFA', 'PSKT', 'TOYS'],
    "Healthcare": ['DVLA', 'PRDA', 'PEVE', 'INAF', 'PRIM', 'HALO', 'KAEF', 'HEAL', 'RSCH', 'KLBF', 'PEHA', 'IKPM', 'MERK', 'IRRA', 'SURI', 'MIKA', 'SOHO', 'LABS', 'PYFA', 'BMHS', 'OBAT', 'SAME', 'RSGK', 'CHEK', 'SCPI', 'MTMH', 'MDLA', 'SIDO', 'MEDS', 'DKHH', 'SILO', 'PRAY', 'CARE', 'SRAJ', 'OMED', 'DGNS', 'TSPC', 'MMIX'],
    "Financials": ['ABDA', 'BPFI', 'TIFA', 'AMAG', 'BPII', 'TRIM', 'APIC', 'BSIM', 'TRUS', 'ARTO', 'BSWD', 'VICO', 'ASBI', 'BTPN', 'SMBC', 'VINS', 'ASDM', 'BVIC', 'VRNA', 'ASJT', 'CFIN', 'WOMF', 'ASMI', 'DEFI', 'YULE', 'ASRM', 'DNAR', 'CASA', 'BABP', 'DNET', 'BRIS', 'BACA', 'GSMF', 'MTWI', 'BBCA', 'HDFA', 'JMAS', 'BBHI', 'INPC', 'NICK', 'BBKP', 'LPGI', 'BTPS', 'BBLD', 'LPPS', 'TUGU', 'BBMD', 'MAYA', 'POLA', 'BBNI', 'MCOR', 'SFAN', 'BBRI', 'MEGA', 'LIFE', 'MSIG', 'BBTN', 'MREI', 'FUJI', 'BBYB', 'NISP', 'OCBC', 'AMAR', 'BCAP', 'NOBU', 'AMOR', 'BCIC', 'OCAP', 'BHAT', 'BDMN', 'PADI', 'BBSI', 'BEKS', 'PALM', 'BANK', 'BFIN', 'PANS', 'MASB', 'BGTG', 'PEGE', 'VTNY', 'BINA', 'PLAS', 'YOII', 'BJBR', 'PNBN', 'COIN', 'BJTM', 'PNBS', 'SUPA', 'BKSW', 'PNIN', 'ADMF', 'BMAS', 'PNLF', 'AGRO', 'BMRI', 'RELI', 'AGRS', 'BNBA', 'SDRA', 'AHAP', 'BNGA', 'CIMB', 'SMMA', 'POOL', 'BNII', 'SRTG', 'BNLI', 'STAR'],
    "Property": ['APLN', 'MMLP', 'NZIA', 'ASRI', 'MTLA', 'REAL', 'BAPA', 'MTSM', 'INDO', 'BCIP', 'NIRO', 'TRIN', 'BEST', 'OMRE', 'KBAG', 'BIKA', 'PLIN', 'BBSS', 'BIPP', 'PUDP', 'UANG', 'BKDP', 'PWON', 'PURI', 'BKSL', 'RBMS', 'HOMI', 'BSDE', 'RDTX', 'ROCK', 'COWL', 'RIMO', 'ATAP', 'CTRA', 'RODA', 'ADCP', 'DART', 'SMDM', 'TRUE', 'DILD', 'SMRA', 'IPAC', 'DMAS', 'TARA', 'WINR', 'DUTI', 'CSIS', 'BSBK', 'ELTY', 'ARMY', 'CBPE', 'EMDE', 'NASA', 'VAST', 'FMII', 'RISE', 'SAGE', 'GAMA', 'POLL', 'RELF', 'GMTD', 'LAND', 'HBAT', 'GPRA', 'PANI', 'GRIA', 'INPP', 'CITY', 'MSIE', 'JRPT', 'MPRO', 'KOCI', 'KIJA', 'SATU', 'KSIX', 'LCGP', 'URBN', 'CBDK', 'LPCK', 'POLI', 'DADA', 'LPKR', 'CPRI', 'ASPI', 'LPLI', 'POSA', 'AMAN', 'MDLN', 'PAMG', 'PPRO', 'MKPI', 'BAPI'],
    "Technology": ['ATIC', 'DMMX', 'ELIT', 'EMTK', 'GLVA', 'IRSX', 'KREN', 'PGJO', 'CHIP', 'LMAS', 'CASH', 'TRON', 'MLPT', 'TECH', 'JATI', 'MTDL', 'EDGE', 'CYBR', 'PTSN', 'ZYRX', 'IOTF', 'SKYB', 'UVCR', 'MSTI', 'KIOS', 'BUKA', 'TOSK', 'MCAS', 'RUNS', 'MPIX', 'NFCX', 'WGSH', 'AREA', 'DIVA', 'WIRG', 'ASIA', 'MENN', 'LUCK', 'GOTO', 'AWAN', 'ENVY', 'AXIO', 'WIFI', 'HDIT', 'BELI', 'DCII', 'TFAS', 'NINE'],
    "Infrastructure": ['ACST', 'TBIG', 'JAST', 'ADHI', 'TLKM', 'KEEN', 'BALI', 'TOTL', 'PTPW', 'BTEL', 'TOWR', 'TAMA', 'BUKK', 'WIKA', 'RONY', 'CASS', 'WSKT', 'PTDU', 'CENT', 'IDPR', 'FIMP', 'CMNP', 'MTRA', 'MTEL', 'DGIK', 'OASA', 'SMKM', 'EXCL', 'POWR', 'ARKO', 'GOLD', 'PBSA', 'KRYA', 'HADE', 'PORT', 'PGEO', 'IBST', 'TGRA', 'BDKR', 'ISAT', 'TOPS', 'INET', 'JKON', 'MPOW', 'BREN', 'JSMR', 'GMFI', 'KOKA', 'KARW', 'PPRE', 'ASLI', 'KBLV', 'WEGE', 'LINK', 'MORA', 'HGII', 'META', 'IPCM', 'CDIA', 'NRCA', 'LCKM', 'MANG', 'PTPP', 'GHON', 'KETR', 'SSIA', 'IPCC', 'SUPR', 'MTPS'],
    "Transport": ['AKSI', 'SMDR', 'PPGL', 'ASSA', 'TAXI', 'TRJA', 'BIRD', 'TMAS', 'HAIS', 'BLTA', 'WEHA', 'HATM', 'CMPP', 'HELI', 'RCCC', 'GIAA', 'TRUK', 'ELPI', 'IMJS', 'TNCA', 'LAJU', 'LRNA', 'BPTR', 'GTRA', 'MIRA', 'SAPX', 'MPXL', 'MITI', 'DEAL', 'KLAS', 'NELY', 'JAYA', 'LOPI', 'SAFE', 'KJEN', 'BLOG', 'SDMU', 'PURA', 'PJHB'],
}
