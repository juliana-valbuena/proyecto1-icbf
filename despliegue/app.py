"""
app.py — Tablero de contratación pública del ICBF (SECOP II)

Responde dos preguntas de negocio:
  1. ¿Qué contratos terminan extendiéndose más allá del plazo pactado?
  2. ¿Qué tan concentrada está la contratación entre proveedores?

Ejecución local:  python app.py   ->  http://127.0.0.1:8050/
Ejecución en EC2: app.run(host="0.0.0.0", ...)  (ver el final del archivo)
"""
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# ======================================================================
# 1. CARGA DE DATOS
# ======================================================================
ext = pd.read_parquet("datos_extensiones.parquet")
con = pd.read_parquet("datos_concentracion.parquet")

# int() de Python: dcc.RangeSlider no acepta claves numpy.int64 en marks
ANIOS = sorted(int(a) for a in ext["anio_firma"].dropna().unique())
DEPTOS = sorted(ext["departamento"].dropna().unique())
MODALIDADES = sorted(ext["modalidad_de_contratacion"].dropna().unique())
ORDEN_RANGO = ["≤3 meses", "3-6 meses", "6-12 meses", ">1 año"]

# Paleta del proyecto
VERDE, ROJO, GRIS, TINTA, PAPEL = "#2F7A3E", "#B3423F", "#6E7A72", "#16261F", "#F2F2EE"
ESCALA = ["#FFF7BC", "#FEC44F", "#F16913", "#B3423F", "#7F1D1D"]

PLANTILLA = dict(
    plot_bgcolor="white", paper_bgcolor="white",
    font=dict(family="IBM Plex Sans, Segoe UI, sans-serif", size=12, color=TINTA),
    margin=dict(l=60, r=30, t=55, b=50),
)

# ======================================================================
# 2. APLICACIÓN
# ======================================================================
app = dash.Dash(__name__, title="Tablero ICBF — Contratación pública")
server = app.server          # necesario para desplegar con gunicorn

# ---------- Componentes reutilizables ----------
def tarjeta(titulo, id_valor, ayuda):
    """Indicador numérico que responde a los filtros."""
    return html.Div(className="tarjeta", children=[
        html.Span(titulo, className="tarjeta-titulo"),
        html.Span(id=id_valor, className="tarjeta-valor"),
        html.Span(ayuda, className="tarjeta-ayuda"),
    ])

# ---------- Panel de filtros ----------
filtros = html.Div(className="filtros", children=[
    html.Div([
        html.Label("Año de firma", className="etiqueta"),
        dcc.RangeSlider(
            id="f-anios", min=min(ANIOS), max=max(ANIOS), step=1,
            value=[min(ANIOS), max(ANIOS)],
            marks={a: str(a) for a in ANIOS},
            tooltip={"placement": "bottom", "always_visible": False},
        ),
    ], className="filtro-ancho"),

    html.Div([
        html.Label("Departamento", className="etiqueta"),
        dcc.Dropdown(
            id="f-depto", options=[{"label": d, "value": d} for d in DEPTOS],
            value=[], multi=True, placeholder="Todos los departamentos",
        ),
    ], className="filtro"),

    html.Div([
        html.Label("Modalidad de contratación", className="etiqueta"),
        dcc.Dropdown(
            id="f-modalidad", options=[{"label": m, "value": m} for m in MODALIDADES],
            value=[], multi=True, placeholder="Todas las modalidades",
        ),
    ], className="filtro"),
])

