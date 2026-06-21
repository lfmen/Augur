import pandas as pd
import numpy as np
from datetime import datetime
import src.augur.scrapers.requests_retry as requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_mercados_opinion_data() -> pd.DataFrame:
    """
    Scraper de Riesgo País y Brecha Cambiaria Histórica.
    Extrae evolución histórica del Dólar Oficial y Blue de Bluelytics.
    Cuando la brecha es nula (unificación cambiaria), registra 0%.
    Retorna datos con frecuencia mensual.
    """
    logger.info("  [Mercados] Obteniendo histórico de Brecha Cambiaria y Riesgo País...")
    
    # 1. Brecha Cambiaria Histórica (Bluelytics)
    df_brecha = pd.DataFrame()
    try:
        res = requests.get('https://api.bluelytics.com.ar/v2/evolution.json', timeout=30)
        res.raise_for_status()
        data = res.json()
        
        df_dolares = pd.DataFrame(data)
        df_dolares['date'] = pd.to_datetime(df_dolares['date'])
        
        # Pivotear para tener Oficial y Blue como columnas
        df_pivot = df_dolares.pivot_table(index='date', columns='source', values='value_sell', aggfunc='last')
        df_pivot = df_pivot.sort_index()
        
        if 'Blue' in df_pivot.columns and 'Oficial' in df_pivot.columns:
            # Calcular brecha diaria. Donde Blue es NaN o igual a Oficial = unificación = brecha 0.
            blue = df_pivot['Blue'].ffill()
            oficial = df_pivot['Oficial'].ffill()
            
            brecha_diaria = ((blue / oficial) - 1) * 100
            # Si la brecha es negativa (inconsistencia), asumir 0
            brecha_diaria = brecha_diaria.clip(lower=0)
            
            # Resamplear a mensual: último dato del mes disponible
            # Usar 'ME' y luego convertir a inicio de mes para alineación con el pipeline
            brecha_men = brecha_diaria.resample('ME').last()
            
            # Si el mes no tiene datos de Blue (Bluelytics dejó de trackear),
            # fill forward desde el último mes con dato real.
            # Pero limitar a máximo 3 meses de ffill para no propagar datos viejos.
            # Si el ffill supera 3 meses, poner NaN (dejarlo explícito).
            brecha_men = brecha_men.ffill(limit=3)
            
            # Convertir el índice a inicio de mes (consistente con el resto del pipeline)
            brecha_men.index = brecha_men.index.to_period("M").to_timestamp()
            
            df_brecha = brecha_men.rename('Brecha_Cambiaria').to_frame()
            logger.info(f"  [Mercados] Extraídos {len(df_brecha)} registros históricos de Brecha.")
            logger.info(f"  [Mercados] Último dato de Brecha: {df_brecha['Brecha_Cambiaria'].dropna().iloc[-1]:.2f}% ({df_brecha['Brecha_Cambiaria'].dropna().index[-1].strftime('%b %Y')})")
        
    except Exception as e:
        logger.error(f"  [Mercados] Error extrayendo histórico Dólar Blue: {e}")

    # 2. Riesgo País (Ámbito)
    df_rp = pd.DataFrame()
    try:
        now = datetime.now()
        start_str = f"{now.year}-01-01"
        end_str = f"{now.year}-{now.month:02d}-{now.day:02d}"
        url = f"https://mercados.ambito.com/riesgopais/historico-general/{start_str}/{end_str}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(url, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            if len(data) > 1:
                rp_records = []
                for row in data[1:]:
                    try:
                        fecha = pd.to_datetime(row[0], format='%d-%m-%Y')
                        valor = float(row[1].replace('.', '').replace(',', '.'))
                        rp_records.append({'date': fecha, 'Riesgo_Pais': valor})
                    except (ValueError, IndexError):
                        continue
                
                if rp_records:
                    df_rp_daily = pd.DataFrame(rp_records).set_index('date').sort_index()
                    df_rp = df_rp_daily.resample('ME').last()
                    df_rp.index = df_rp.index.to_period("M").to_timestamp()
                    logger.info(f"  [Mercados] Extraídos {len(df_rp)} registros de Riesgo País.")
    except Exception as e:
        logger.error(f"  [Mercados] Error extrayendo Riesgo País: {e}")
        
    # Merge
    if not df_brecha.empty and not df_rp.empty:
        df_final = df_brecha.join(df_rp, how='outer')
    elif not df_brecha.empty:
        df_final = df_brecha.copy()
        df_final['Riesgo_Pais'] = np.nan
    elif not df_rp.empty:
        df_final = df_rp.copy()
        df_final['Brecha_Cambiaria'] = np.nan
    else:
        df_final = pd.DataFrame(columns=['Brecha_Cambiaria', 'Riesgo_Pais'])
        
    return df_final

if __name__ == "__main__":
    df_mo = get_mercados_opinion_data()
    print("Muestra actual extraída:")
    print(df_mo.tail(6))
