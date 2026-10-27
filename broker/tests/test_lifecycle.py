import unittest
from types import SimpleNamespace
from broker.lifecycle import Controller, Rejected

class Ledger(dict):
    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self: return False
        self[key] = value.copy()
        return True

class Sandbox:
    object_id = 'sb-test'
    dead = False
    def poll(self): return 0 if self.dead else None

class Backend:
    image = 'pinned-image'
    def __init__(self): self.sb = Sandbox(); self.creates = 0; self.kills = 0
    def create(self, session): self.creates += 1; return self.sb
    def ready(self, sandbox): pass
    def get(self, identity): return self.sb
    def find(self): return self.sb
    def connect(self, sandbox): return SimpleNamespace(url='https://test.modal.host', token='secret-test-only')
    def terminate(self, sandbox): self.kills += 1; sandbox.dead = True

class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.store, self.backend = Ledger(), Backend()
        self.now = 1000
        self.c = Controller(self.store, self.backend, lambda: self.now)
        self.body = {'session': 'test', 'lease': 'a'*64}
    def test_reconnect_reuses_sandbox_without_extending_lifetime(self):
        a = self.c.acquire(self.body); self.now += 20; b = self.c.acquire(self.body)
        self.assertEqual(a['sandbox'], b['sandbox']); self.assertEqual(a['until'], b['until'])
        self.assertEqual(self.backend.creates, 1)
        self.assertNotIn('secret-test-only', str(self.store))
    def test_single_writer_and_stale_release_rejected(self):
        self.c.acquire(self.body)
        with self.assertRaises(Rejected): self.c.acquire({'session':'other','lease':'b'*64})
        with self.assertRaises(Rejected): self.c.release({'lease':'b'*64})
        self.assertFalse(self.backend.sb.dead)
    def test_release_idempotent_and_lease_never_reallocated(self):
        self.c.acquire(self.body)
        self.assertTrue(self.c.release(self.body)['terminated'])
        self.assertTrue(self.c.release(self.body)['terminated'])
        self.assertEqual(self.backend.kills, 1)
        with self.assertRaises(Rejected): self.c.acquire(self.body)
    def test_failed_readiness_keeps_reservation_until_release(self):
        self.backend.ready = lambda _: (_ for _ in ()).throw(RuntimeError())
        with self.assertRaises(Rejected): self.c.acquire(self.body)
        self.assertTrue(self.backend.sb.dead); self.assertIn('slot',self.store)
        self.c.release(self.body); self.assertNotIn('slot',self.store)
    def test_lost_allocation_response_does_not_blindly_reallocate(self):
        self.backend.create = lambda _: (_ for _ in ()).throw(RuntimeError())
        self.backend.find = lambda: None
        with self.assertRaises(Rejected): self.c.acquire(self.body)
        with self.assertRaises(Rejected): self.c.acquire(self.body)
        with self.assertRaises(Rejected): self.c.release(self.body)
        self.now += 301; self.assertTrue(self.c.release(self.body)['terminated'])
    def test_crash_after_reservation_reconciles_by_name(self):
        self.store['slot']={'lease':'a'*64,'until':1300}
        self.assertTrue(self.c.release(self.body)['terminated']); self.assertTrue(self.backend.sb.dead)
    def test_crash_after_release_checkpoint_removes_orphan_slot(self):
        self.c.acquire(self.body); self.store['lease:'+'a'*64]['status']='released'
        self.assertTrue(self.c.release(self.body)['terminated']); self.assertNotIn('slot',self.store)
    def test_unverified_termination_keeps_slot(self):
        self.c.acquire(self.body); self.backend.terminate=lambda _:None
        with self.assertRaises(Rejected):self.c.release(self.body)
        self.assertIn('slot',self.store)
    def test_expired_lease_needs_explicit_release(self):
        self.c.acquire(self.body);self.now+=301
        with self.assertRaises(Rejected):self.c.acquire(self.body)
        self.assertEqual(self.backend.creates,1)
    def test_session_conflict_and_bad_inputs(self):
        self.c.acquire(self.body)
        with self.assertRaises(Rejected):self.c.acquire({'session':'other','lease':'a'*64})
        with self.assertRaises(Rejected):self.c.acquire({'session':'../escape','lease':'b'*64})

if __name__=='__main__': unittest.main()
