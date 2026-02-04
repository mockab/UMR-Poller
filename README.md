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
