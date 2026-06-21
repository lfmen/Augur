import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ViabilityIndex:
    """
    Índice Cuantitativo Determinístico de Viabilidad de Reelección.
    Calcula un score del 0 al 100% basado en 8 variables macroeconómicas reales.
    """
    def __init__(self):
        # Pesos históricos adaptados a Argentina (Total 100%)
        self.weights = {
            'Inflacion_IPC': 0.15,
            'Inflacion_Aceleracion': 0.10,
            'Salario_Real': 0.15,
            'Brecha_Cambiaria_Hist': 0.10,
            'Aprobacion_ICG': 0.10,
            'Empleo_Privado': 0.10,
            'Reservas_Netas_RIN': 0.10,
            'Resultado_Fiscal': 0.10,
            'Vulnerabilidad_IVS': 0.05,
            'Confianza_ICC': 0.05
        }
        
    def _normalize_icg(self, value):
        if pd.isna(value): return 0.5
        norm = (value - 1.0) / (3.5 - 1.0)
        return float(np.clip(norm, 0, 1))

    def _normalize_icc(self, value):
        if pd.isna(value): return 0.5
        norm = (value - 30.0) / (55.0 - 30.0)
        return float(np.clip(norm, 0, 1))
        
    def _normalize_ipc(self, value):
        if pd.isna(value): return 0.5
        norm = 1 - ((value - 2) / (15 - 2))
        return float(np.clip(norm, 0, 1))
        
    def _normalize_infla_accel(self, delta):
        # Castiga fuerte si la inflación acelera (+2 puntos o más) -> 0
        # Premia si desciende (-2 puntos o más) -> 1
        if pd.isna(delta): return 0.5
        norm = 1 - ((delta - (-2.0)) / (2.0 - (-2.0)))
        return float(np.clip(norm, 0, 1))

    def _normalize_salario(self, delta_1m):
        if pd.isna(delta_1m): return 0.5
        norm = (delta_1m - (-2.0)) / (2.0 - (-2.0))
        return float(np.clip(norm, 0, 1))
        
    def _normalize_empleo(self, delta_1m):
        # Creación de empleo (+0.5% mensual) es excelente -> 1
        # Destrucción de empleo (-0.5% mensual) es pésimo -> 0
        if pd.isna(delta_1m): return 0.5
        norm = (delta_1m - (-0.5)) / (0.5 - (-0.5))
        return float(np.clip(norm, 0, 1))
        
    def _normalize_brecha(self, value):
        if pd.isna(value): return 0.5
        norm = 1 - ((value - 10) / (100 - 10))
        return float(np.clip(norm, 0, 1))

    def _normalize_rin(self, value):
        if pd.isna(value): return 0.5
        norm = (value - (-5000)) / (5000 - (-5000))
        return float(np.clip(norm, 0, 1))
        
    def _normalize_fiscal(self, value):
        # Déficit mensual severo (-300,000 millones) -> 0
        # Superávit mensual sólido (+300,000 millones) -> 1
        if pd.isna(value): return 0.5
        norm = (value - (-300000)) / (300000 - (-300000))
        return float(np.clip(norm, 0, 1))

    def _normalize_ivs(self, value):
        if pd.isna(value): return 0.5
        norm = 1 - ((value - 0.8) / (1.05 - 0.8))
        return float(np.clip(norm, 0, 1))

    def calculate_score(self, row: pd.Series) -> dict:
        icg = row.get('ICG_Aprobacion', np.nan)
        icc = row.get('icc_nivel', np.nan)
        ipc = row.get('IPC_BCRA', np.nan)
        infla_accel = row.get('IPC_Delta_1M', np.nan)
        salario = row.get('Salario_Delta_1M', np.nan)
        empleo = row.get('Empleo_Delta_1M', np.nan)
        brecha = row.get('Brecha_Cambiaria', np.nan)
        rin = row.get('rin_est_usd', np.nan)
        fiscal = row.get('Resultado_Financiero_Millones', np.nan)
        ivs = row.get('ivs', np.nan)
        
        score_icg = self._normalize_icg(icg) * self.weights['Aprobacion_ICG']
        score_icc = self._normalize_icc(icc) * self.weights['Confianza_ICC']
        score_ipc = self._normalize_ipc(ipc) * self.weights['Inflacion_IPC']
        score_infla_accel = self._normalize_infla_accel(infla_accel) * self.weights['Inflacion_Aceleracion']
        score_salario = self._normalize_salario(salario) * self.weights['Salario_Real']
        score_empleo = self._normalize_empleo(empleo) * self.weights['Empleo_Privado']
        score_brecha = self._normalize_brecha(brecha) * self.weights['Brecha_Cambiaria_Hist']
        score_rin = self._normalize_rin(rin) * self.weights['Reservas_Netas_RIN']
        score_fiscal = self._normalize_fiscal(fiscal) * self.weights['Resultado_Fiscal']
        score_ivs = self._normalize_ivs(ivs) * self.weights['Vulnerabilidad_IVS']
        
        total_score = (score_icg + score_icc + score_ipc + score_infla_accel + 
                       score_salario + score_empleo + score_brecha + score_rin + 
                       score_fiscal + score_ivs)
        
        return {
            'Total_Score': total_score,
            'Components': {
                'Aprobacion_ICG': score_icg,
                'Confianza_ICC': score_icc,
                'Inflacion_IPC': score_ipc,
                'Inflacion_Aceleracion': score_infla_accel,
                'Salario_Real': score_salario,
                'Empleo_Privado': score_empleo,
                'Brecha_Cambiaria_Hist': score_brecha,
                'Reservas_Netas_RIN': score_rin,
                'Resultado_Fiscal': score_fiscal,
                'Vulnerabilidad_IVS': score_ivs
            },
            'Raw_Values': {
                'ICG': icg,
                'ICC': icc,
                'IPC': ipc,
                'Inflacion_Aceleracion': infla_accel,
                'Salario_Delta': salario,
                'Empleo_Delta': empleo,
                'Brecha': brecha,
                'RIN': rin,
                'Resultado_Fiscal': fiscal,
                'IVS': ivs
            }
        }

    def score_series(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        scores = [self.calculate_score(row)['Total_Score'] for idx, row in df.iterrows()]
        df_out = df.copy()
        df_out['Viability_Score'] = scores
        return df_out
