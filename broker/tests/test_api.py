import importlib
import json
import os
import unittest
from unittest.mock import patch
from starlette.requests import Request

module=importlib.import_module('broker.app')

class FakeController:
    def __init__(self,*args): pass
    def acquire(self,body):return {'lease':body['lease'],'token':'test-connect-token'}
    def release(self,body):return {'lease':body['lease'],'terminated':True}

def request(body,authorization='Bearer test-key'):
    sent=False
    async def receive():
        nonlocal sent
        if sent:return {'type':'http.disconnect'}
        sent=True
        return {'type':'http.request','body':body,'more_body':False}
    return Request({'type':'http','method':'POST','path':'/leases/acquire','headers':[(b'authorization',authorization.encode())]},receive)

class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env=patch.dict(os.environ,{'BROKER_KEY':'test-key'});self.env.start()
        with patch.object(module,'Controller',FakeController):
            app=module.service.local()
        self.route=next(r.endpoint for r in app.routes if r.path=='/leases/{operation}')
    async def asyncTearDown(self):self.env.stop()
    async def test_unauthorized_and_no_secret_config_rejected(self):
        self.assertEqual((await self.route('acquire',request(b'{}','Bearer wrong'))).status_code,401)
        os.environ['BROKER_KEY']=''
        self.assertEqual((await self.route('acquire',request(b'{}','Bearer '))).status_code,401)
    async def test_no_tool_relay_and_payload_limits(self):
        self.assertEqual((await self.route('tool',request(b'{}'))).status_code,404)
        self.assertEqual((await self.route('acquire',request(b'x'*1025))).status_code,413)
        self.assertEqual((await self.route('acquire',request(b'[]'))).status_code,400)
        self.assertEqual((await self.route('acquire',request(b'{"code":"console.log(42)"}'))).status_code,400)
    async def test_credentials_are_never_cacheable(self):
        r=await self.route('acquire',request(json.dumps({'session':'test','lease':'a'*64}).encode()))
        self.assertEqual(r.status_code,200);self.assertEqual(r.headers['Cache-Control'],'no-store')
