import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

from delivery_ledger import Ledger
import query_metrics as metrics

class SharedStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = {}
        self.version = 0

class FakeLedger(Ledger):
    def __init__(self, store):
        self.store = store

    def read(self):
        with self.store.lock:
            return copy.deepcopy(self.store.data), self.store.version

    def write(self, data, sha):
        with self.store.lock:
            if sha != self.store.version:
                return False
            self.store.data = copy.deepcopy(data)
            self.store.version += 1
            return True

class Tests(unittest.TestCase):
    def test_concurrent_claims_and_restart(self):
        store = SharedStore()
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: FakeLedger(store).claim('same-job'), range(4)))
        self.assertEqual(results.count('claimed'), 1)
        self.assertEqual(results.count('pending'), 3)
        FakeLedger(store).finish('same-job')
        self.assertEqual(FakeLedger(store).claim('same-job'), 'sent')

    def test_distinct_jobs_survive_concurrent_writes(self):
        store = SharedStore()
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda k: FakeLedger(store).claim(str(k)), range(4)))
        self.assertEqual(results, ['claimed'] * 4)
        self.assertEqual(len(store.data), 4)

    def test_metrics_no_double_credit_and_unknown_not_verified(self):
        metrics.ROWS.clear(); metrics.BASELINE.clear(); metrics.EXPERIMENTS.clear()
        metrics.EXPERIMENTS.add('brand storytelling')
        job = dict(title='Creative Strategist', company='Example', location='Berlin',
                   is_remote=True, url='https://example.com/1')
        metrics.record('Indeed', 'creative strategist', 'Germany', 3, [job, job])
        metrics.record('Indeed', 'brand storytelling', 'Germany', 4, [job, dict(job,url='https://example.com/2')])
        row = metrics.report()[1]
        self.assertEqual(row['incremental_vs_core_this_run'], 1)
        self.assertEqual(row['explicit_international'], 0)
        self.assertEqual(row['eligibility_unknown'], 2)
        metrics.ROWS.clear()

if __name__ == '__main__':
    unittest.main()
