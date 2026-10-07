"""Offline byte and secret-boundary verification of the B+J raw archive."""

from __future__ import annotations

import json

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.crs_v01_fyne_gate_infra_replacement_20261007 import verify_archive as inherited
from method_discovery.curator_supervisor_convergence_v0.crs_rhr_fyne_gate_20261007 import archive_result


def check():
    inherited.archive.DESTINATION = archive_result.DESTINATION
    inherited.archive.CAMPAIGN = archive_result.CAMPAIGN
    inherited.archive.RUN_ID = archive_result.RUN_ID
    result = inherited.check()
    result['schema'] = 'crs-rhr-fyne-archive-integrity/1'
    result['rhr_trace_index_sha256'] = raw.digest(
        archive_result.DESTINATION / 'RHR_TRACE_INDEX.json')
    raw.write(archive_result.DESTINATION / 'ARCHIVE_INTEGRITY.json', result)
    return result


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