# ======================================================================
# 3. DISEÑO (layout)
# ======================================================================
app.layout = html.Div(className="pagina", children=[

    # ---------- Encabezado ----------
    html.Div(className="encabezado", children=[
        html.H1("Contratación pública del ICBF"),
        html.P("Instituto Colombiano de Bienestar Familiar · datos de SECOP II, 2017–2026"),
    ]),

    # ---------- Instrucciones ----------
    html.Details(className="instrucciones", open=False, children=[
        html.Summary("Cómo usar este tablero"),
        html.Div([
            html.P("Los filtros de abajo aplican a las dos pestañas al mismo tiempo. "
                   "Si no selecciona nada, se muestran todos los registros."),
            html.Ul([
                html.Li([html.B("Extensiones de plazo: "),
                         "identifica qué contratos reciben días adicionales. "
                         "Útil para revisar cómo se dimensionan los plazos en la planeación."]),
                html.Li([html.B("Concentración de proveedores: "),
                         "muestra qué proporción del valor contratado se acumula en pocos proveedores. "
                         "Útil para evaluar la competencia en la contratación."]),
            ]),
            html.P([html.B("Nota sobre la medida de valor: "),
                    "las columnas de valor del contrato vienen vacías en la fuente, "
                    "por lo que se usa el saldo del Certificado de Disponibilidad Presupuestal (CDP) "
                    "como aproximación. No es el valor ejecutado."]),
        ]),
    ]),

    filtros,

    # ---------- Pestañas ----------
    dcc.Tabs(id="pestanas", value="tab-ext", className="pestanas", children=[

        # ============ PESTAÑA 1: EXTENSIONES ============
        dcc.Tab(label="Extensiones de plazo", value="tab-ext", className="pestana",
                selected_className="pestana-activa", children=[
            html.Div(className="contenido", children=[

                html.Div(className="tarjetas", children=[
                    tarjeta("Contratos analizados", "kpi-ext-n", "tras aplicar los filtros"),
                    tarjeta("Reciben días adicionales", "kpi-ext-tasa", "proporción del total"),
                    tarjeta("Extensión mediana", "kpi-ext-med", "entre los que se extienden"),
                    tarjeta("Brecha por duración", "kpi-ext-brecha", "más de un año vs. hasta tres meses"),
                ]),

                html.Div(className="fila", children=[
                    html.Div(className="panel", children=[
                        dcc.Graph(id="g-rango", config={"displayModeBar": False}),
                        html.P("La tasa de extensión crece de forma sostenida con la duración pactada. "
                               "Es el patrón más consistente del análisis.", className="lectura"),
                    ]),
                    html.Div(className="panel", children=[
                        dcc.Graph(id="g-hist", config={"displayModeBar": False}),
                        html.P("Los días adicionados se agrupan en múltiplos de mes, no se distribuyen "
                               "de forma continua: las extensiones se otorgan en bloques de calendario.",
                               className="lectura"),
                    ]),
                ]),

                html.Div(className="fila", children=[
                    html.Div(className="panel ancho", children=[
                        dcc.Graph(id="g-heat", config={"displayModeBar": False}),
                        html.P("Comparando contratos del mismo tramo de duración, la diferencia entre "
                               "departamentos se mantiene. La brecha territorial no se explica por los plazos.",
                               className="lectura"),
                    ]),
                ]),
            ]),
        ]),

        # ============ PESTAÑA 2: CONCENTRACIÓN ============
        dcc.Tab(label="Concentración de proveedores", value="tab-con", className="pestana",
                selected_className="pestana-activa", children=[
            html.Div(className="contenido", children=[

                html.Div(className="tarjetas", children=[
                    tarjeta("Proveedores distintos", "kpi-con-n", "con al menos un contrato"),
                    tarjeta("Valor respaldado por CDP", "kpi-con-valor", "suma del periodo filtrado"),
                    tarjeta("Concentración CR10", "kpi-con-cr10", "% del valor en los 10 mayores"),
                    tarjeta("Índice HHI", "kpi-con-hhi", "sobre 10.000; >2.500 es alta"),
                ]),

                html.Div(className="fila", children=[
                    html.Div(className="panel", children=[
                        html.Label("Número de proveedores en la curva", className="etiqueta"),
                        dcc.Slider(id="f-topk", min=5, max=50, step=5, value=20,
                                   marks={k: str(k) for k in range(5, 51, 5)}),
                        dcc.Graph(id="g-pareto", config={"displayModeBar": False}),
                        html.P("La curva acumulada muestra qué tan rápido se concentra el valor. "
                               "Mueva el control para cambiar cuántos proveedores se incluyen.",
                               className="lectura"),
                    ]),
                    html.Div(className="panel", children=[
                        dcc.Graph(id="g-hhi", config={"displayModeBar": False}),
                        html.P("Evolución anual de la concentración. Un HHI creciente indica que el "
                               "valor se acumula en cada vez menos proveedores.", className="lectura"),
                    ]),
                ]),

                html.Div(className="fila", children=[
                    html.Div(className="panel ancho", children=[
                        html.H3("Mayores proveedores del periodo seleccionado"),
                        dash_table.DataTable(
                            id="t-proveedores", page_size=10,
                            style_table={"overflowX": "auto"},
                            style_cell={"fontFamily": "IBM Plex Sans, sans-serif",
                                        "fontSize": 12, "padding": "8px", "textAlign": "left"},
                            style_header={"backgroundColor": PAPEL, "fontWeight": "600",
                                          "border": "none", "borderBottom": f"2px solid {VERDE}"},
                            style_data={"border": "none", "borderBottom": "1px solid #E8E9E5"},
                            style_cell_conditional=[
                                {"if": {"column_id": c}, "textAlign": "right"}
                                for c in ["Contratos", "Valor CDP (COP)", "Participación (%)"]
                            ],
                        ),
                    ]),
                ]),
            ]),
        ]),
    ]),

    html.Div(className="pie", children=[
        html.P("Fuente: SECOP II — Colombia Compra Eficiente. Se excluyen contratos en estado "
               "Borrador y Cancelado, y registros con fechas inconsistentes."),
    ]),
])

