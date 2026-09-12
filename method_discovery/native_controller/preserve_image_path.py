"""Build-time login-shell setup: retain the base image's tool search path."""
import os
from pathlib import Path
import shlex

image_path = os.environ['PATH']
Path('/etc/profile.d/99-native-image-path.sh').write_text(
    '# Preserve image-declared tools in login shells.\n'
    'export PATH=' + shlex.quote(image_path) + ':"$PATH"\n', encoding='utf-8')
