"""Private Monitor Agent profiles; independent of the task harness configuration."""
import json
import os
from pathlib import Path


def load_profile(name, path=None):
    bundled = Path(__file__).with_name('models.local.json')
    default = bundled if bundled.exists() else Path(__file__).resolve().parents[2] / 'monitor_config' / 'models.local.json'
    source = Path(path or os.environ.get('MONITOR_CONFIG_FILE') or default)
    profiles = json.loads(source.read_text(encoding='utf-8'))
    if name not in profiles or not isinstance(profiles[name], dict):
        raise ValueError(f'Unknown independent monitor profile: {name}')
    config = dict(profiles[name])
    if not all(config.get(k) for k in ('apikey', 'apibase', 'model')):
        raise ValueError('Monitor profile requires apikey, apibase and model')
    return config
