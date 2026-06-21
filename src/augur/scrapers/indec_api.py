import src.augur.scrapers.requests_retry as requests
import pandas as pd
from datetime import datetime
import logging
from io import StringIO
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cabeceras para evadir el Firewall 403 de datos.gob.ar
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-419,es;q=0.9',
    'Referer': 'https://www.google.com/'
}

BASE_URL = "https://apis.datos.gob.ar/series/api/series"
SERIES_IDS = {
    "EMAE": "143.3_NO_PR_2004_A_21", 
    "RIPTE": "158.1_REPTE_0_0_5"
}

URL_ICG = "https://infra.datos.gob.ar/catalog/sspm/dataset/370/distribution/370.3/download/indice-confianza-gobierno-valores-mensuales.csv"

def fetch_api_indec() -> pd.DataFrame:
    try:
        logger.info("Extrayendo EMAE y RIPTE vía API disfrazada...")
        ids_param = ",".join(SERIES_IDS.values())
        params = {"ids": ids_param, "format": "json", "limit": 5000}
        res = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        res.raise_for_status()
        
        data = res.json()
        dates = []
        series_ids = list(SERIES_IDS.values())
        values = {s_id: [] for s_id in series_ids}
        
        for row in data.get("data", []):
            dates.append(row[0])
            for i, s_id in enumerate(series_ids):
                values[s_id].append(row[i+1])
                
        df = pd.DataFrame(values)
        df['date'] = pd.to_datetime(dates)
        df.set_index('date', inplace=True)
        
        rename_dict = {v: k for k, v in SERIES_IDS.items()}
        df = df.rename(columns=rename_dict)
        return df
    except Exception as e:
        logger.error(f"Error en API INDEC: {e}")
        return pd.DataFrame()

def fetch_csv_icg() -> pd.DataFrame:
    try:
        logger.info("Descargando ICG (Aprobación) desde CSV de Di Tella...")
        res = requests.get(URL_ICG, headers=HEADERS, timeout=15)
        res.raise_for_status()
        
        df = pd.read_csv(StringIO(res.text))
        time_col = df.columns[0]
        val_col = "icg_nivel_general"
            
        df = df[[time_col, val_col]].copy()
        df[time_col] = pd.to_datetime(df[time_col])
        df.set_index(time_col, inplace=True)
        df.rename(columns={val_col: "ICG_Aprobacion"}, inplace=True)
        
        df = df.resample('MS').mean()
        return df
    except Exception as e:
        logger.error(f"Error descargando ICG: {e}")
        return pd.DataFrame()

def get_indec_data() -> pd.DataFrame:
    """
    Obtiene EMAE, RIPTE e ICG burlando el firewall.
    """
    df_api = fetch_api_indec()
    df_icg = fetch_csv_icg()
    
    if df_api.empty and df_icg.empty:
        return pd.DataFrame()
        
    if df_api.empty:
        return df_icg.sort_index()
        
    if df_icg.empty:
        return df_api.sort_index()
        
    df_final = df_api.join(df_icg, how='outer')
    return df_final.sort_index()

if __name__ == "__main__":
    df_indec = get_indec_data()
    if not df_indec.empty:
        print("Datos del INDEC/UTDT extraídos con éxito:")
        print(df_indec.tail())
    else:
        print("Fallo total en la extracción de INDEC/ICG.")
