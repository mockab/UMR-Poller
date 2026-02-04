import dash
from dash import dcc, html, Input, Output, dash_table
import pandas as pd
import plotly.graph_objs as go
import numpy as np
from datetime import datetime, timedelta
import pytz

app = dash.Dash(__name__)

# Reference Table Data
threshold_data = [
    {"Metric": "RSSI", "Excellent": "> -60", "Good": "-70", "Weak": "-80", "Poor": "< -80"},
    {"Metric": "RSRP", "Excellent": "> -80", "Good": "-90", "Weak": "-100", "Poor": "< -100"},
    {"Metric": "RSRQ", "Excellent": "> -5", "Good": "-10", "Weak": "-15", "Poor": "< -15"},
]

def get_metric_health(val, metric):
    if pd.isna(val): return "N/A", "#7f8c8d"
    thresholds = {
        'rsrp': [(-80, "Excellent", "#2ecc71"), (-90, "Good", "#27ae60"), (-100, "Weak", "#f1c40f")],
        'rssi': [(-60, "Excellent", "#2ecc71"), (-70, "Good", "#27ae60"), (-80, "Weak", "#f1c40f")],
        'rsrq': [(-5, "Excellent", "#2ecc71"), (-10, "Good", "#27ae60"), (-15, "Weak", "#f1c40f")]
    }
    for limit, label, color in thresholds[metric]:
        if val > limit: return label, color
    return "Poor", "#e74c3c"

app.layout = html.Div([
    html.H1(id='dynamic-title', style={'textAlign': 'center', 'color': 'white'}),

    # Time Filter Switch
    html.Div([
        dcc.RadioItems(
            id='time-filter',
            options=[
                {'label': '1 Hour', 'value': '1H'},
                {'label': '1 Day', 'value': '1D'},
                {'label': '1 Week', 'value': '1W'},
                {'label': '1 Month', 'value': '1M'},
                {'label': 'All Time', 'value': 'ALL'}
            ],
            value='ALL', inline=True, style={'color': 'white', 'fontSize': '18px'}
        )
    ], style={'textAlign': 'center', 'marginBottom': '20px'}),

    # Summary Stats Row
    html.Div([
        html.Div(id='uptime-stat', style={'flex': '1', 'backgroundColor': '#34495e', 'color': 'white', 'padding': '10px', 'margin': '5px', 'borderRadius': '10px', 'textAlign': 'center'}),
        html.Div(id='band-stat', style={'flex': '1', 'backgroundColor': '#34495e', 'color': 'white', 'padding': '10px', 'margin': '5px', 'borderRadius': '10px', 'textAlign': 'center'}),
    ], style={'display': 'flex', 'marginBottom': '10px'}),

    # Health Cards and Reference Table
    html.Div([
        html.Div([
            html.Div(id='rssi-card', style={'margin': '5px', 'flex': '1'}),
            html.Div(id='rsrp-card', style={'margin': '5px', 'flex': '1'}),
            html.Div(id='rsrq-card', style={'margin': '5px', 'flex': '1'}),
        ], style={'flex': '1', 'display': 'flex', 'flexDirection': 'column'}),
        
        html.Div([
            dash_table.DataTable(
                data=threshold_data,
                columns=[{"name": i, "id": i} for i in threshold_data[0].keys()],
                style_as_list_view=True,
                style_header={'backgroundColor': '#1a1a1a', 'color': 'white', 'fontWeight': 'bold'},
                style_cell={'backgroundColor': '#2c3e50', 'color': 'white', 'textAlign': 'center', 'fontSize': '13px'},
            )
        ], style={'flex': '1.5', 'margin': '5px', 'backgroundColor': '#2c3e50', 'padding': '15px', 'borderRadius': '10px'})
    ], style={'display': 'flex', 'flexWrap': 'wrap'}),

    dcc.Graph(id='rf-metrics-graph'),
    dcc.Graph(id='quality-graph'),

    # High Latency Table
    html.Div([
        html.H4("Top 5 Latency Spikes (Current View)", style={'color': 'white', 'textAlign': 'center'}),
        dash_table.DataTable(id='latency-table', style_header={'backgroundColor': '#1a1a1a', 'color': 'white'}, style_cell={'backgroundColor': '#2c3e50', 'color': 'white'})
    ], style={'padding': '20px'}),
    
    dcc.Interval(id='interval-component', interval=2000, n_intervals=0)
], style={'backgroundColor': '#111111', 'minHeight': '100vh', 'padding': '20px'})

