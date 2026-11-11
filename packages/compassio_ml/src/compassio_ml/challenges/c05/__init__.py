"""C05: poisoned training batch quarantine (label-flip detection before training).

Modules:

* ``config``   - the frozen challenge configuration (``configs/c05_poison_quarantine.yaml``).
* ``batch``    - the supplied training batch (ids, text, SUPPLIED labels, groups, publishers).
* ``attack``   - deterministic 5% label inversion; the ONLY module that knows the flips (oracle).
* ``detector`` - out-of-fold, group-aware label-consistency scoring (never sees the oracle).
* ``gate``     - the quarantine gate; downstream training accepts only its output.
* ``experiment`` / ``report`` / ``cli`` - the reproducible experiment and judge report.
"""
