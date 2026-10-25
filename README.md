# rates-data

This repo contains historical project completion rates over time, one record per line.
The data format has varied over time, so some custom parsing logic may be needed.
RC5 project data is in Mkeys/sec, and OGR is in Mnodes/sec.

## Interactive charts

The GitHub Pages site in `docs/` charts the historical rates. The parser converts
the source logs from Mkeys/sec or Mnodes/sec into Gkeys/sec or Gnodes/sec and
generates JSON shards by project and UTC year. The original logs remain the
source of truth; generated files are built during deployment and are not
committed.

The parser accepts `*-rate*.log` files for OGR, OGR-NG, OGR-P2, RC5-64, and
RC5-72. Combined `mirc*` logs are intentionally excluded. Records are assigned
to years using their timestamps, not the year in a filename. Invalid records
stop the build with an error. Duplicate timestamps are collapsed in sorted
filename and line order, keeping the last record; the parser reports how many
duplicates had differing rates.

To generate the data locally and run the parser tests:

```sh
python scripts/build_rate_data.py
python -m unittest discover -s tests
```

The generated `docs/data/` directory can be previewed with any local static
HTTP server. GitHub Actions regenerates the data and deploys the site when rate
logs or site/parser files change on `master`, or when manually dispatched. Set
the repository's Pages build and deployment source to **GitHub Actions** to
enable deployment.