@app.callback(
    [Output('dynamic-title', 'children'),
     Output('uptime-stat', 'children'),
     Output('band-stat', 'children'),
     Output('rssi-card', 'children'), Output('rssi-card', 'style'),
     Output('rsrp-card', 'children'), Output('rsrp-card', 'style'),
     Output('rsrq-card', 'children'), Output('rsrq-card', 'style'),
     Output('rf-metrics-graph', 'figure'),
     Output('quality-graph', 'figure'),
     Output('latency-table', 'data')],
    [Input('interval-component', 'n_intervals'),
     Input('time-filter', 'value')]
)
def update_dashboard(n, time_range):
    try:
        df = pd.read_csv('output.csv').replace('n/a', np.nan)
        df['time'] = pd.to_datetime(df['Systemdate']).dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.tz_localize(None)
        
        sample_col = [c for c in df.columns if ".InfoHighDump" in c]
        site_name = sample_col[0].split('.')[0].upper() if sample_col else "LTE"

        # Filter Logic
        now = df['time'].max()
        if time_range == '1H':
            df = df[df['time'] > now - timedelta(hours=1)]
        elif time_range == '1D':
            df = df[df['time'] > now - timedelta(days=1)]

        if df.empty:
            return [f"{site_name} MONITOR (No Data)"] + [dash.no_update] * 11

        # Uptime & Stats
        state_col = next((c for c in df.columns if 'lte_state' in c.lower()), None)
        uptime_pct = (pd.to_numeric(df[state_col], errors='coerce') == 4).mean() * 100 if state_col else 0
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # Metric Processing
        results = {}
        for key in ['rssi', 'rsrp', 'rsrq']:
            col = next((c for c in df.columns if key in c.lower()), None)
            cv = pd.to_numeric(latest[col], errors='coerce') if col else np.nan
            pv = pd.to_numeric(prev[col], errors='coerce') if col else np.nan
            trend = " ↑" if cv > pv else (" ↓" if cv < pv else " ↔")
            label, color = get_metric_health(cv, key)
            results[key] = {
                'content': [html.H4(f"{key.upper()}: {cv}{trend}", style={'margin': '0'})],
                'style': {'backgroundColor': color, 'color': 'white', 'padding': '10px', 'borderRadius': '10px', 'textAlign': 'center', 'marginBottom': '5px'}
            }

        # Band Change Annotations
        band_col = next((c for c in df.columns if 'band' in c.lower()), None)
        band_changes = df[df[band_col] != df[band_col].shift()].dropna(subset=[band_col])
        
        shapes = []
        annotations = []
        for _, row in band_changes.iterrows():
            shapes.append(dict(type="line", x0=row['time'], x1=row['time'], y0=0, y1=1, yref="paper", line=dict(color="rgba(255,255,255,0.2)", width=1, dash="dot")))
            annotations.append(dict(x=row['time'], y=1, yref="paper", text=f" {row[band_col]}", showarrow=False, font=dict(color="white", size=10), textangle=-90, xanchor="left"))

        # Graphs
        rf_fig = go.Figure()
        for key, name, c in [('rsrp', 'RSRP', '#3498db'), ('rsrq', 'RSRQ', '#9b59b6'), ('rssi', 'RSSI', '#1abc9c')]:
            col = next((cn for cn in df.columns if key in cn.lower()), None)
            if col: rf_fig.add_trace(go.Scatter(x=df['time'], y=pd.to_numeric(df[col], errors='coerce'), name=name))
        rf_fig.update_layout(title="Signal History", template="plotly_dark", height=350, uirevision='constant', shapes=shapes, annotations=annotations)

        lat_col = next((c for c in df.columns if 'latency_max_ms' in c.lower()), None)
        qual_fig = go.Figure()
        if lat_col: qual_fig.add_trace(go.Scatter(x=df['time'], y=pd.to_numeric(df[lat_col], errors='coerce'), name="Latency", line=dict(color='#e67e22')))
        qual_fig.update_layout(title="Latency History", template="plotly_dark", height=350, uirevision='constant', shapes=shapes, annotations=annotations)

        top_latency = df.nlargest(5, lat_col)[['time', band_col, lat_col]].to_dict('records') if lat_col else []

        return (f"{site_name} LTE MONITORING", f"Uptime in View: {uptime_pct:.2f}%", f"Current Band: {latest[band_col]}",
                results['rssi']['content'], results['rssi']['style'],
                results['rsrp']['content'], results['rsrp']['style'],
                results['rsrq']['content'], results['rsrq']['style'],
                rf_fig, qual_fig, top_latency)

    except Exception as e:
        return [f"ERROR: {str(e)}"] + [dash.no_update] * 11

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=False)
