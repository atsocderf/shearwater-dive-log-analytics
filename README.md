# Shearwater Dive Log Analytics

A local Flask web application for analyzing dive logs stored in a SQLite database.

The application reads raw dive-computer data, decodes and normalizes the information from multiple computers, associates synchronized measurements, and presents the result in a simple browser interface.

The project is designed around local/offline processing: the SQLite database remains on the user's computer and is **not included in this repository**. 

## Features

- Local Flask web interface
- SQLite input database
- Consolidation of dive logs from multiple dive computers
- Computer identification by model and serial number
- Per-computer synchronized data
- PPO₂
- TTS (Time To Surface)
- Ceiling / decompression stop
- GF99
- CNS
- O₂ cell readings in mV
- Tank pressure / wireless transmitter data
- Transmitter association by computer and transmitter serial number
- Metric / Imperial display
- Median average depth
- Median dive duration
- Deco-dive filtering
- Computer selection for analysis
- Sortable dive list
- GPS location information and map links when available

## Architecture

The application is intentionally small and uses a straightforward Python/Flask architecture.

```text
                    ┌─────────────────────┐
                    │   SQLite database   │
                    │     dive_data.db    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      decoder.py     │
                    │                     │
                    │ SQLite access       │
                    │ PNF/raw data decode │
                    │ computer metadata   │
                    │ transmitter data    │
                    │ O₂ cell data        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │      matcher.py     │
                    │                     │
                    │ Multi-computer      │
                    │ dive association    │
                    │ synchronized        │
                    │ timeline generation │
                    │ transmitter mapping │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┴─────────────┐
                 ▼                           ▼
        ┌─────────────────┐         ┌─────────────────┐
        │     app.py      │         │     geo.py      │
        │                 │         │                 │
        │ Flask routes    │         │ GPS/location    │
        │ filters         │         │ handling        │
        │ unit selection  │         └─────────────────┘
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────────────────┐
        │          Templates          │
        │                             │
        │ templates/index.html        │
        │ templates/dive.html         │
        │ static/style.css            │
        └─────────────────────────────┘
```

### File overview

| File | Purpose |
|---|---|
| `app.py` | Flask application, routes, filters and web presentation logic |
| `decoder.py` | Reads SQLite data and decodes computer/log information |
| `matcher.py` | Consolidates logs from multiple computers and builds synchronized dive timelines |
| `geo.py` | Handles GPS/location information |
| `templates/index.html` | Main dive list and filters |
| `templates/dive.html` | Detailed synchronized dive view |
| `static/style.css` | Application styling |
| `requirements.txt` | Python dependencies |
| `verify_d0009.py` | Diagnostic/verification utility |
| `verify_o2_cells.py` | O₂-cell verification utility |

## Multi-computer architecture

A central design principle is that a physical dive computer is identified by its **serial number**, not only by its model.

For example, the database may contain multiple Petrel units. They can therefore be kept as independent sources even when they share the same model.

The application first decodes each computer's log independently and then builds a unified dive representation.

Conceptually:

```text
Computer A ─┐
            │
Computer B ─┼──► dive matching / synchronization ──► unified dive timeline
            │
Computer C ─┘
```

Measurements are not blindly merged. Values remain associated with the computer that actually recorded them.

This is particularly important for:

- PPO₂
- TTS
- ceiling/decompression information
- GF99
- CNS
- O₂ cells
- wireless transmitter pressure

If a computer does not have a particular measurement capability, or if the transmitter was temporarily disconnected, the corresponding value remains unavailable rather than being copied from another computer.

## Transmitter handling

Wireless transmitters are associated using their recorded identity and the computer to which they belong.

The application can therefore represent situations such as:

```text
Nerd 2
 ├── B1
 ├── B2
 └── O2

Petrel
 └── no transmitter data
```

The transmitter serial number is used internally for reliable identification, while the user interface displays the transmitter name.

A transmitter may legitimately have missing samples during a dive if communication was temporarily lost.

## Units

The interface supports:

- **Metric** — depth in meters and pressure in bar
- **Imperial** — depth in feet and pressure in PSI

Pressure is kept internally in its source representation and converted for presentation, avoiding cumulative conversion errors when the user switches units.

## Installation

### Requirements

- Python 3.11+ recommended
- SQLite 3
- A modern web browser
- macOS, Linux or Windows

Python 3.14 has been used during development, but the project does not require Python-specific functionality beyond the standard Flask/runtime dependencies.

### 1. Clone the repository

```bash
git clone https://github.com/atsocderf/shearwater-dive-log-analytics.git
cd shearwater-dive-log-analytics
```

### 2. Create a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your local SQLite database

The application expects the SQLite database at:

```text
dive_data.db
```

Copy your local database into the project directory:

```text
project/
├── app.py
├── decoder.py
├── matcher.py
├── geo.py
├── requirements.txt
├── dive_data.db       ← local file, NOT committed to Git
├── templates/
└── static/
```

The database is intentionally excluded from Git because it contains personal dive data and can be large.

### 5. Start the application

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Database requirements

The application expects the SQLite database to contain the tables/fields used by the decoder, including the dive detail and log data structures produced by the source dive-log software.

The exact schema is intentionally handled by `decoder.py`; the application does not migrate or modify the user's source database.

The database is treated as **read-only input** by the application.

You'll need to copy the sqlite database from Shearwater Cloud Applicatiion -> File -> Open Dive Log Directory -> dive_data.db to the same directory as app.py.


## Privacy

Dive logs can contain personally sensitive information, including:

- dive dates and times
- GPS coordinates
- dive locations
- equipment serial numbers
- physiological/decompression data

For this reason, the production database is deliberately excluded from the Git repository.

If you distribute sample data for development, use an anonymized database with GPS coordinates and equipment identifiers removed or replaced.


## Project status

This is a local analytical tool intended primarily for personal CCR dive-log analysis.

The application does not write back to the source SQLite database and does not replace the manufacturer's dive-computer software or decompression planning tools.

All decompression-related values shown by the application should be treated as recorded/logged data from the source computer rather than as independent decompression calculations.

## License

```text
MIT License
```
