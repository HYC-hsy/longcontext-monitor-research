"""Private traceback records and safe correlation; never capture frame locals."""
import json
import os
from pathlib import Path
import traceback
import uuid


class EpisodeFault(RuntimeError):
    def __init__(self, failure):
        self.failure = failure
        super().__init__('PMA event failed; inspect the private failure record')


def record_failure(directory, error, *, event_id=None):
    failure = {'failure_id': uuid.uuid4().hex, 'error_type': type(error).__name__}
    try:
        record = {**failure, 'event_id': event_id,
                  'traceback': ''.join(traceback.TracebackException.from_exception(
                      error, capture_locals=False).format())}
        private = Path(directory) / 'private_failures'
        private.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = private / ('failure-' + failure['failure_id'] + '.json')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, ensure_ascii=True, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        # The safe ID still identifies the failed attempt; no public exception message.
        failure['diagnostic_saved'] = False
    else:
        failure['diagnostic_saved'] = True
    return failure
