import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def align_and_impute(
    df_indec: pd.DataFrame, 
    df_bcra: pd.DataFrame, 
    df_mo: pd.DataFrame,
    df_salario: pd.DataFrame, 
    df_icc: pd.DataFrame, 
    df_rin: pd.DataFrame,
    df_ivs: pd.DataFrame,
    df_macro: pd.DataFrame = None
) -> pd.DataFrame:
    """
    Une los datasets reales extraídos de las APIs.
    """
    logger.info("Uniendo y alineando datasets reales...")
    
    if df_macro is None:
        df_macro = pd.DataFrame()
        
    dfs = []
    for df in [df_indec, df_bcra, df_salario, df_icc, df_rin, df_ivs, df_macro]:
        if not df.empty:
            df_copy = df.copy()
            if not isinstance(df_copy.index, pd.DatetimeIndex):
                # Intentamos parsear por si el índice no es fecha
                try:
                    df_copy.index = pd.to_datetime(df_copy.index)
                except Exception:
                    pass
            if isinstance(df_copy.index, pd.DatetimeIndex):
                # Normalizar índices a start of month si son fin de mes
                df_copy.index = df_copy.index.to_period('M').to_timestamp()
                # Eliminar duplicados en el index por si acaso
                df_copy = df_copy[~df_copy.index.duplicated(keep='last')]
                dfs.append(df_copy)

    if not df_mo.empty:
        df_mo_aligned = df_mo.copy()
        if not isinstance(df_mo_aligned.index, pd.DatetimeIndex):
            df_mo_aligned.index = pd.to_datetime(df_mo_aligned.index)
        df_mo_aligned.index = df_mo_aligned.index.to_period('M').to_timestamp()
        df_mo_aligned = df_mo_aligned.dropna(how='all')
        df_mo_aligned = df_mo_aligned[~df_mo_aligned.index.duplicated(keep='last')]
        if not df_mo_aligned.empty:
            dfs.append(df_mo_aligned)
        
    if not dfs:
        logger.error("Todos los dataframes están vacíos.")
        return pd.DataFrame()
        
    # Inicializar df_aligned con el primero
    df_aligned = dfs[0]
    for df in dfs[1:]:
        # Join externo iterativo
        df_aligned = df_aligned.join(df, how='outer', rsuffix='_dup')
        
    # Limpiar columnas duplicadas por colisiones de nombres si hubieran
    cols_to_drop = [c for c in df_aligned.columns if c.endswith('_dup')]
    df_aligned = df_aligned.drop(columns=cols_to_drop)
        
    # Ordenar por fecha
    df_aligned = df_aligned.sort_index()
    
    # Asegurarnos de tener columnas necesarias para features
    cols = ['EMAE', 'RIPTE', 'ICG_Aprobacion', 'Reservas', 'IPC_BCRA', 'Brecha_Cambiaria', 'Riesgo_Pais',
            'salario_real_idx', 'icc_nivel', 'rin_est_usd', 'ivs', 'Empleo_Privado_Miles', 'Resultado_Financiero_Millones']
    for c in cols:
        if c not in df_aligned.columns:
            df_aligned[c] = np.nan
            
    return df_aligned

if __name__ == "__main__":
    df_final = align_and_impute(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    print("Muestra alineada:", df_final)
