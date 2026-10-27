"""Single-owner lifecycle state machine. Tool payloads never pass through here.

The service serializes requests; the atomic slot and fixed live sandbox name also
fail closed on uncertain allocation/restarts. No automatic lease renewal/replay.
"""
import re
import time

LIFETIME = 240
RESERVATION = 300  # includes allocation time; must exceed the hard sandbox TTL


class Rejected(Exception):
    def __init__(self, reason, status=409):
        self.reason, self.status = reason, status
        super().__init__(reason)


class Controller:
    def __init__(self, ledger, backend, now=time.time):
        self.ledger, self.backend, self.now = ledger, backend, now

    def acquire(self, body):
        session, lease = body.get('session'), body.get('lease')
        if not isinstance(session, str) or not re.fullmatch(r'[a-z0-9-]{1,64}', session):
            raise Rejected('invalid-session', 400)
        if not isinstance(lease, str) or not re.fullmatch(r'[a-f0-9]{64}', lease):
            raise Rejected('invalid-lease', 400)
        key = 'lease:' + lease
        previous = self.ledger.get(key, None)
        if previous:
            if previous['session'] != session:
                raise Rejected('lease-conflict')
            if previous['status'] != 'active':
                raise Rejected('lease-not-active-no-replay')
            sandbox = self.backend.get(previous['sandbox'])
            if sandbox is None or sandbox.poll() is not None or previous['until'] <= self.now():
                raise Rejected('lease-expired-release-required')
            # Reconnecting does not extend the sandbox's hard lifetime.
            return self.describe(previous, sandbox)
        slot = {'lease': lease, 'until': self.now() + RESERVATION}
        if not self.ledger.put('slot', slot, skip_if_exists=True):
            raise Rejected('active-or-uncertain-lease-release-required')
        record = dict(slot, session=session, status='allocating')
        self.ledger[key] = record  # reserve before allocating any compute
        sandbox = None
        try:
            sandbox = self.backend.create(session)
            record.update(sandbox=sandbox.object_id)
            self.ledger[key] = record  # persist ID before waiting for readiness
            self.backend.ready(sandbox)
            record['status'] = 'active'
            self.ledger[key] = record
            return self.describe(record, sandbox)
        except Exception:
            # Preserve the reservation even if allocation returned no sandbox ID.
            # Explicit release reconciles by name; hard lifetime bounds leakage.
            record['status'] = 'uncertain'
            self.ledger[key] = record
            if sandbox:
                try:
                    self.backend.terminate(sandbox)
                except Exception:
                    pass
            raise Rejected('allocation-uncertain-release-required', 502) from None

    def describe(self, record, sandbox):
        credentials = self.backend.connect(sandbox)
        return {'lease': record['lease'], 'sandbox': sandbox.object_id,
                'url': credentials.url.rstrip('/') + '/mcp', 'token': credentials.token,
                'until': record['until'], 'image': self.backend.image}

    def release(self, body):
        lease = body.get('lease')
        if not isinstance(lease, str) or not re.fullmatch(r'[a-f0-9]{64}', lease):
            raise Rejected('invalid-lease', 400)
        key = 'lease:' + lease
        record, slot = self.ledger.get(key, None), self.ledger.get('slot', None)
        if record and record['status'] == 'released':
            if slot and slot['lease'] == lease:
                del self.ledger['slot']
            return {'lease': lease, 'terminated': True}
        if not slot or slot['lease'] != lease:
            raise Rejected('lease-not-current')
        # Covers a crash after atomic slot reservation but before record storage.
        record = record or dict(slot, status='uncertain')
        sandbox = self.backend.get(record['sandbox']) if record.get('sandbox') else self.backend.find()
        if sandbox:
            self.backend.terminate(sandbox)
            if sandbox.poll() is None:
                raise Rejected('termination-unverified', 502)
        elif self.now() < slot['until']:
            # An allocation whose response was lost might still be in flight.
            raise Rejected('allocation-outcome-uncertain')
        record['status'] = 'released'
        self.ledger[key] = record
        del self.ledger['slot']  # only after verified death or conservative expiry
        return {'lease': lease, 'terminated': True}