# ======================================================================
# 4. FUNCIONES DE APOYO
# ======================================================================
def filtrar_ext(anios, deptos, modalidades):
    d = ext[ext["anio_firma"].between(anios[0], anios[1])]
    if deptos:
        d = d[d["departamento"].isin(deptos)]
    if modalidades:
        d = d[d["modalidad_de_contratacion"].isin(modalidades)]
    return d

def filtrar_con(anios, deptos):
    d = con[con["anio_firma"].between(anios[0], anios[1])]
    if deptos:
        d = d[d["departamento"].isin(deptos)]
    return d

def pesos(v):
    """Formato legible para montos en pesos colombianos."""
    if v >= 1e12: return f"${v/1e12:,.1f} B"
    if v >= 1e9:  return f"${v/1e9:,.1f} MM"
    if v >= 1e6:  return f"${v/1e6:,.1f} M"
    return f"${v:,.0f}"

def vacio(mensaje="Sin datos para los filtros seleccionados"):
    fig = go.Figure()
    fig.add_annotation(text=mensaje, showarrow=False, font=dict(size=14, color=GRIS))
    fig.update_layout(**PLANTILLA, xaxis=dict(visible=False), yaxis=dict(visible=False))
    return fig

# ======================================================================
# 5. CALLBACKS — PESTAÑA DE EXTENSIONES
# ======================================================================
@app.callback(
    [Output("kpi-ext-n", "children"), Output("kpi-ext-tasa", "children"),
     Output("kpi-ext-med", "children"), Output("kpi-ext-brecha", "children")],
    [Input("f-anios", "value"), Input("f-depto", "value"), Input("f-modalidad", "value")],
)
def kpis_extensiones(anios, deptos, modalidades):
    d = filtrar_ext(anios, deptos, modalidades)
    if d.empty:
        return "—", "—", "—", "—"
    tasa = d["tuvo_extension"].mean()
    med = d.loc[d["tuvo_extension"], "dias_adicionados"].median()
    t = d.groupby("rango_duracion", observed=True)["tuvo_extension"].mean()
    brecha = (t.get(">1 año", np.nan) / t.get("≤3 meses", np.nan)
              if t.get("≤3 meses", 0) else np.nan)
    return (f"{len(d):,}", f"{tasa:.1%}",
            f"{med:.0f} días" if pd.notna(med) else "—",
            f"{brecha:.1f}×" if pd.notna(brecha) else "—")


@app.callback(Output("g-rango", "figure"),
              [Input("f-anios", "value"), Input("f-depto", "value"), Input("f-modalidad", "value")])
def grafica_rango(anios, deptos, modalidades):
    d = filtrar_ext(anios, deptos, modalidades)
    if d.empty: return vacio()
    g = (d.groupby("rango_duracion", observed=True)
           .agg(tasa=("tuvo_extension", "mean"), n=("tuvo_extension", "size"))
           .reindex(ORDEN_RANGO).dropna().reset_index())
    fig = px.bar(g, x="rango_duracion", y="tasa", text=g["tasa"].map(lambda v: f"{v:.1%}"))
    fig.update_traces(marker_color=VERDE, textposition="outside",
                      hovertemplate="%{x}<br>Tasa: %{y:.1%}<br>n = %{customdata:,}<extra></extra>",
                      customdata=g["n"])
    fig.update_layout(**PLANTILLA, title="Tasa de extensión según duración pactada",
                      xaxis_title="Rango de duración", yaxis_title="Proporción con extensión",
                      yaxis=dict(tickformat=".0%", gridcolor="#E8E9E5"), xaxis=dict(showgrid=False))
    return fig


