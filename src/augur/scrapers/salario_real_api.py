"""
SCRAPER 1: Salario Real (RIPTE deflactado por IPC)
===================================================
Fuente RIPTE : Ministerio de Trabajo → argentina.gob.ar (Excel mensual)
Fuente IPC   : INDEC API pública → indec.gob.ar (Excel mensual)

Métrica producida
-----------------
  salario_real_idx  : RIPTE a pesos constantes del mes base (base=100)
  var_ia_pct        : variación interanual del salario real (%)
  gana_o_pierde     : "GANA" si el salario le gana a la inflación, "PIERDE" si no

Por qué importa electoralmente
--------------------------------
El poder adquisitivo real es el indicador histórico más predictivo del
resultado en elecciones argentinas. Si var_ia_pct > 0, el bolsillo mejoró
(el gobierno tiende a obtener mejor performance). Si < 0, el votante
castiga al oficialismo.
"""

import io
import re
import warnings
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import src.augur.scrapers.requests_retry as requests

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constantes de fuentes
# ---------------------------------------------------------------------------
RIPTE_URL = "https://www.argentina.gob.ar/trabajo/seguridadsocial/ripte"
# La URL del Excel de RIPTE cambia cada mes; la página la linkea dinámicamente.
# Fallback directo al último Excel publicado (patrón histórico):
RIPTE_EXCEL_PATTERN = "https://www.argentina.gob.ar/sites/default/files/ripte_{año}{mes}.xlsx"

# IPC: INDEC publica un Excel con la serie completa de índices
IPC_URL = "https://www.indec.gob.ar/ftp/cuadros/economia/sh_ipc_aperturas.xls"
# Alternativa más estable: serie desde API de estadisticasbcra (usa datos INDEC)
IPC_API_URL = "https://api.estadisticasbcra.com/ipc"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ScraperArgentina/1.0; "
        "+https://github.com/tu-proyecto)"
    )
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fetch_json(url: str, token: Optional[str] = None) -> list:
    """GET JSON desde una API. Soporta Bearer token opcional."""
    headers = {**HEADERS}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()


def _mes_str(d: date) -> str:
    """Convierte date → 'YYYY-MM' para uso como índice."""
    return d.strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Descarga de IPC
# ---------------------------------------------------------------------------
def get_ipc_serie(token: Optional[str] = None) -> pd.Series:
    """
    Descarga la serie mensual del IPC (nivel general, base dic-2016=100)
    desde el CSV oficial de Datos Argentina.

    Retorna
    -------
    pd.Series con índice DatetimeIndex (frecuencia mensual, fin de mes)
    y valores float del índice IPC.
    """
    print("  [IPC] Extrayendo IPC Nivel General desde CSV oficial de Datos Argentina...")
    url = "https://infra.datos.gob.ar/catalog/sspm/dataset/145/distribution/145.3/download/indice-precios-al-consumidor-nivel-general-base-diciembre-2016-mensual.csv"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        
        # El CSV tiene columnas: "indice_tiempo" e "ipc_ng_nacional"
        time_col = df.columns[0]
        val_col = df.columns[1]
        
        df[time_col] = pd.to_datetime(df[time_col])
        df = df.set_index(time_col)
        df.index = df.index.to_period("M").to_timestamp()
        
        serie = df[val_col].astype(float).sort_index()
        print(f"  [IPC] {len(serie)} registros desde CSV oficial.")
        return serie
    except Exception as e:
        raise RuntimeError(f"Error descargando IPC desde CSV oficial: {e}")


# ---------------------------------------------------------------------------
# Descarga de RIPTE
# ---------------------------------------------------------------------------
def get_ripte_serie() -> pd.Series:
    """
    Obtiene la serie mensual del RIPTE desde la API de Datos Argentina,
    reutilizando la función fetch_api_indec del scraper de INDEC.
    """
    from src.augur.scrapers.indec_api import fetch_api_indec
    print("  [RIPTE] Extrayendo desde API Datos Argentina...")
    df = fetch_api_indec()
    if df.empty or "RIPTE" not in df.columns:
        raise RuntimeError("No se pudo obtener el RIPTE desde la API.")
    
    serie = df["RIPTE"].dropna()
    # Ensure index is end of month
    serie.index = pd.to_datetime(serie.index).to_period("M").to_timestamp()
    print(f"  [RIPTE] {len(serie)} registros parseados desde API.")
    return serie


