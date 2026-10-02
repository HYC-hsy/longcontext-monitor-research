
import sys
sys.path.insert(0, r'E:\runs\d720ba89a8e5ad87acb69737\workspace')

from dispatcher import handle
print(handle('/'))
print(handle('/missing'))