@app.callback(Output("g-hist", "figure"),
              [Input("f-anios", "value"), Input("f-depto", "value"), Input("f-modalidad", "value")])
def grafica_hist(anios, deptos, modalidades):
    d = filtrar_ext(anios, deptos, modalidades)
    d = d[d["tuvo_extension"]]
    if d.empty: return vacio("Ningún contrato extendido con estos filtros")
    # xbins explícito: nbins no controla el ancho de forma fiable junto con range_x
    fig = go.Figure(go.Histogram(
        x=d["dias_adicionados"], xbins=dict(start=0, end=140, size=2),
        marker_color=VERDE, marker_line_color="white", marker_line_width=0.4,
        hovertemplate="%{x} días<br>%{y:,} contratos<extra></extra>"))
    for x, etiqueta in {31: "1 mes", 61: "2 meses", 92: "3 meses", 123: "4 meses"}.items():
        fig.add_vline(x=x, line_dash="dot", line_color=GRIS, opacity=0.55,
                      annotation_text=etiqueta, annotation_font_size=10,
                      annotation_font_color=GRIS)
    fig.update_layout(**PLANTILLA, title="Magnitud de la extensión otorgada",
                      xaxis_title="Días adicionados", yaxis_title="Número de contratos",
                      yaxis=dict(gridcolor="#E8E9E5"),
                      xaxis=dict(showgrid=False, range=[0, 140]), bargap=0.04)
    return fig


@app.callback(Output("g-heat", "figure"),
              [Input("f-anios", "value"), Input("f-depto", "value"), Input("f-modalidad", "value")])
def grafica_heat(anios, deptos, modalidades):
    d = filtrar_ext(anios, deptos, modalidades)
    if d.empty: return vacio()
    top = d["departamento"].value_counts().head(12).index
    s = d[d["departamento"].isin(top)]
    piv = s.pivot_table(index="departamento", columns="rango_duracion",
                        values="tuvo_extension", aggfunc="mean", observed=True)
    cnt = s.pivot_table(index="departamento", columns="rango_duracion",
                        values="tuvo_extension", aggfunc="size", observed=True)
    piv = piv.where(cnt >= 30)                       # se ocultan celdas sin muestra suficiente
    piv = piv.reindex(columns=[c for c in ORDEN_RANGO if c in piv.columns])
    piv = piv.loc[piv.mean(axis=1).sort_values().index]
    if piv.dropna(how="all").empty:
        return vacio("Muestra insuficiente para desagregar por departamento")

    fig = px.imshow(piv, text_auto=".2f", color_continuous_scale=ESCALA, aspect="auto")
    fig.update_traces(hovertemplate="%{y}<br>%{x}<br>Tasa: %{z:.1%}<extra></extra>")
    fig.update_layout(**PLANTILLA, height=430,
                      title="Tasa de extensión por departamento y duración "
                            "(celdas con menos de 30 contratos en blanco)",
                      xaxis_title="Rango de duración pactada", yaxis_title="",
                      coloraxis_colorbar=dict(title="Tasa"))
    return fig

# ======================================================================
# 6. CALLBACKS — PESTAÑA DE CONCENTRACIÓN
# ======================================================================
@app.callback(
    [Output("kpi-con-n", "children"), Output("kpi-con-valor", "children"),
     Output("kpi-con-cr10", "children"), Output("kpi-con-hhi", "children")],
    [Input("f-anios", "value"), Input("f-depto", "value")],
)
def kpis_concentracion(anios, deptos):
    d = filtrar_con(anios, deptos)
    if d.empty:
        return "—", "—", "—", "—"
    g = d.groupby("documento_proveedor")["valor_cdp"].sum().sort_values(ascending=False)
    total = g.sum()
    part = g / total * 100
    cr10 = part.head(10).sum()
    hhi = (part ** 2).sum()
    return f"{len(g):,}", pesos(total), f"{cr10:.1f}%", f"{hhi:,.0f}"


@app.callback(Output("g-pareto", "figure"),
              [Input("f-anios", "value"), Input("f-depto", "value"), Input("f-topk", "value")])
