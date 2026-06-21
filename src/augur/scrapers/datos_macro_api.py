import pandas as pd
import src.augur.scrapers.requests_retry as requests
import io
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

def _fetch_serie(url: str, col_rename: str) -> pd.DataFrame:
    """Helper genérico para bajar una serie en CSV de la API datos.gob.ar."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    
    # La API siempre devuelve 2 columnas: indice_tiempo + el valor
    # (no importa el nombre exacto de la segunda columna)
    df.columns = ['fecha', col_rename]
    df['fecha'] = pd.to_datetime(df['fecha'])
    df = df.set_index('fecha').dropna()
    df.index = df.index.to_period("M").to_timestamp()
    return df

def get_datos_macro() -> pd.DataFrame:
    """
    Descarga Empleo Asalariado Privado (desestacionalizado) y Resultado Financiero
    desde la API de Datos Argentina.
    Retorna un DataFrame mensual.
    """
    logger.info("=== Scraper 5: Datos Macro (Empleo y Fiscal) ===")
    
    # 1. Empleo Asalariado Privado Desestacionalizado
    # Serie: 151.1_AARIADOTAC_2012_M_26 (Asalariados privados registrados, miles)
    df_empleo = pd.DataFrame()
    try:
        logger.info("  [Macro] Extrayendo Empleo Asalariado Privado...")
        url_empleo = "https://apis.datos.gob.ar/series/api/series/?ids=151.1_AARIADOTAC_2012_M_26&format=csv&limit=5000"
        df_empleo = _fetch_serie(url_empleo, 'Empleo_Privado_Miles')
        logger.info(f"  [Macro] {len(df_empleo)} registros de Empleo (último: {df_empleo.index[-1].strftime('%b %Y')}, {df_empleo['Empleo_Privado_Miles'].iloc[-1]:,.1f} miles)")
    except Exception as e:
        logger.error(f"  [Macro] Error extrayendo Empleo Privado: {e}")

    # 2. Resultado Financiero SPN (Sector Público Nacional)
    # Serie: 378.9_RESULTADO_017_0_M_18_90 (Resultado financiero mensual, millones ARS)
    df_fiscal = pd.DataFrame()
    try:
        logger.info("  [Macro] Extrayendo Resultado Financiero SPN...")
        url_fiscal = "https://apis.datos.gob.ar/series/api/series/?ids=378.9_RESULTADO_017_0_M_18_90&format=csv&limit=5000"
        df_fiscal = _fetch_serie(url_fiscal, 'Resultado_Financiero_Millones')
        logger.info(f"  [Macro] {len(df_fiscal)} registros Fiscales (último: {df_fiscal.index[-1].strftime('%b %Y')}, ${df_fiscal['Resultado_Financiero_Millones'].iloc[-1]:,.0f} M)")
    except Exception as e:
        logger.error(f"  [Macro] Error extrayendo Resultado Fiscal: {e}")

    # Merge
    if not df_empleo.empty and not df_fiscal.empty:
        df_final = df_empleo.join(df_fiscal, how='outer')
    elif not df_empleo.empty:
        df_final = df_empleo.copy()
        df_final['Resultado_Financiero_Millones'] = pd.NA
    elif not df_fiscal.empty:
        df_final = df_fiscal.copy()
        df_final['Empleo_Privado_Miles'] = pd.NA
    else:
        df_final = pd.DataFrame(columns=['Empleo_Privado_Miles', 'Resultado_Financiero_Millones'])

    return df_final.sort_index()

if __name__ == "__main__":
    df = get_datos_macro()
    print(df.tail(5))
