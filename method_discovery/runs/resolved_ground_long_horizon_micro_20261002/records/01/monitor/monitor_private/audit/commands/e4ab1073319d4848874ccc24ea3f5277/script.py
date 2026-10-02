
import sys
sys.path.insert(0, r"E:\runs\78d6f30e4a44b2b1ce18ebfe\workspace")

from dispatcher import handle
print(handle('/'))
print(handle('/missing'))
