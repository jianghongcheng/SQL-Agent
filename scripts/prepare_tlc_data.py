"""Import an official TLC month; independently derive checks from Parquet rows.

Requires the optional data extra. Downloads public data, never runs remote code.
All raw rows are retained; anomalous records are measured, not silently removed.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request

TRIPS = 'https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2025-01.parquet'
ZONES = 'https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv'


def main():
    import pyarrow.parquet as pq
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/local/tlc_2025_01'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    downloads = []
    for url, name in [(TRIPS, 'trips.parquet'), (ZONES, 'zones.csv')]:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(20_000_001)
            if len(data) > 20_000_000:
                raise ValueError('unexpected download size')
        (args.output / name).write_bytes(data)
        downloads.append({'url': url, 'file': name, 'bytes': len(data),
                          'sha256': hashlib.sha256(data).hexdigest()})
    table = pq.read_table(args.output / 'trips.parquet', columns=[
        'lpep_pickup_datetime', 'lpep_dropoff_datetime', 'passenger_count',
        'trip_distance', 'fare_amount', 'PULocationID', 'DOLocationID'])
    raw = table.to_pylist()
    zones = list(csv.DictReader((args.output / 'zones.csv').open()))
    db = sqlite3.connect(args.output / 'tlc.sqlite')
    try:
        db.executescript('''
        CREATE TABLE trips(trip_id INTEGER PRIMARY KEY, pickup_at TEXT, dropoff_at TEXT,
          passenger_count REAL, trip_distance REAL, fare_amount REAL,
          pickup_location_id INTEGER, dropoff_location_id INTEGER);
        CREATE TABLE zones(location_id INTEGER PRIMARY KEY, borough TEXT, zone TEXT);
        ''')
        db.executemany('INSERT INTO trips VALUES(?,?,?,?,?,?,?,?)', [
            (i, str(r['lpep_pickup_datetime']) if r['lpep_pickup_datetime'] is not None else None,
             str(r['lpep_dropoff_datetime']) if r['lpep_dropoff_datetime'] is not None else None,
             r['passenger_count'], r['trip_distance'], r['fare_amount'], r['PULocationID'], r['DOLocationID'])
            for i, r in enumerate(raw)])
        db.executemany('INSERT INTO zones VALUES(?,?,?)', [(int(r['LocationID']), r['Borough'], r['Zone']) for r in zones])
        db.execute('CREATE INDEX trips_pickup ON trips(pickup_at)')
        db.execute('CREATE INDEX trips_zone ON trips(pickup_location_id)')
        db.commit()
        # Expectations come from raw Python/Arrow rows, not executing the SQL below.
        january = sum(r['lpep_pickup_datetime'] is not None and
            datetime(2025, 1, 1) <= r['lpep_pickup_datetime'] < datetime(2025, 2, 1) for r in raw)
        counts = Counter(r['PULocationID'] for r in raw)
        names = {int(r['LocationID']): r['Zone'] for r in zones}
        top = sorted(((k, n) for k, n in counts.items() if k in names), key=lambda pair: (-pair[1], pair[0]))[:5]
        definitions = [
            ('all_rows', 'Count all raw trip records, without filtering dates, as trip_count.',
             ['trip_count'], 'SELECT COUNT(*) AS trip_count FROM trips', [[len(raw)]]),
            ('january', 'Count trips with pickup_at >= 2025-01-01 and pickup_at < 2025-02-01 as trip_count.',
             ['trip_count'], "SELECT COUNT(*) AS trip_count FROM trips WHERE pickup_at >= '2025-01-01' AND pickup_at < '2025-02-01'", [[january]]),
            ('missing_passengers', 'Count raw trips where passenger_count IS NULL as missing_count.',
             ['missing_count'], 'SELECT COUNT(*) AS missing_count FROM trips WHERE passenger_count IS NULL',
             [[sum(r['passenger_count'] is None for r in raw)]]),
            ('negative_fares', 'Count raw trips with fare_amount < 0 as negative_count. Include all dates.',
             ['negative_count'], 'SELECT COUNT(*) AS negative_count FROM trips WHERE fare_amount < 0',
             [[sum(r['fare_amount'] is not None and r['fare_amount'] < 0 for r in raw)]]),
            ('zero_distance', 'Count raw trips where trip_distance = 0 as zero_count. Include all dates.',
             ['zero_count'], 'SELECT COUNT(*) AS zero_count FROM trips WHERE trip_distance = 0',
             [[sum(r['trip_distance'] == 0 for r in raw)]]),
            ('top_zones', 'For all raw trips, return the top 5 pickup zones present in zones: location_id, zone, trip_count. Join pickup_location_id to location_id; order by trip_count descending, then location_id ascending.',
             ['location_id', 'zone', 'trip_count'], 'SELECT z.location_id,z.zone,COUNT(*) AS trip_count FROM trips t JOIN zones z ON t.pickup_location_id=z.location_id GROUP BY z.location_id,z.zone ORDER BY trip_count DESC,z.location_id ASC LIMIT 5',
             [[k, names[k], n] for k, n in top]),
        ]
        tasks, expected = [], {}
        for name, question, columns, sql, rows in definitions:
            # This assertion detects import/reference bugs before any model runs.
            cursor = db.execute(sql)
            assert [list(row) for row in cursor.fetchall()] == rows, name
            task_id = 'tlc:' + name
            tasks.append({'task_id': task_id, 'question': question, 'database': 'tlc.sqlite',
                'contract': {'columns': columns, 'min_rows': 1, 'max_rows': 100,
                    'verification_sql': sql, 'fallback_to_verified_query': True}})
            expected[task_id] = {'columns': columns, 'rows': rows}
    finally:
        db.close()
    (args.output / 'tasks.json').write_text(json.dumps(tasks, indent=2))
    (args.output / 'expected.json').write_text(json.dumps(expected, indent=2))
    manifest = {'imported_at': datetime.now(timezone.utc).isoformat(), 'sources': downloads,
        'source_page': 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page',
        'row_count': len(raw), 'zone_count': len(zones), 'rows_outside_january_or_missing_pickup': len(raw)-january,
        'transforms': 'Select seven source columns; ISO timestamp strings; add zero-based row ID. No rows dropped.',
        'checks': 'Expected answers computed independently from raw Parquet rows using Python, cross-checked against imported SQL.',
        'scope': 'Real public records; six project-authored tasks, not an official text-to-SQL benchmark. TLC does not guarantee data accuracy.',
        'sqlite_sha256': hashlib.sha256((args.output / 'tlc.sqlite').read_bytes()).hexdigest()}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
