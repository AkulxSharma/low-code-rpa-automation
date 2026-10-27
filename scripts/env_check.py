"""Report whether the UB login variables are present in this process, without showing them."""
import os

for key in ("UBL_USER", "UBL_PASS"):
    value = os.environ.get(key, "")
    print("%s: %s" % (key, "set, %d characters" % len(value) if value else "NOT set"))
