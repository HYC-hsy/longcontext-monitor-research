# Synthetic PoS lifecycle fixture

Create `/app/pos-fixture-marker.txt` with exactly `POS_FILE_OK` followed by a newline. Start an HTTP service on `127.0.0.1:19173` that returns status 200. This is a synthetic wiring check, not a benchmark Task.
