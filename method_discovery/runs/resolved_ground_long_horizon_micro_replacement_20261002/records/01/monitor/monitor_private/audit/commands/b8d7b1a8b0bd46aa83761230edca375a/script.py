
import sys
sys.path.insert(0, r'E:\runs\d720ba89a8e5ad87acb69737\workspace')

# Clear any cached imports
if 'dispatcher' in sys.modules:
    del sys.modules['dispatcher']
if 'wiring' in sys.modules:
    del sys.modules['wiring']

from dispatcher import handle
print("handle('/'):", handle('/'))
print("handle('/missing'):", handle('/missing'))