def grafica_pareto(anios, deptos, topk):
    d = filtrar_con(anios, deptos)
    if d.empty: return vacio()
    g = (d.groupby("documento_proveedor")
           .agg(proveedor=("proveedor", "first"), valor=("valor_cdp", "sum"))
           .sort_values("valor", ascending=False))
    total = g["valor"].sum()
    g["part"] = g["valor"] / total * 100
    t = g.head(topk).copy()
    t["acum"] = t["part"].cumsum()
    t["etiqueta"] = [f"{i+1}" for i in range(len(t))]

    fig = go.Figure()
    fig.add_bar(x=t["etiqueta"], y=t["part"], marker_color=VERDE, name="Participación",
                customdata=t["proveedor"].str.slice(0, 45),
                hovertemplate="%{customdata}<br>Participación: %{y:.2f}%<extra></extra>")
    fig.add_scatter(x=t["etiqueta"], y=t["acum"], mode="lines+markers", yaxis="y2",
                    line=dict(color=ROJO, width=2), name="Acumulado",
                    hovertemplate="Top %{x}: %{y:.1f}% acumulado<extra></extra>")
    plantilla = {**PLANTILLA, "margin": dict(l=60, r=60, t=88, b=50)}
    fig.update_layout(**plantilla, title=f"Participación de los {topk} mayores proveedores",
                      xaxis_title="Posición del proveedor", yaxis_title="Participación individual (%)",
                      yaxis=dict(gridcolor="#E8E9E5"),
                      yaxis2=dict(title="Acumulado (%)", overlaying="y", side="right",
                                  range=[0, 100], showgrid=False),
                      legend=dict(orientation="h", y=1.14, x=0, yanchor="bottom"),
                      xaxis=dict(showgrid=False))
    return fig


@app.callback(Output("g-hhi", "figure"),
              [Input("f-anios", "value"), Input("f-depto", "value")])
def grafica_hhi(anios, deptos):
    d = filtrar_con(anios, deptos)
    if d.empty: return vacio()
    filas = []
    for anio, sub in d.groupby("anio_firma"):
        g = sub.groupby("documento_proveedor")["valor_cdp"].sum()
        part = g / g.sum() * 100
        filas.append({"anio": int(anio), "hhi": (part ** 2).sum(),
                      "cr10": part.sort_values(ascending=False).head(10).sum(),
                      "n": len(g)})
    h = pd.DataFrame(filas).sort_values("anio")
    if len(h) < 2: return vacio("Se requiere más de un año para ver la evolución")
    # Años con muy pocos proveedores inflan artificialmente el HHI
    h["fiable"] = h["n"] >= 200

    fig = go.Figure()
    fig.add_scatter(x=h["anio"], y=h["hhi"], mode="lines+markers",
                    line=dict(color=VERDE, width=2.5), name="HHI",
                    marker=dict(size=9, color=np.where(h["fiable"], VERDE, "#C9CFC9"),
                                line=dict(width=1.5, color=VERDE)),
                    customdata=h["n"],
                    hovertemplate="%{x}<br>HHI: %{y:,.0f}<br>%{customdata:,} proveedores<extra></extra>")
    if (~h["fiable"]).any():
        fig.add_annotation(xref="paper", yref="paper", x=0, y=1.10, showarrow=False,
                           text="Los puntos claros corresponden a años con menos de 200 "
                                "proveedores: el índice no es comparable.",
                           font=dict(size=10, color=GRIS), align="left")
    # El umbral de alta concentración (2.500) solo se dibuja si la serie se le acerca;
    # de lo contrario aplastaría la escala y ocultaría la variación real.
    if h["hhi"].max() > 800:
        fig.add_hline(y=2500, line_dash="dash", line_color=ROJO,
                      annotation_text="Umbral de alta concentración",
                      annotation_font_size=10, annotation_font_color=ROJO)
    else:
        fig.add_annotation(xref="paper", yref="paper", x=0.99, y=0.97, showarrow=False,
                           text="Referencia: un HHI sobre 2.500 indica alta concentración",
                           font=dict(size=10, color=GRIS), align="right")
    fig.update_layout(**PLANTILLA, title="Evolución anual del índice HHI",
                      xaxis_title="Año de firma", yaxis_title="HHI (sobre 10.000)",
                      yaxis=dict(gridcolor="#E8E9E5"), xaxis=dict(showgrid=False, dtick=1))
    return fig


