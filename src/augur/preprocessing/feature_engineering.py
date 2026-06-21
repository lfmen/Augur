import pandas as pd
import numpy as np

def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula indicadores derivados sobre la serie de tiempo real continua de Argentina.
    Calcula variaciones porcentuales y promedios móviles para el Scoring.
    """
    if df.empty:
        return df
        
    df = df.copy()
    
    # Asegurar orden cronológico
    df = df.sort_index()
    
    # 1. Deltas Inflacionarios (Aceleración/Desaceleración)
    if 'IPC_BCRA' in df.columns:
        df['IPC_Delta_1M'] = df['IPC_BCRA'].diff(1)
        df['IPC_Delta_3M'] = df['IPC_BCRA'].diff(3)
        df['IPC_Media_3M'] = df['IPC_BCRA'].rolling(3, min_periods=1).mean()
    else:
        df['IPC_Delta_1M'] = np.nan
        df['IPC_Delta_3M'] = np.nan
        df['IPC_Media_3M'] = np.nan
        
    # 2. Tendencia de Aprobación
    if 'ICG_Aprobacion' in df.columns:
        df['ICG_Delta_1M'] = df['ICG_Aprobacion'].diff(1)
        df['ICG_Media_Movil_3M'] = df['ICG_Aprobacion'].rolling(3, min_periods=1).mean()
    else:
        df['ICG_Delta_1M'] = np.nan
        df['ICG_Media_Movil_3M'] = np.nan
        
    # 3. Volatilidad Cambiaria y Riesgo
    if 'Brecha_Cambiaria' in df.columns:
        df['Brecha_Volatilidad_3M'] = df['Brecha_Cambiaria'].rolling(3, min_periods=1).std()
    else:
        df['Brecha_Volatilidad_3M'] = np.nan
        
    if 'Riesgo_Pais' in df.columns:
        df['Riesgo_Pais_Delta_3M'] = df['Riesgo_Pais'].diff(3)
    else:
        df['Riesgo_Pais_Delta_3M'] = np.nan
        
    # 4. Actividad
    if 'EMAE' in df.columns:
        df['EMAE_Delta_1M'] = df['EMAE'].pct_change(1, fill_method=None) * 100
    else:
        df['EMAE_Delta_1M'] = np.nan
        
    if 'Empleo_Privado_Miles' in df.columns:
        df['Empleo_Delta_1M'] = df['Empleo_Privado_Miles'].pct_change(fill_method=None) * 100
    else:
        df['Empleo_Delta_1M'] = np.nan
        
    # 5. Nuevos Índices
    if 'salario_real_idx' in df.columns:
        df['Salario_Delta_1M'] = df['salario_real_idx'].pct_change(1, fill_method=None) * 100
    else:
        df['Salario_Delta_1M'] = np.nan
        
    if 'icc_nivel' in df.columns:
        df['ICC_Delta_1M'] = df['icc_nivel'].pct_change(1, fill_method=None) * 100
    else:
        df['ICC_Delta_1M'] = np.nan
        
    if 'rin_est_usd' in df.columns:
        df['RIN_Delta_1M'] = df['rin_est_usd'].diff(1)
    else:
        df['RIN_Delta_1M'] = np.nan

    return df

if __name__ == "__main__":
    df_features = create_features(pd.DataFrame())
    print("Features generadas:", df_features)
