"""Simulate the Windows default line terminator for pandas.DataFrame.to_csv.

pandas documents lineterminator as defaulting to os.linesep.  On Windows that is
'\r\n'.  This shim makes the Linux sandbox behave the same way so the reported
Windows CRLF failure can be reproduced without a Windows machine.
"""
import pandas as pd

_orig = pd.DataFrame.to_csv


def _to_csv(self, *args, **kwargs):
    kwargs.setdefault("lineterminator", "\r\n")
    return _orig(self, *args, **kwargs)


pd.DataFrame.to_csv = _to_csv