@app.callback(Output("t-proveedores", "data"), Output("t-proveedores", "columns"),
              [Input("f-anios", "value"), Input("f-depto", "value")])
def tabla_proveedores(anios, deptos):
    d = filtrar_con(anios, deptos)
    if d.empty:
        return [], []
    g = (d.groupby("documento_proveedor")
           .agg(Proveedor=("proveedor", "first"),
                Contratos=("n_contratos", "sum"),
                valor=("valor_cdp", "sum"))
           .sort_values("valor", ascending=False).head(25).reset_index(drop=True))
    total = d["valor_cdp"].sum()
    g["Participación (%)"] = (g["valor"] / total * 100).round(2)
    g["Valor CDP (COP)"] = g["valor"].map(lambda v: f"{v:,.0f}")
    g = g[["Proveedor", "Contratos", "Valor CDP (COP)", "Participación (%)"]]
    return g.to_dict("records"), [{"name": c, "id": c} for c in g.columns]

# ======================================================================
# 7. ESTILOS
# ======================================================================
app.index_string = """<!DOCTYPE html>
<html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@600&display=swap" rel="stylesheet">
<style>
 body{margin:0;background:#F2F2EE;font-family:'IBM Plex Sans',Segoe UI,sans-serif;color:#16261F}
 .pagina{max-width:1320px;margin:0 auto;padding:22px 26px 50px}
 .encabezado h1{font-family:'IBM Plex Serif',Georgia,serif;font-size:29px;margin:0 0 4px;letter-spacing:-.015em}
 .encabezado p{margin:0 0 16px;color:#6E7A72;font-size:13.5px}
 .instrucciones{background:#fff;border-left:3px solid #2F7A3E;padding:12px 16px;margin-bottom:16px;font-size:13.5px;line-height:1.55}
 .instrucciones summary{cursor:pointer;font-weight:600;color:#2F7A3E}
 .instrucciones p{margin:10px 0}
 .instrucciones ul{margin:8px 0;padding-left:20px}
 .instrucciones li{margin-bottom:6px}
 .filtros{display:grid;grid-template-columns:1.6fr 1fr 1fr;gap:20px;background:#fff;padding:16px 20px 20px;margin-bottom:16px;border:1px solid #E2E3DE}
 .etiqueta{display:block;font-size:12px;font-weight:600;color:#6E7A72;margin-bottom:7px}
 .pestanas{margin-bottom:0}
 .pestana{background:#E8E9E4!important;border:none!important;font-size:14px!important;padding:11px!important;color:#6E7A72!important}
 .pestana-activa{background:#fff!important;border-top:3px solid #2F7A3E!important;font-weight:600!important;color:#16261F!important}
 .contenido{background:#fff;padding:20px;border:1px solid #E2E3DE;border-top:none}
 .tarjetas{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:22px}
 .tarjeta{border-left:3px solid #2F7A3E;padding:4px 0 4px 13px;display:flex;flex-direction:column;gap:3px}
 .tarjeta-titulo{font-size:11.5px;color:#6E7A72;font-weight:500}
 .tarjeta-valor{font-family:'IBM Plex Serif',Georgia,serif;font-size:29px;font-weight:600;color:#2F7A3E;line-height:1.1}
 .tarjeta-ayuda{font-size:11px;color:#98A19C}
 .fila{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
 .panel.ancho{grid-column:1/-1}
 .fila:has(.ancho){grid-template-columns:1fr}
 .panel h3{font-family:'IBM Plex Serif',Georgia,serif;font-size:16px;margin:0 0 12px}
 .lectura{font-size:12.5px;color:#6E7A72;line-height:1.5;margin:4px 0 0;padding-left:11px;border-left:2px solid #E2E3DE}
 .pie{margin-top:18px;font-size:11.5px;color:#98A19C}
 @media(max-width:900px){.filtros,.tarjetas,.fila{grid-template-columns:1fr}}
</style>
</head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

# ======================================================================
# 8. EJECUCIÓN
# ======================================================================
if __name__ == "__main__":
    # Local: http://127.0.0.1:8050/
    # En EC2 cambie por:  app.run(host="0.0.0.0", debug=True)
    app.run(debug=True)
