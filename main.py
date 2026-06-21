import logging
import os
import pandas as pd
import json
import re
from src.augur.scrapers.indec_api import get_indec_data
from src.augur.scrapers.bcra_api import get_bcra_data
from src.augur.scrapers.mercados_opinion import get_mercados_opinion_data
from src.augur.scrapers.salario_real_api import calcular_salario_real
from src.augur.scrapers.icc_api import get_icc_completo
from src.augur.scrapers.rin_api import get_reservas_netas
from src.augur.scrapers.ivs_api import calcular_ivs
from src.augur.scrapers.datos_macro_api import get_datos_macro
from src.augur.preprocessing.data_alignment import align_and_impute
from src.augur.preprocessing.feature_engineering import create_features
from src.augur.modeling.model_selection import ViabilityIndex

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _safe_run(func, *args, **kwargs):
    try:
        df = func(*args, **kwargs)
        # Ensure it's not None
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        logger.error(f"Error en scraper {func.__name__}: {e}")
        return pd.DataFrame()

def run_pipeline():
    logger.info("=== INICIANDO PIPELINE: ÍNDICE DE VIABILIDAD REELECCIÓN ===")
    
    # Fase 1: Extracción
    logger.info("Fase 1: Extracción de Datos...")
    
    df_indec = _safe_run(get_indec_data)
    df_bcra = _safe_run(get_bcra_data)
    df_mo = _safe_run(get_mercados_opinion_data)
    df_salario = _safe_run(calcular_salario_real)
    df_icc = _safe_run(get_icc_completo)
    df_rin = _safe_run(get_reservas_netas, frecuencia="mensual")
    df_ivs = _safe_run(calcular_ivs)
    df_macro = _safe_run(get_datos_macro)

    if df_indec.empty and df_bcra.empty and df_mo.empty and df_salario.empty and df_icc.empty and df_rin.empty and df_ivs.empty and df_macro.empty:
        logger.error("No se pudieron extraer datos de ninguna fuente. Abortando.")
        return

    # Fase 2: Preprocesamiento
    logger.info("Fase 2: Preprocesamiento y Alineación...")
    df_aligned = align_and_impute(df_indec, df_bcra, df_mo, df_salario, df_icc, df_rin, df_ivs, df_macro)
    df_features = create_features(df_aligned)
    
    # Eliminar filas con fechas futuras (pueden aparecer si algún scraper genera datos especulativos)
    hoy = pd.Timestamp.today().to_period('M').to_timestamp()
    df_features = df_features[df_features.index <= hoy]
    
    # Lógica robusta de fallbacks (recuperar de caché si una API falló)
    if os.path.exists("data/dataset_procesado.csv"):
        try:
            df_cache = pd.read_csv("data/dataset_procesado.csv", index_col='Fecha', parse_dates=True)
            # Filtrar caché por fechas pasadas/presentes únicamente
            df_cache = df_cache[df_cache.index <= hoy]
            # combine_first prioriza df_features, pero rellena NaNs con df_cache
            df_features = df_features.combine_first(df_cache)
            # ffill propaga el último dato conocido del caché si la API falló este mes
            df_features = df_features.ffill(limit=3)
            # Volver a filtrar por si combine_first introdujo fechas del caché
            df_features = df_features[df_features.index <= hoy]
        except Exception as e:
            logger.warning(f"No se pudo usar el caché para fallback: {e}")
    
    # Universal ffill para propagar los deltas o niveles calculados a los meses donde la API no tiene dato aún
    df_features = df_features.ffill(limit=3)
    
    # Filtrar solo meses a partir del inicio del mandato de Milei (Diciembre 2023)
    df_milei = df_features[df_features.index >= '2023-12-01'].copy()
    
    # Fase 3: Cálculo del Índice
    logger.info("Fase 3: Cálculo del Índice Cuantitativo...")
    idx = ViabilityIndex()
    df_scored = idx.score_series(df_milei)
    
    # Guardar base procesada para el dashboard
    os.makedirs("data", exist_ok=True)
    df_scored.to_csv("data/dataset_procesado.csv", index=True, index_label='Fecha')
    
    # Fase 4: Proyección y Output
    logger.info("Fase 4: Output del Escenario Actual...")
    
    if not df_scored.empty:
        last_row = df_scored.iloc[-1]
        current_score = last_row['Viability_Score']
        last_date = df_scored.index[-1].strftime("%Y-%m-%d")
        
        logger.info(f">>> ÍNDICE DE VIABILIDAD ACTUAL ({last_date}): {current_score:.1%} <<<")
        
        # Guardar en historial de predicciones
        history_path = "data/predictions_history.csv"
        new_record = pd.DataFrame([{
            "Fecha_Ejecucion": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "Mes_Actual": last_date,
            "Indice_Viabilidad": current_score
        }])
        
        if os.path.exists(history_path):
            history_df = pd.read_csv(history_path)
            history_df = pd.concat([history_df, new_record], ignore_index=True)
        else:
            history_df = new_record
            
        history_df.to_csv(history_path, index=False)
        logger.info("Registro de probabilidad guardado en predictions_history.csv")
        
        # Clasificar la viabilidad sin emojis ni slop
        if current_score >= 0.65:
            opinion = "Viabilidad Alta. El entorno macroeconómico actual es altamente favorable. La combinación de baja inflación y brecha con buena aprobación empujan el índice al alza."
        elif current_score >= 0.40:
            opinion = "Viabilidad Media (Escenario Competitivo). Las variables muestran un cuadro mixto. Hay estabilidad en algunos frentes, pero debilidad en otros."
        else:
            opinion = "Viabilidad Baja. El contexto actual refleja fuertes tensiones macroeconómicas, lo que presiona el índice hacia abajo."

        def safe_float(val):
            return None if pd.isna(val) else float(val)

        # Guardar latest_prediction.json para la web
        latest_data = {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "date": last_date,
            "viability_score": safe_float(current_score),
            "opinion": opinion,
            "variables": {
                "ICG_Aprobacion": safe_float(last_row.get('ICG_Aprobacion')),
                "ICC_Nivel": safe_float(last_row.get('icc_nivel')),
                "IPC_BCRA": safe_float(last_row.get('IPC_BCRA')),
                "IPC_Delta_1M": safe_float(last_row.get('IPC_Delta_1M')),
                "Salario_Delta_1M": safe_float(last_row.get('Salario_Delta_1M')),
                "Empleo_Delta_1M": safe_float(last_row.get('Empleo_Delta_1M')),
                "Brecha_Cambiaria": safe_float(last_row.get('Brecha_Cambiaria')),
                "RIN_Est_USD": safe_float(last_row.get('rin_est_usd')),
                "Resultado_Financiero_Millones": safe_float(last_row.get('Resultado_Financiero_Millones')),
                "EMAE_Delta_1M": safe_float(last_row.get('EMAE_Delta_1M')),
                "IVS": safe_float(last_row.get('ivs'))
            }
        }
        os.makedirs("docs", exist_ok=True)
        with open("docs/data.json", "w", encoding="utf-8") as f:
            json.dump(latest_data, f, ensure_ascii=False, indent=4)
        logger.info("JSON data guardado en docs/data.json")

        # Actualizar README.md
        readme_path = "README.md"
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                readme_content = f.read()
                
            timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
            new_prediction_text = (
                f"<!-- PREDICTION_START -->\n"
                f"**Índice de Viabilidad de Reelección:** {current_score:.1%}\n\n"
                f"**Análisis:** {opinion}\n\n"
                f"*(Última actualización: {timestamp})*\n"
                f"<!-- PREDICTION_END -->"
            )
            
            updated_readme = re.sub(
                r"<!-- PREDICTION_START -->.*?<!-- PREDICTION_END -->",
                new_prediction_text,
                readme_content,
                flags=re.DOTALL
            )
            
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(updated_readme)
            logger.info("README.md actualizado con la nueva proyección y opinión.")
            
    else:
        logger.warning("No hay datos recientes.")
        
    logger.info("=== PIPELINE COMPLETADO EXITOSAMENTE ===")

if __name__ == "__main__":
    run_pipeline()
