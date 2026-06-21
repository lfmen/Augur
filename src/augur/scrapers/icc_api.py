"""
SCRAPER 2: Índice de Confianza del Consumidor (ICC)
====================================================
Fuente: Centro de Investigación en Finanzas (CIF) – Universidad Torcuato Di Tella
URL   : https://www.utdt.edu/ver_contenido.php?id_contenido=2575&id_item_menu=4982

La Di Tella ya no publica el Excel histórico. En cambio, la página HTML
contiene líneas de texto con el dato de variación mensual por período, del tipo:
  'LA CONFIANZA DE LOS CONSUMIDORES SUBE 6,4% EN JUNIO'
  'LA CONFIANZA DE LOS CONSUMIDORES CAE 5,7% EN ABRIL'
  'LA CONFIANZA DE LOS CONSUMIDORES NO CAMBIA EN JUNIO'

Este scraper:
  1. Extrae mes/año + variación mensual % de cada entrada del HTML.
  2. Reconstruye el nivel ICC usando mayo 2025 (~40 puntos) como anclaje.
  3. Retorna un DataFrame con índice DatetimeIndex y columna 'icc_nivel'.

Por qué importa electoralmente
--------------------------------
El ICC mide EXPECTATIVAS, no realidades pasadas. En política, la gente vota
por la esperanza. Un ICC en alza antes de elecciones → señal de optimismo →
beneficia al oficialismo. El subíndice "Situación Personal" es el más
predictivo a nivel individual.
"""

import re
import warnings
from datetime import date

import pandas as pd
import src.augur.scrapers.requests_retry as requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
ICC_PAGE_URL = (
    "https://www.utdt.edu/ver_contenido.php"
    "?id_contenido=2575&id_item_menu=4982"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ScraperArgentina/1.0)",
    "Accept-Language": "es-AR,es;q=0.9",
}

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Valor de anclaje: ICC nivel en mayo 2025 (último dato conocido fiable)
ANCLA_FECHA = pd.Timestamp("2025-05-01")
ANCLA_NIVEL = 40.0


