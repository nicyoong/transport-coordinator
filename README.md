# Transport Planner

A Python transport coordination tool for proposing car assignments and route plans.

The system helps decide:

- which passengers should ride with which drivers
- who cannot be paired together
- who must travel together
- which drivers are unavailable
- which passengers may be left outside if there is not enough valid car space
- pickup routes from driver homes to passenger homes to the destination
- drop-off routes from the final destination to passenger homes to the driver home

This is designed to generate a **proposed arrangement**, not a final compulsory plan.

---

## Trip Types

The planner supports two trip types.

### 1. Single-place trip

Use this when everyone goes to one place, then returns home.

```text
Driver home → passenger homes → place → passenger homes → driver home
````

Example:

```text
Olivia home → Charlotte home → Amelia home → Beta KL → Amelia home → Charlotte home → Olivia home
```

### 2. Multiple-place trip

Use this when everyone goes to more than one place before going home.

```text
Driver home → passenger homes → place 1 → place 2 → ... → passenger homes → driver home
```

Example:

```text
Olivia home → Charlotte home → Amelia home → Beta KL → Yun House → Tatsu Japanese Cuisine → Amelia home → Charlotte home → Olivia home
```

---

## Project Structure

```text
transport_planner/
├── main.py
├── transport_planner.py
├── google_routes_client.py
├── people.csv
├── places.csv
├── rules.yml
├── config.yml
├── .env
├── requirements.txt
└── tests/
    ├── __init__.py
    └── test_transport_planner.py
```

---

## Installation

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install pandas pyyaml requests ortools pytest python-dotenv
```

Or create a `requirements.txt`:

```text
pandas
pyyaml
requests
ortools
pytest
python-dotenv
```

Then install:

```bash
pip install -r requirements.txt
```

---

## Environment Variables

The Google Maps API key should be stored in `.env`, not in `config.yml`.

Create a `.env` file:

```env
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
```

Add `.env` to `.gitignore`:

```gitignore
.env
```

---

## Input Files

### `people.csv`

This file contains all drivers and passengers.

```csv
name,gender,home_address,can_drive,car_capacity
Olivia,F,"Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur",true,4
Emma,F,"Yun House, Four Seasons Hotel Kuala Lumpur, 145 Jalan Ampang, 50450 Kuala Lumpur",true,4
Sophia,F,"Shang Palace, Shangri-La Kuala Lumpur, 11 Jalan Sultan Ismail, 50250 Kuala Lumpur",true,3
Charlotte,F,"FLOCK, W Kuala Lumpur, 121 Jalan Ampang, 50450 Kuala Lumpur",false,0
Amelia,F,"Curate, Four Seasons Hotel Kuala Lumpur, 145 Jalan Ampang, 50450 Kuala Lumpur",false,0
```

Fields:

| Field          | Meaning                                    |
| -------------- | ------------------------------------------ |
| `name`         | Person's name                              |
| `gender`       | Used for same-gender grouping rules        |
| `home_address` | Pickup/drop-off address                    |
| `can_drive`    | `true` for drivers, `false` for passengers |
| `car_capacity` | Number of passengers the driver can take   |

Important:

* Car capacity means passenger seats only.
* A driver with `car_capacity: 4` can take up to 4 passengers.
* Passengers should have `can_drive: false` and `car_capacity: 0`.

---

### `places.csv`

This file contains possible destination places.

```csv
name,address
Beta KL,"Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur"
Yun House,"Yun House, Four Seasons Hotel Kuala Lumpur, 145 Jalan Ampang, 50450 Kuala Lumpur"
FLOCK W Kuala Lumpur,"FLOCK, W Kuala Lumpur, 121 Jalan Ampang, 50450 Kuala Lumpur"
Tatsu Japanese Cuisine,"Tatsu Japanese Cuisine, InterContinental Kuala Lumpur, 165 Jalan Ampang, 50450 Kuala Lumpur"
Village Park Restaurant,"Village Park Restaurant, 5 Jalan SS 21/37, Damansara Utama, 47400 Petaling Jaya"
Strangers at 47,"Strangers at 47, 45 Jalan 17/45, Seksyen 17, 46400 Petaling Jaya"
```

Fields:

| Field     | Meaning                                |
| --------- | -------------------------------------- |
| `name`    | Short name used in `config.yml`        |
| `address` | Full address sent to Google Routes API |

---

### `rules.yml`

This file stores pairing rules and exceptions.

```yaml
same_gender_only: true

must_together:
  - [Charlotte, Amelia]
  - [Oliver, James]
  - [Benjamin, Lucas]

cannot_pair:
  - [Mia, Evelyn]
  - [William, Henry]
  - [Noah, Alexander]
  - [Emma, Harper]

preferred_driver:
  Charlotte: Olivia
  Amelia: Olivia
  Isabella: Emma
  Oliver: Noah
  James: Noah
  Benjamin: Liam
  Lucas: Liam

unavailable_drivers: []
```

