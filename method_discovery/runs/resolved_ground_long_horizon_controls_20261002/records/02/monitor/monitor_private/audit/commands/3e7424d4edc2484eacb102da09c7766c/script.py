
import sys
sys.path.insert(0, r'E:\runs\55fa000108a4dd1af5a9d4cf\workspace')

from dispatcher import handle
print("Testing handle('/'):")
print(handle('/'))
print("\nTesting handle('/missing'):")
print(handle('/missing'))
