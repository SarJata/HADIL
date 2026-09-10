import os
import sys
import unittest

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import app

class TestCorsConfiguration(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_01_allowed_configured_frontend_origin_preflight(self):
        """1. Allowed configured frontend origin receives successful OPTIONS preflight response."""
        custom_origin = "https://my-hadil-frontend.example.com"
        # Temporarily inject origin into ALLOWED_ORIGINS inside middleware if needed or test via TestClient
        # We test default allowed origin or configured origin.
        # Let's test with localhost origin which is allowed by default:
        response = self.client.options(
            "/api/setup/status",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Authorization, Content-Type"
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:5173")

    def test_02_required_cors_headers_present(self):
        """2. Required CORS headers are present in preflight response."""
        response = self.client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue("access-control-allow-origin" in response.headers)
        self.assertTrue("access-control-allow-methods" in response.headers)

    def test_03_authorization_header_accepted(self):
        """3. Authorization header is accepted in preflight request."""
        response = self.client.options(
            "/api/auth/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization"
            }
        )
        self.assertEqual(response.status_code, 200)
        allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
        self.assertIn("authorization", allowed_headers)

    def test_04_content_type_header_accepted(self):
        """4. Content-Type header is accepted in preflight request."""
        response = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            }
        )
        self.assertEqual(response.status_code, 200)
        allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
        self.assertIn("content-type", allowed_headers)

    def test_05_unconfigured_arbitrary_origin_rejected(self):
        """5. Unconfigured arbitrary origin is rejected (no allow-origin header returned)."""
        response = self.client.options(
            "/api/health",
            headers={
                "Origin": "https://untrusted-malicious-site.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        # CORSMiddleware does not include access-control-allow-origin for unauthorized origins
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_06_wildcard_not_used_with_credentials(self):
        """6. Wildcard '*' is not used with credentials."""
        from main import ALLOWED_ORIGINS
        self.assertNotIn("*", ALLOWED_ORIGINS)

    def test_07_https_remote_origin_when_configured(self):
        """7. HTTPS origin such as https://example.ngrok-free.app is allowed when configured in HADIL_ALLOWED_ORIGINS."""
        ngrok_origin = "https://example.ngrok-free.app"
        # Temporarily append ngrok_origin to app's ALLOWED_ORIGINS to test middleware response
        from main import ALLOWED_ORIGINS
        ALLOWED_ORIGINS.append(ngrok_origin)
        
        response = self.client.options(
            "/api/setup/status",
            headers={
                "Origin": ngrok_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization, content-type"
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), ngrok_origin)
        self.assertEqual(response.headers.get("access-control-allow-credentials"), "true")
        
        allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
        self.assertIn("authorization", allowed_headers)
        self.assertIn("content-type", allowed_headers)

        # Cleanup
        if ngrok_origin in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.remove(ngrok_origin)

    def test_08_health_preflight_works(self):
        """8. OPTIONS /health works for allowed origin."""
        response = self.client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertEqual(response.status_code, 200)

    def test_09_production_same_origin_preflight_works(self):
        """9. OPTIONS /api/setup/status and /api/auth/login return 200 for production origin (127.0.0.1:8000)."""
        prod_origin = "http://127.0.0.1:8000"
        response = self.client.options(
            "/api/setup/status",
            headers={
                "Origin": prod_origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization, content-type"
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("access-control-allow-origin"), prod_origin)

    def test_10_spa_fallback_does_not_intercept_options_preflight(self):
        """10. OPTIONS requests to / or static routes are not handled by SPA catch-all route."""
        response = self.client.options(
            "/api/nonexistent_route",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET"
            }
        )
        # Should be handled by CORS / 404 router, not return index.html static response
        self.assertNotEqual(response.headers.get("content-type"), "text/html; charset=utf-8")

if __name__ == "__main__":
    unittest.main()