# ---------------------------------------------------------------------------
# Cálculo del Salario Real
# ---------------------------------------------------------------------------
def calcular_salario_real(
    base_mes: Optional[str] = None,
    token_bcra: Optional[str] = None,
) -> pd.DataFrame:
    """
    Cruza RIPTE con IPC y calcula el Salario Real.

    Parámetros
    ----------
    base_mes   : mes de referencia como '2017-12' (si None, usa primer mes disponible)
    token_bcra : Bearer token para la API de estadisticasbcra (opcional; sin token
                 el endpoint IPC puede requerir registro)

    Retorna
    -------
    pd.DataFrame con columnas:
        ripte_nominal    : RIPTE en pesos corrientes
        ipc              : Índice de Precios al Consumidor (base dic-2016=100)
        ipc_base100      : IPC rebaseado al mes elegido
        salario_real_idx : RIPTE deflactado (pesos constantes del mes base, base=100)
        var_ia_pct       : variación interanual del salario real (%)
        gana_o_pierde    : "GANA" / "PIERDE" / "NEUTRO"
    """
    print("=== Scraper 1: Salario Real (RIPTE / IPC) ===")

    ipc = get_ipc_serie(token=token_bcra)
    ripte = get_ripte_serie()

    # Alinear en período mensual común
    df = pd.DataFrame({"ripte_nominal": ripte, "ipc": ipc}).dropna()

    if df.empty:
        raise ValueError("No hay datos solapados entre RIPTE e IPC.")

    # Rebase del IPC al mes elegido (base=100)
    if base_mes is None:
        base_mes = _mes_str(df.index[0])
    base_dt = pd.to_datetime(base_mes) + pd.offsets.MonthEnd(0)
    if base_dt not in df.index:
        base_dt = df.index[df.index.get_indexer([base_dt], method="nearest")[0]]

    ipc_base = df.loc[base_dt, "ipc"]
    df["ipc_base100"] = df["ipc"] / ipc_base * 100

    # Salario real: RIPTE deflactado
    # Fórmula: salario_real = RIPTE_nominal / (IPC / IPC_base) * 100
    # → equivale a RIPTE en pesos del mes base, expresado como índice base=100
    df["salario_real_idx"] = (df["ripte_nominal"] / df["ipc_base100"]) * 100

    # Variación interanual del salario real
    df["var_ia_pct"] = df["salario_real_idx"].pct_change(12) * 100

    # Semáforo
    def semaforo(v):
        if pd.isna(v):
            return "N/D"
        if v > 0.5:
            return "GANA"
        if v < -0.5:
            return "PIERDE"
        return "NEUTRO"

    df["gana_o_pierde"] = df["var_ia_pct"].map(semaforo)

    print(f"\n  Último dato disponible: {df.index[-1].strftime('%B %Y')}")
    ultimo = df.iloc[-1]
    print(f"  RIPTE nominal      : ${ultimo['ripte_nominal']:,.0f}")
    print(f"  Salario real idx   : {ultimo['salario_real_idx']:.1f}")
    print(f"  Var. interanual    : {ultimo['var_ia_pct']:+.1f}%")
    print(f"  Diagnóstico        : {ultimo['gana_o_pierde']}")

    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Salario Real Argentina (RIPTE/IPC)")
    parser.add_argument("--base", default=None, help="Mes base ej. 2019-12")
    parser.add_argument("--token", default=None, help="Bearer token estadisticasbcra")
    parser.add_argument("--output", default="salario_real.csv", help="Archivo de salida")
    args = parser.parse_args()

    df = calcular_salario_real(base_mes=args.base, token_bcra=args.token)
    df.to_csv(args.output)
    print(f"\n✓ Guardado en {args.output}")