# ---------------------------------------------------------------------------
# Extracción de variaciones desde el HTML
# ---------------------------------------------------------------------------
def _extraer_variaciones_html() -> pd.DataFrame:
    """
    Scrapea la página de la Di Tella y extrae la variación mensual (%) por
    período a partir de las líneas de texto del tipo:
      'LA CONFIANZA DE LOS CONSUMIDORES SUBE 6,4% EN JUNIO'
      'LA CONFIANZA DE LOS CONSUMIDORES CAE 5,7% EN ABRIL'
      'LA CONFIANZA DE LOS CONSUMIDORES NO CAMBIA EN JUNIO'

    Las líneas aparecen en orden descendente (más reciente primero) y
    generalmente no incluyen el año explícito. Se infiere el año partiendo
    del año/mes actual y decrementando cada vez que se detecta una
    transición diciembre→mes_mayor (rollover de año hacia atrás).

    Retorna
    -------
    pd.DataFrame con índice DatetimeIndex (inicio de mes) y columna 'var_pct'
    ordenado cronológicamente.
    """
    print("  [ICC] Scrapeando página HTML de la Di Tella...")
    r = requests.get(ICC_PAGE_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    texto_completo = soup.get_text(separator="\n")
    lineas = [l.strip() for l in texto_completo.splitlines() if l.strip()]

    # Patrón: captura verbo + porcentaje opcional + mes + año opcional
    patron = re.compile(
        r"(SUBE|CAE|BAJA|AUMENTA|DESCIENDE|NO\s+CAMBIA)"
        r"(?:\s+([\d]+[,.][\d]+|\d+)\s*%)?"
        r"\s+EN\s+"
        r"(ENERO|FEBRERO|MARZO|ABRIL|MAYO|JUNIO|JULIO|AGOSTO|"
        r"SEPTIEMBRE|OCTUBRE|NOVIEMBRE|DICIEMBRE)"
        r"(?:\s+(?:DE\s+)?(\d{4}))?",
        re.IGNORECASE,
    )

    # Extraer todos los matches en el orden en que aparecen en la página
    # (descendente: más reciente → más antiguo)
    matches = []
    for linea in lineas:
        m = patron.search(linea)
        if m:
            matches.append(m)

    if not matches:
        print("  [ICC] No se encontraron variaciones en la página HTML.")
        return pd.DataFrame(columns=["fecha", "var_pct"])

    # Asignar años: las entradas vienen de más reciente a más antigua.
    # Empezamos con el año/mes actuales y decrementamos cuando el mes
    # encontrado es >= al mes anterior (rollover hacia atrás en el tiempo).
    hoy = date.today()
    año_actual = hoy.year
    mes_anterior = hoy.month + 1  # +1 para que el primer match siempre pase

    registros = []
    for m in matches:
        direccion = m.group(1).upper().replace(" ", "")
        pct_raw = m.group(2)
        mes_str = m.group(3).lower()
        año_str = m.group(4)

        mes = MESES_ES.get(mes_str, 0)
        if not mes:
            continue

        if año_str:
            # El año está explícito en el texto: úsarlo y recalibrar
            año = int(año_str)
            año_actual = año
            mes_anterior = mes
        else:
            # Inferir año por posición: si el mes es >= mes_anterior,
            # hemos dado la vuelta un año hacia atrás.
            if mes >= mes_anterior:
                año_actual -= 1
            año = año_actual
            mes_anterior = mes

        # Calcular variación
        if "NOCAMBIA" in direccion or pct_raw is None:
            var_pct = 0.0
        else:
            valor = float(pct_raw.replace(",", "."))
            if re.search(r"CAE|BAJA|DESCIEN", direccion, re.I):
                var_pct = -valor
            else:
                var_pct = valor

        fecha = pd.Timestamp(date(año, mes, 1))
        registros.append({"fecha": fecha, "var_pct": var_pct})

    if not registros:
        print("  [ICC] No se encontraron variaciones en la página HTML.")
        return pd.DataFrame(columns=["fecha", "var_pct"])

    df = (
        pd.DataFrame(registros)
        .drop_duplicates("fecha")
        .set_index("fecha")
        .sort_index()
    )
    # Eliminar fechas futuras (posible bug en inferencia de año)
    hoy = pd.Timestamp(date.today()).to_period("M").to_timestamp()
    df = df[df.index <= hoy]
    print(f"  [ICC] {len(df)} variaciones extraídas del HTML.")
    return df


# ---------------------------------------------------------------------------
# Reconstrucción del nivel ICC desde variaciones
# ---------------------------------------------------------------------------
def _reconstruir_nivel(df_var: pd.DataFrame) -> pd.DataFrame:
    """
    A partir de un DataFrame con columna 'var_pct' indexado por fecha (inicio
    de mes), reconstruye el nivel ICC usando el dato de anclaje:
        ANCLA_FECHA = mayo 2025  →  ANCLA_NIVEL = 40.0 puntos

    La fórmula es:
        nivel[t] = nivel[t-1] * (1 + var_pct[t] / 100)

    El anclaje se aplica hacia adelante y hacia atrás.

    Retorna
    -------
    pd.DataFrame con índice DatetimeIndex y columna 'icc_nivel'.
    """
    if df_var.empty:
        return pd.DataFrame(columns=["icc_nivel"])

    # Crear serie completa (índice mensual continuo entre min y max fecha)
    idx_completo = pd.date_range(
        start=df_var.index.min(),
        end=df_var.index.max(),
        freq="MS",  # Month Start
    )
    var = df_var["var_pct"].reindex(idx_completo)

    niveles = pd.Series(index=idx_completo, dtype=float, name="icc_nivel")

    # Si la fecha de anclaje cae dentro del rango, usarla; si no, usar el
    # extremo más cercano del rango disponible como punto de partida.
    if ANCLA_FECHA in idx_completo:
        ancla_idx = idx_completo.get_loc(ANCLA_FECHA)
        niveles.iloc[ancla_idx] = ANCLA_NIVEL

        # Hacia adelante
        for i in range(ancla_idx + 1, len(niveles)):
            vp = var.iloc[i]
            if pd.notna(vp):
                niveles.iloc[i] = niveles.iloc[i - 1] * (1 + vp / 100)
            else:
                niveles.iloc[i] = niveles.iloc[i - 1]  # mantener si falta

        # Hacia atrás
        for i in range(ancla_idx - 1, -1, -1):
            vp = var.iloc[i + 1]
            if pd.notna(vp):
                niveles.iloc[i] = niveles.iloc[i + 1] / (1 + vp / 100)
            else:
                niveles.iloc[i] = niveles.iloc[i + 1]
    else:
        # Anclaje fuera del rango: construir desde el primer punto con nivel=None
        # y luego escalar para que el último punto conocido coincida con el ancla
        # (aproximación razonable cuando no hay superposición).
        print(
            f"  [ICC] Advertencia: fecha de anclaje {ANCLA_FECHA.date()} "
            f"fuera del rango de variaciones. Usando primer punto como base."
        )
        niveles.iloc[0] = ANCLA_NIVEL
        for i in range(1, len(niveles)):
            vp = var.iloc[i]
            if pd.notna(vp):
                niveles.iloc[i] = niveles.iloc[i - 1] * (1 + vp / 100)
            else:
                niveles.iloc[i] = niveles.iloc[i - 1]

    df_nivel = niveles.to_frame()
    df_nivel.index.name = "fecha"
    return df_nivel


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def get_icc_completo() -> pd.DataFrame:
    """
    Obtiene la serie del ICC scrapeando variaciones mensuales desde la página
    HTML de la Di Tella y reconstruyendo el nivel con mayo 2025 ≈ 40 pts.

    Retorna
    -------
    pd.DataFrame con:
        - Índice: DatetimeIndex (inicio de mes, freq='MS')
        - Columna 'icc_nivel': nivel ICC reconstruido
        - Columna 'var_mensual_pct': variación mensual extraída del HTML
        - Columna 'var_ia_pct': variación interanual calculada
        - Columna 'señal_electoral': interpretación política
    """
    print("=== Scraper 2: Índice de Confianza del Consumidor (ICC - Di Tella) ===")

    # 1. Extraer variaciones del HTML
    df_var = _extraer_variaciones_html()

    if df_var.empty:
        raise RuntimeError(
            "No se pudieron extraer variaciones del ICC desde la página HTML.\n"
            f"Verificar manualmente: {ICC_PAGE_URL}"
        )

    # 2. Reconstruir niveles
    df_nivel = _reconstruir_nivel(df_var)

    # 3. Combinar nivel + variaciones en un único DataFrame
    df = df_nivel.copy()
    df["var_mensual_pct"] = df_var["var_pct"].reindex(df.index)

    # 4. Variación interanual
    df["var_ia_pct"] = df["icc_nivel"].pct_change(12) * 100

    # 5. Señal electoral
    def señal(v):
        if pd.isna(v):
            return "N/D"
        if v > 5:
            return "OPTIMISMO (favorece oficialismo)"
        if v < -5:
            return "PESIMISMO (favorece oposición)"
        return "NEUTRO"

    df["señal_electoral"] = df["var_ia_pct"].map(señal)

    # 6. Asegurar que el índice sea inicio de mes (to_period → to_timestamp)
    df.index = df.index.to_period("M").to_timestamp()
    df = df.sort_index()

    # 7. Reporte
    df_clean = df.dropna(subset=["icc_nivel"])
    if not df_clean.empty:
        ult = df_clean.iloc[-1]
        print(f"\n  Último dato : {df_clean.index[-1].strftime('%B %Y')}")
        print(f"  ICC nivel   : {ult['icc_nivel']:.2f} puntos")
        vm = ult.get("var_mensual_pct")
        if pd.notna(vm):
            print(f"  Var. mensual: {vm:+.1f}%")
        via = ult.get("var_ia_pct")
        if pd.notna(via):
            print(f"  Var. interan: {via:+.1f}%")
        print(f"  Señal       : {ult.get('señal_electoral', 'N/D')}")

    return df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ICC Argentina – Universidad Di Tella")
    parser.add_argument("--output", default="icc.csv", help="Archivo de salida CSV")
    args = parser.parse_args()

    df = get_icc_completo()
    df.to_csv(args.output)
    print(f"\n✓ Guardado en {args.output}")
