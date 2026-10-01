import hashlib
import hmac
import http.client
import json
import threading
import unittest
from http.server import HTTPServer
from unittest import mock

import webhook


class WebhookTests(unittest.TestCase):
    def setUp(self):
        webhook._deliveries.clear()
        self.server = HTTPServer(("127.0.0.1", 0), webhook.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        if webhook._deploy_lock.locked():
            webhook._deploy_lock.release()

    def request(self, method, path, body=b"", headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=2)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        result = response.status, response.read()
        connection.close()
        return result

    def signed_headers(self, body, delivery="delivery-1"):
        signature = hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        return {
            "Content-Length": str(len(body)),
            "X-Hub-Signature-256": "sha256=" + signature,
            "X-GitHub-Event": "push",
            "X-GitHub-Delivery": delivery,
        }

    def test_only_health_get_is_exposed(self):
        self.assertEqual(self.request("GET", "/healthz")[0], 200)
        self.assertEqual(self.request("GET", "/")[0], 404)
        self.assertEqual(self.request("PUT", "/hooks/deploy")[0], 405)
        self.assertEqual(self.request("OPTIONS", "/hooks/deploy")[0], 405)

    def test_rejects_oversized_body_without_reading_it(self):
        headers = {"Content-Length": str(webhook.MAX_BODY + 1)}
        self.assertEqual(self.request("POST", "/hooks/deploy", headers=headers)[0], 413)

    @mock.patch.object(webhook, "_secret", return_value=b"secret")
    @mock.patch.object(webhook.threading.Thread, "start")
    def test_deduplicates_delivery_and_prevents_parallel_deploys(self, start, _secret):
        body = json.dumps({"ref": webhook.TARGET_REF}).encode()
        headers = self.signed_headers(body)
        self.assertEqual(self.request("POST", "/hooks/deploy", body, headers)[0], 202)
        self.assertEqual(self.request("POST", "/hooks/deploy", body, headers)[1], b"entrega duplicada")

        other = self.signed_headers(body, "delivery-2")
        self.assertEqual(self.request("POST", "/hooks/deploy", body, other)[0], 409)
        start.assert_called_once()


if __name__ == "__main__":
    unittest.main()
