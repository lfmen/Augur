"""
SCRAPER 4: Canasta Básica Alimentaria (CBA) vs. Salario Mínimo (SMVM)
======================================================================
Fuente CBA  : INDEC → indec.gob.ar (Excel mensual, GBA)
              https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-43-149
Fuente SMVM : Ministerio de Trabajo → argentina.gob.ar (tabla de resoluciones)
              https://www.argentina.gob.ar/trabajo/salariominimo

Métrica producida: Índice de Vulnerabilidad Social (IVS)
---------------------------------------------------------
  IVS = CBA_familia_tipo / SMVM

  Si IVS > 1  → el SMVM NO alcanza para cubrir la alimentación básica
                 de una familia tipo (4 integrantes = 3.09 adultos eq.)
                 → vulnerabilidad extrema

  Si IVS ≤ 1  → el SMVM cubre la CBA

  dias_alim_smvm = 30 / IVS  → días de mes que el SMVM puede alimentar
                                a la familia tipo

Por qué importa electoralmente
--------------------------------
Para los sectores populares del Gran Buenos Aires (los que definen las
elecciones en la Provincia de Buenos Aires), la inflación de alimentos
es LA inflación. El IVS > 1 es el termómetro más directo de la
"pobreza activa": gente que trabaja el mes completo y no puede comer.
"""

import io
import re
import warnings
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import pandas as pd
import src.augur.scrapers.requests_retry as requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# URLs fuente
# ---------------------------------------------------------------------------
INDEC_CBA_PAGE = "https://www.indec.gob.ar/indec/web/Nivel4-Tema-4-43-149"
INDEC_CBA_EXCEL_PATTERN = (
    "https://www.indec.gob.ar/ftp/cuadros/sociedad/canbasicamental_{año}{mes}.xls"
)
# URL directa conocida del último Excel publicado:
INDEC_CBA_EXCEL_FALLBACK = (
    "https://www.indec.gob.ar/uploads/informesdeprensa/"
    "canasta_{mes}_{año}{hash}.xls"  # patrón con hash variable
)

SMVM_PAGE_URL = "https://www.argentina.gob.ar/trabajo/salariominimo"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScraperArgentina/1.0)",
    "Accept-Language": "es-AR,es;q=0.9",
}

# Familia tipo INDEC: 4 integrantes = 3.09 adultos equivalentes
ADULTOS_EQ_FAMILIA_TIPO = 3.09

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
    # abreviaturas
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