Rule types:

| Rule                  | Meaning                                                                    |
| --------------------- | -------------------------------------------------------------------------- |
| `same_gender_only`    | If true, passengers are matched only with drivers of the same gender       |
| `must_together`       | These passengers must be assigned to the same car or left outside together |
| `cannot_pair`         | These people cannot be in the same car                                     |
| `preferred_driver`    | Soft preference; reduces cost if matched                                   |
| `unavailable_drivers` | Drivers excluded from the reroll                                           |

To reroll after a driver becomes unavailable:

```yaml
unavailable_drivers:
  - Olivia
```

Then run the planner again.

---

### `config.yml`

For a single-place trip:

```yaml
trip:
  type: "single_place"
  places:
    - "Beta KL"

settings:
  max_passengers_per_car: 4
  outside_penalty_minutes: 10000
  preferred_driver_bonus_minutes: 20
  routes_usage_database: "routes_usage.sqlite3"
  routes_matrix_element_limit_30_days: 10000
  output_json_path: "transport_plan_{duty}.json"
  output_csv_path: "transport_plan_{duty}.csv"
```

For a multiple-place trip:

```yaml
trip:
  type: "multiple_places"
  places:
    - "Beta KL"
    - "Yun House"
    - "Tatsu Japanese Cuisine"

settings:
  max_passengers_per_car: 4
  outside_penalty_minutes: 10000
  preferred_driver_bonus_minutes: 20
  routes_usage_database: "routes_usage.sqlite3"
  routes_matrix_element_limit_30_days: 10000
  output_json_path: "transport_plan_{duty}.json"
  output_csv_path: "transport_plan_{duty}.csv"
```

Settings:

| Setting                          | Meaning                                     |
| -------------------------------- | ------------------------------------------- |
| `max_passengers_per_car`         | Hard maximum passenger seats per car        |
| `outside_penalty_minutes`        | Penalty for leaving a passenger outside     |
| `preferred_driver_bonus_minutes` | Bonus applied when preferred driver is used |
| `routes_usage_database`          | Local SQLite API usage ledger               |
| `routes_matrix_element_limit_30_days` | Maximum matrix elements allowed in any rolling 30-day window |
| `output_json_path`               | Raw JSON path; `{duty}` becomes the selected duty |
| `output_csv_path`                | Driver/passenger CSV path; `{duty}` becomes the selected duty |

A high outside penalty makes the system try hard to assign everyone.

---

## Running the Planner

Run one duty:

```bash
python main.py pickup
python main.py dropoff
```

To optimize both duties together:

```bash
python main.py both
```

Running `python main.py` without an argument also defaults to `both`.

Show command help with any of:

```bash
python main.py help
python main.py --help
python main.py -h
```

Pickup and drop-off modes optimize driver assignments using only the selected
duty's travel time and print only that route. Both mode uses the combined
travel time. The terminal report shows only each car, driver, passenger order,
total estimated driving time, unused drivers, unassigned passengers, and
notes. Addresses and API usage remain in the raw JSON.

The complete raw result is written to `transport_plan_pickup.json`,
`transport_plan_dropoff.json`, or `transport_plan_both.json`. Separate files
prevent one duty's result from overwriting another.

A spreadsheet-friendly CSV is also written for each duty:
`transport_plan_pickup.csv`, `transport_plan_dropoff.csv`, or
`transport_plan_both.csv`. Cell A1 contains `Driver`; driver names occupy B1
onward, and their passengers are listed downward in optimized duty order.
Unused drivers retain an empty column. Combined mode uses pickup order because
a single CSV column can represent only one passenger sequence.

### Routes API usage guard

Every planned Compute Route Matrix request is recorded in the local SQLite
database before it is sent. Billing is based on matrix elements, calculated as
origins multiplied by destinations, so the rolling limit is enforced on
elements rather than HTTP requests. If a complete calculation would exceed the
limit, no request from that calculation is sent.

Usage is stored and limited separately by the API key's last six characters.
The complete API key is never written to the database. Changing the key starts
a separate rolling usage allowance.

The planner output includes `routes_api_usage_30_days`. You can also inspect
usage without calling Google:

```bash
python routes_usage.py
```

This defaults to the current `GOOGLE_MAPS_API_KEY` in `.env`. To inspect a
specific stored key suffix:

```bash
python routes_usage.py --api-key-last6 abc123
```

Show database command help with:

```bash
python routes_usage.py help
python routes_usage.py --help
python routes_usage.py -h
```

Failed API attempts remain counted conservatively because they may have reached
Google. The database and its journal files are excluded from Git. Keep a Google
Cloud quota configured as a second, server-side safeguard.

