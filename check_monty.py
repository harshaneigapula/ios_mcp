import montydb
print(dir(montydb))
try:
    from montydb import ReplaceOne
    print("ReplaceOne found in montydb")
except ImportError:
    print("ReplaceOne NOT found in montydb")