# ---------------------------------------------------------------------------
# Descarga CBA (Datos Argentina API)
# ---------------------------------------------------------------------------
def get_cba_serie() -> pd.DataFrame:
    """
    Obtiene la serie de Canasta Básica Alimentaria desde la API de Datos Argentina.
    Utiliza el ID: 444.1_CANASTA_BARIAGBA_0_0_26_47 (CBA GBA)
    y 444.1_CANASTA_batotGBA_0_0_26_47 (CBT GBA).
    
    Retorna
    -------
    pd.DataFrame con índice mensual y columnas:
        cba_adulto_eq    : CBA por adulto equivalente (pesos)
        cba_familia_tipo : CBA para familia tipo (4 integrantes, pesos)
        cbt_adulto_eq    : CBT por adulto equivalente (pesos)
        cbt_familia_tipo : CBT para familia tipo (pesos)
    """
    print("  [CBA] Extrayendo CBA y CBT desde API Datos Argentina...")
    url = "https://apis.datos.gob.ar/series/api/series"
    params = {
        "ids": "444.1_CANASTA_BARIAGBA_0_0_26_47,444.1_CANASTA_batotGBA_0_0_26_47",
        "format": "json",
        "limit": 5000
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            raise ValueError("API devolvió JSON sin datos.")
            
        df = pd.DataFrame(data, columns=["fecha", "cba_adulto_eq", "cbt_adulto_eq"])
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.set_index("fecha").dropna()
        df.index = df.index.to_period("M").to_timestamp()
        
        df["cba_familia_tipo"] = df["cba_adulto_eq"] * ADULTOS_EQ_FAMILIA_TIPO
        df["cbt_familia_tipo"] = df["cbt_adulto_eq"] * ADULTOS_EQ_FAMILIA_TIPO
        
        print(f"  [CBA] {len(df)} registros descargados desde API.")
        return df.sort_index()
    except Exception as e:
        raise RuntimeError(f"Error extrayendo CBA desde API: {e}")


# ---------------------------------------------------------------------------
# Descarga SMVM (Datos Argentina API)
# ---------------------------------------------------------------------------
def get_smvm_serie() -> pd.Series:
    """
    Obtiene la serie del SMVM desde la API de Datos Argentina.
    Utiliza el ID: 57.1_SMVMM_0_M_34
    
    Retorna pd.Series con índice DatetimeIndex mensual (fin de mes) y valores en pesos.
    """
    print("  [SMVM] Extrayendo Salario Mínimo desde API Datos Argentina...")
    url = "https://apis.datos.gob.ar/series/api/series"
    params = {
        "ids": "57.1_SMVMM_0_M_34",
        "format": "json",
        "limit": 5000
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", [])
        if not data:
            raise ValueError("API devolvió JSON sin datos.")
            
        df = pd.DataFrame(data, columns=["fecha", "smvm"])
        df["fecha"] = pd.to_datetime(df["fecha"])
        df = df.set_index("fecha").dropna()
        df.index = df.index.to_period("M").to_timestamp()
        
        serie = df["smvm"].sort_index()
        print(f"  [SMVM] {len(serie)} registros descargados desde API.")
        return serie
    except Exception as e:
        raise RuntimeError(f"Error extrayendo SMVM desde API: {e}")


def _expandir_smvm_mensual(smvm_vigencias: pd.Series) -> pd.Series:
    """
    La API ya devuelve la serie mensualizada, por lo que esta función 
    solo la retorna igual o completa meses faltantes si existieran huecos.
    Usa freq='MS' (inicio de mes) para alinearse con el pipeline.
    """
    inicio = smvm_vigencias.index.min()
    # Limitar hasta el mes actual (no incluir meses futuros)
    hoy = pd.Timestamp(date.today())
    fin = hoy.to_period('M').to_timestamp()  # inicio del mes actual
    indice_mensual = pd.date_range(inicio, fin, freq="MS")

    smvm_mensual = smvm_vigencias.reindex(
        smvm_vigencias.index.union(indice_mensual)
    ).sort_index().ffill()

    return smvm_mensual.reindex(indice_mensual)


# ---------------------------------------------------------------------------
# Pipeline principal: IVS
# ---------------------------------------------------------------------------
def calcular_ivs() -> pd.DataFrame:
    """
    Calcula el Índice de Vulnerabilidad Social (IVS = CBA familia tipo / SMVM).

    Retorna
    -------
    pd.DataFrame con columnas:
        cba_familia_tipo : CBA para familia de 4 (3.09 adultos eq.), pesos
        smvm             : Salario Mínimo Vital y Móvil vigente, pesos
        ivs              : CBA / SMVM (>1 → emergencia)
        dias_alim_smvm   : días del mes que el SMVM alcanza para alimentar
        var_ia_ivs_pct   : variación interanual del IVS (%)
        alerta           : nivel de alerta social
    """
    print("=== Scraper 4: CBA vs SMVM – Índice de Vulnerabilidad Social ===")

    cba = get_cba_serie()
    smvm_vigencias = get_smvm_serie()
    smvm = _expandir_smvm_mensual(smvm_vigencias)

    # Alinear
    if "cba_familia_tipo" not in cba.columns:
        # Calcular si solo hay CBA por adulto equivalente
        if "cba_adulto_eq" in cba.columns:
            cba["cba_familia_tipo"] = cba["cba_adulto_eq"] * ADULTOS_EQ_FAMILIA_TIPO
        else:
            raise ValueError("No se encontró CBA en el DataFrame parseado.")

    df = pd.DataFrame({
        "cba_familia_tipo": cba["cba_familia_tipo"],
        "smvm": smvm,
    }).dropna()

    if df.empty:
        raise ValueError("No hay datos solapados entre CBA y SMVM.")

    # Métricas centrales
    df["ivs"] = (df["cba_familia_tipo"] / df["smvm"]).round(4)
    df["dias_alim_smvm"] = (30 / df["ivs"]).round(1)

    # CBT si disponible
    if "cbt_familia_tipo" in cba.columns:
        df["cbt_familia_tipo"] = cba["cbt_familia_tipo"].reindex(df.index)
        df["ivs_pobreza"] = (df["cbt_familia_tipo"] / df["smvm"]).round(4)

    # Variaciones
    df["var_ia_ivs_pct"] = df["ivs"].pct_change(12) * 100
    df["var_ia_cba_pct"] = df["cba_familia_tipo"].pct_change(12) * 100
    df["var_ia_smvm_pct"] = df["smvm"].pct_change(12) * 100

    # Alerta social
    def alerta(v):
        if pd.isna(v):
            return "N/D"
        if v > 1.5:
            return "EMERGENCIA (SMVM cubre menos del 66% de la CBA)"
        if v > 1.0:
            return "CRÍTICO (SMVM no cubre la CBA familiar)"
        if v > 0.85:
            return "TENSO (SMVM cubre la CBA con menos del 15% de margen)"
        return "TOLERABLE (SMVM supera la CBA)"

    df["alerta"] = df["ivs"].map(alerta)

    # Comparación inflación alimentos vs salario
    def diagnóstico_salario(row):
        if pd.isna(row.get("var_ia_cba_pct")) or pd.isna(row.get("var_ia_smvm_pct")):
            return "N/D"
        diff = row["var_ia_smvm_pct"] - row["var_ia_cba_pct"]
        if diff > 3:
            return "SMVM le gana a los alimentos"
        if diff < -3:
            return "Alimentos le ganan al SMVM (deterioro)"
        return "Empate técnico"

    df["diagnóstico"] = df.apply(diagnóstico_salario, axis=1)

    # Reporte
    ult = df.iloc[-1]
    print(f"\n  Último dato        : {df.index[-1].strftime('%B %Y')}")
    print(f"  CBA familia tipo   : ${ult['cba_familia_tipo']:,.0f}")
    print(f"  SMVM               : ${ult['smvm']:,.0f}")
    print(f"  IVS                : {ult['ivs']:.3f} ({'> 1 → EMERGENCIA' if ult['ivs'] > 1 else '≤ 1 → OK'})")
    print(f"  Días alim. c/SMVM  : {ult['dias_alim_smvm']:.1f} días del mes")
    print(f"  Alerta             : {ult['alerta']}")
    print(f"  Diagnóstico        : {ult['diagnóstico']}")

    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IVS: CBA vs SMVM Argentina")
    parser.add_argument("--output", default="ivs_cba_smvm.csv", help="Archivo de salida")
    args = parser.parse_args()

    df = calcular_ivs()
    df.to_csv(args.output)
    print(f"\n✓ Guardado en {args.output}")
