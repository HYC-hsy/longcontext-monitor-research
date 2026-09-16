"""Private Monitor Agent profiles; independent of the task harness configuration."""
import json
import os
from pathlib import Path


def load_profile(name, path=None):
    location = path or os.environ.get('MONITOR_CONFIG_FILE')
    if not location:
        raise ValueError('An explicit monitor configuration path is required')
    source = Path(location)
    profiles = json.loads(source.read_text(encoding='utf-8'))
    if name not in profiles or not isinstance(profiles[name], dict):
        raise ValueError(f'Unknown independent monitor profile: {name}')
    config = dict(profiles[name])
    if not all(config.get(k) for k in ('apikey', 'apibase', 'model')):
        raise ValueError('Monitor profile requires apikey, apibase and model')
    return config