### Geocoding fixed test locations

Enable the **Geocoding API** in the same Google Cloud project used for the
Routes API. The existing `GOOGLE_MAPS_API_KEY` can be used if its API
restrictions allow both APIs.

Generate coordinates and Place IDs for the unique addresses in `people.csv`
and `places.csv`:

```bash
python geocode_locations.py
```

This writes `locations.csv`. Existing complete rows are reused, so subsequent
runs only request new or incomplete addresses. To geocode every address again:

```bash
python geocode_locations.py --refresh
```

Review rows where `partial_match` is `True` or where `location_type` is less
precise than expected. The API key is read from `.env` and is never written to
the output.

Example output:

```json
{
  "trip_type": "single_place",
  "summary": {
    "total_people": 20,
    "total_drivers_available": 6,
    "total_passengers": 14,
    "total_passengers_assigned": 14,
    "total_passengers_outside": 0
  },
  "places": [
    {
      "name": "Beta KL",
      "address": "Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur"
    }
  ],
  "cars": [
    {
      "driver": "Olivia",
      "passengers": ["Charlotte", "Amelia"],
      "pickup_path": {
        "description": "Driver home to passenger homes to place",
        "route": [
          "Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur",
          "FLOCK, W Kuala Lumpur, 121 Jalan Ampang, 50450 Kuala Lumpur",
          "Curate, Four Seasons Hotel Kuala Lumpur, 145 Jalan Ampang, 50450 Kuala Lumpur",
          "Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur"
        ],
        "estimated_duration_min": 22
      },
      "dropoff_path": {
        "description": "Place to passenger homes to driver home",
        "route": [
          "Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur",
          "Curate, Four Seasons Hotel Kuala Lumpur, 145 Jalan Ampang, 50450 Kuala Lumpur",
          "FLOCK, W Kuala Lumpur, 121 Jalan Ampang, 50450 Kuala Lumpur",
          "Beta KL, Cormar Suites, No. 10, Jalan Perak, 50450 Kuala Lumpur"
        ],
        "estimated_duration_min": 24
      },
      "total_estimated_duration_min": 46
    }
  ],
  "outside_due_to_no_space": [],
  "warnings": [
    "This is only a proposed arrangement.",
    "Pickup route is optimized separately from drop-off route.",
    "Passengers may be outside if there is insufficient valid car space."
  ]
}
```

---

## Running Tests

The test suite does not need a Google API key.

It uses a fake duration matrix so that the planner logic can be tested before using real routing data.

Run:

```bash
pytest
```

For detailed output:

```bash
pytest -v
```

The tests cover:

* route duration calculation
* best pickup/drop-off ordering
* single-place trips
* multiple-place trips
* same-gender rule
* must-together rule
* cannot-pair rule
* unavailable drivers
* outside passengers when there is not enough space
* invalid trip type handling

---

## How the Routing Works

The system separates the problem into two parts.

### 1. Routing data

`google_routes_client.py` asks Google Routes API for travel duration between every pair of addresses.

This creates a duration matrix:

```python
duration_matrix[(origin_address, destination_address)] = seconds
```

Example:

```python
duration_matrix[
    ("Olivia home", "Charlotte home")
] = 600
```

### 2. Assignment optimization

`transport_planner.py` uses the duration matrix to decide:

* which passengers fit each driver
* which groups are valid under the rules
* which pickup order is fastest
* which drop-off order is fastest
* which complete set of cars gives the best proposal

---

## Greedy vs OR-Tools

The project can use two optimizer styles.

### Greedy

Greedy chooses the best-looking car option first, then repeats.

It is:

* simple
* fast
* easy to debug

But it can miss the best overall arrangement.

### OR-Tools

OR-Tools considers all valid car options together and chooses the best full arrangement.

It is better when there are:

* many rules
* must-together groups
* cannot-pair rules
* unavailable drivers
* limited seats
* passengers who may be left outside

Recommended mode:

```text
Use OR-Tools for final planning.
Use greedy only for quick testing or fallback.
```

---

## Important Notes

This tool generates a proposed transport plan only.

Before using the final arrangement:

* confirm drivers are actually available
* confirm car capacities
* confirm passengers are comfortable with the proposed pairings
* confirm destination order
* check live traffic if timing matters
* manually review anyone placed outside

---

## Future Improvements

Possible next steps:

* export results to CSV
* export results to Google Sheets
* generate WhatsApp-friendly messages
* add real geocoding for partial addresses
* add route links to Google Maps
* allow pickup-only or drop-off-only trips
* add time windows
* add driver preference weights
* add passenger priority levels
* add “must be in same car as driver” rules
* add “avoid tolls” or “avoid highways” settings

