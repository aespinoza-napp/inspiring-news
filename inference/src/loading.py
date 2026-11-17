"""
One model load at a time, across the whole service (2026-11-17).

transformers builds a model's weights under process-wide context managers
(empty "meta" tensors filled in afterwards) that are not thread-safe. Two
loads at once - the warm-up thread loading GLiNER, the sentiment model and
bge-m3 while a first /grounding or /decisions request loads its own - can
leave one model holding meta tensors: "NotImplementedError: Cannot copy out
of meta tensor; no data!", or "variable and tensor have incompatible tensor
type". Seen in this suite on 2026-11-17, 7 of 24 tests in one run, which
then passed twice on the same code: a race, not a bug in one model. Every
load takes this lock; inference itself does not.
"""

import threading

LOADING = threading.RLock()
