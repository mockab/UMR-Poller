# UMR-Poller LTE Dashboard

A real-time, interactive signal monitoring dashboard designed for Raspberry Pi. This tool tracks LTE RF metrics (RSSI, RSRP, RSRQ), network stability, and latency spikes using a Dash-based web interface.



## Features

* **Real-time Monitoring:** Live-updating graphs for RF metrics and latency.
* **Health Cards:** Visual indicators (Excellent, Good, Weak, Poor) for signal quality.
* **Timeframe Selectors:** Toggle between 1H, 1D, 1W, 1M, and All Time history.
* **Automated Insights:** * **Uptime Tracker:** Calculates availability based on LTE state.
    * **Band Change Markers:** Visual dotted lines and labels on graphs when the modem switches bands.
    * **Latency Spikes:** Top 5 "Hall of Fame" table for the worst recorded latency events.
* **Site Agnostic:** Automatically detects site names (e.g., Athol, Applewood) from CSV headers.
* **Timezone Aware:** Automatically converts UTC logs to EST (Eastern Standard Time).

## Installation

### Prerequisites
Ensure your system is running the collector from [UMR-Poller](https://github.com/skutov/UMR-Poller) and generating an `output.csv`.
Install requirements.txt

## Prometheus metrics

`UMR-poller.py` can expose the same signal/latency data read by the dashboard as a Prometheus `/metrics` endpoint, so a remote Grafana can scrape it directly instead of (or alongside) the CSV/Dash UI.

Enable it in `config.yml`:

```yaml
global:
  metricsEnable: True
  metricsPort: 9101 # default
```

or via CLI flags: `--metricsEnable --metricsPort 9101`.

Metrics (all labelled `router="<name>"` matching the `name` in `config.yml`):

| Metric | Meaning |
|---|---|
| `umr_router_up` | 1 if the last poll succeeded (`authState > 0`), else 0 |
| `umr_last_poll_timestamp_seconds` | Unix time of the last successful poll |
| `umr_signal_level` | Signal level |
| `umr_rssi_dbm` / `umr_rsrq_db` / `umr_rsrp_dbm` | RF signal quality |
| `umr_latency_max_ms` / `umr_latency_packet_loss_count` | Latency check results |
| `umr_rx_channel` / `umr_tx_channel` | EARFCN |
| `umr_lte_state_info{state="..."}` | Current LTE state, 1 on the active value |
| `umr_band_info{band="..."}` | Currently active band(s), 1 on the active value (supports carrier-aggregation strings) |
| `umr_download_usage_bytes_total` / `umr_upload_usage_bytes_total` / `umr_total_usage_bytes_total` | Cumulative bytes reported by the router. The device never auto-resets these (`reset_usage_timestamp` stays 0), so get "data used this month" via `increase(umr_total_usage_bytes_total[$__range])` with the Grafana time range set to "This month" rather than reading the raw value |
| `umr_usage_reset_timestamp_seconds` | Unix timestamp the router last reset its usage counters (0 = never) |
| `umr_client_count` / `umr_wifi_client_count` | Connected client counts |
| `umr_cpu_percent` / `umr_memory_percent` | Router CPU/memory utilisation |
