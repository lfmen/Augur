import math
import pandas as pd
import numpy as np
from src.augur.modeling.model_selection import ViabilityIndex

def test_viability_index_bounds():
    """Prueba que el índice siempre devuelva valores entre 0 y 1."""
    idx = ViabilityIndex()
    
    # Caso ideal
    row_ideal = pd.Series({
        'ICG_Aprobacion': 4.5, 
        'icc_nivel': 70.0, 
        'IPC_BCRA': 1.0, 
        'IPC_Delta_1M': -3.0,
        'Salario_Delta_1M': 5.0, 
        'Empleo_Delta_1M': 1.0,
        'Brecha_Cambiaria': 5.0, 
        'rin_est_usd': 15000.0, 
        'Resultado_Financiero_Millones': 500000.0,
        'ivs': 0.7
    })
    res_ideal = idx.calculate_score(row_ideal)
    assert 0.95 <= res_ideal['Total_Score'] <= 1.0
    
    # Caso pésimo
    row_pesimo = pd.Series({
        'ICG_Aprobacion': 0.5, 
        'icc_nivel': 10.0, 
        'IPC_BCRA': 20.0, 
        'IPC_Delta_1M': 5.0,
        'Salario_Delta_1M': -5.0, 
        'Empleo_Delta_1M': -2.0,
        'Brecha_Cambiaria': 150.0, 
        'rin_est_usd': -10000.0, 
        'Resultado_Financiero_Millones': -500000.0,
        'ivs': 1.2
    })
    res_pesimo = idx.calculate_score(row_pesimo)
    assert 0.0 <= res_pesimo['Total_Score'] <= 0.05
    
    # Caso con nulos
    row_nulos = pd.Series({
        'ICG_Aprobacion': np.nan, 
        'icc_nivel': np.nan, 
        'IPC_BCRA': np.nan, 
        'IPC_Delta_1M': np.nan,
        'Salario_Delta_1M': np.nan, 
        'Empleo_Delta_1M': np.nan,
        'Brecha_Cambiaria': np.nan, 
        'rin_est_usd': np.nan, 
        'Resultado_Financiero_Millones': np.nan,
        'ivs': np.nan
    })
    res_nulos = idx.calculate_score(row_nulos)
    assert math.isclose(res_nulos['Total_Score'], 0.5, abs_tol=1e-9)

def test_viability_index_series():
    """Prueba el cálculo sobre un dataframe entero."""
    idx = ViabilityIndex()
    df = pd.DataFrame([
        {
            'ICG_Aprobacion': 2.0, 'icc_nivel': 30.0, 'IPC_BCRA': 5.0, 'IPC_Delta_1M': 1.0, 
            'Salario_Delta_1M': -1.0, 'Empleo_Delta_1M': -0.5, 'Brecha_Cambiaria': 30.0, 
            'rin_est_usd': -1000.0, 'Resultado_Financiero_Millones': -100000.0, 'ivs': 1.0
        },
        {
            'ICG_Aprobacion': 2.5, 'icc_nivel': 40.0, 'IPC_BCRA': 4.0, 'IPC_Delta_1M': -1.0, 
            'Salario_Delta_1M': 1.0, 'Empleo_Delta_1M': 0.5, 'Brecha_Cambiaria': 25.0, 
            'rin_est_usd': 1000.0, 'Resultado_Financiero_Millones': 100000.0, 'ivs': 0.9
        }
    ])
    df_scored = idx.score_series(df)
    assert 'Viability_Score' in df_scored.columns
    assert len(df_scored) == 2
    assert df_scored['Viability_Score'].iloc[1] > df_scored['Viability_Score'].iloc[0] # El segundo mes es mejor
