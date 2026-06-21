import src.augur.scrapers.requests_retry as requests
import pandas as pd
from datetime import datetime
import logging
from io import StringIO
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-419,es;q=0.9',
    'Referer': 'https://www.google.com/'
}

CSVS = {
    "Reservas": {
        "url": "https://infra.datos.gob.ar/catalog/sspm/dataset/92/distribution/92.2/download/reservas-internacionales-pasivos-financieros-bcra.csv",
        "col": "reservas_internacionales_dolares"
    },
    "Base_Monetaria": {
        "url": "https://infra.datos.gob.ar/catalog/sspm/dataset/331/distribution/331.1/download/factores-explicacion-base-monetaria-mensuales.csv",
        "col": "saldo_base_monetaria"
    },
    "IPC_Nivel": {
        "url": "https://infra.datos.gob.ar/catalog/sspm/dataset/145/distribution/145.3/download/indice-precios-al-consumidor-nivel-general-base-diciembre-2016-mensual.csv",
        "col": "ipc_ng_nacional"
    }
}

def fetch_csv(config: dict, col_name: str) -> pd.DataFrame:
    try:
        url = config["url"]
        val_col = config["col"]
        logger.info(f"Descargando {col_name} desde INDEC/BCRA...")
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        
        df = pd.read_csv(StringIO(res.text))
        time_col = df.columns[0]
            
        df = df[[time_col, val_col]].copy()
        df[time_col] = pd.to_datetime(df[time_col])
        df.set_index(time_col, inplace=True)
        df.rename(columns={val_col: col_name}, inplace=True)
        
        if col_name == "IPC_Nivel":
            # Calcular variación mensual porcentual (inflación mensual)
            df["IPC_BCRA"] = df["IPC_Nivel"].pct_change() * 100
            df = df[["IPC_BCRA"]].dropna()
            col_name = "IPC_BCRA"
            
        df = df.resample('MS').mean()
        return df
    except Exception as e:
        logger.error(f"Error descargando {col_name}: {e}")
        return pd.DataFrame()

def fetch_usd_oficial() -> pd.DataFrame:
    try:
        logger.info("Extrayendo histórico de Tipo_Cambio_Oficial desde Bluelytics...")
        res = requests.get("https://api.bluelytics.com.ar/v2/evolution.json", timeout=15)
        res.raise_for_status()
        data = res.json()
        df = pd.DataFrame(data)
        df_oficial = df[df["source"] == "Oficial"].copy()
        df_oficial["date"] = pd.to_datetime(df_oficial["date"])
        df_oficial.set_index("date", inplace=True)
        df_oficial.rename(columns={"value_sell": "Tipo_Cambio_Oficial"}, inplace=True)
        df_oficial = df_oficial[["Tipo_Cambio_Oficial"]]
        df_oficial = df_oficial.resample('MS').mean()
        return df_oficial
    except Exception as e:
        logger.error(f"Error en Bluelytics: {e}")
        return pd.DataFrame()

def get_bcra_data(token: str = "") -> pd.DataFrame:
    # Ignoramos el token obsoleto
    dfs = []
    for name, config in CSVS.items():
        df_tmp = fetch_csv(config, name)
        if not df_tmp.empty:
            dfs.append(df_tmp)
            
    df_usd = fetch_usd_oficial()
    if not df_usd.empty:
        dfs.append(df_usd)
            
    if not dfs:
        return pd.DataFrame()
        
    df_final = dfs[0]
    for df_tmp in dfs[1:]:
        df_final = df_final.join(df_tmp, how='outer')
        
    return df_final.sort_index()

if __name__ == "__main__":
    df_bcra = get_bcra_data()
    if not df_bcra.empty:
        print("Datos de BCRA/INDEC extraídos con éxito:")
        print(df_bcra.tail())
    else:
        print("Fallo en extracción.")
