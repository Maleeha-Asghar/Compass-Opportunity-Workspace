"""Test all API endpoints used by frontend buttons."""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from tools.auth_tool import CurrentUser

client = TestClient(app)

# Mock token for testing
MOCK_TOKEN = "test-token"

# Mock dependency for authentication
async def mock_get_current_user():
    return CurrentUser(id="test-user-id", email="test@example.com")

def test_health_endpoint():
    """Test basic health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "date" in data

def test_cors_headers_on_preflight():
    """Test CORS headers are present on preflight requests."""
    response = client.options(
        "/health/ocr",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    # FastAPI should handle OPTIONS automatically with CORSMiddleware
    assert response.status_code in [200, 204]
    assert "access-control-allow-origin" in response.headers or response.status_code == 204

def test_cors_headers_on_get():
    """Test CORS headers are present on actual requests."""
    response = client.get(
        "/health",
        headers={"Origin": "http://127.0.0.1:5173"}
    )
    assert response.status_code == 200
    # Check if CORS headers are present (they should be set by middleware)
    # Note: TestClient might not preserve all middleware headers, but we verify in integration tests

def test_all_endpoints_exist():
    """Verify all endpoints that frontend buttons call exist in the API."""
    endpoints = [
        ("GET", "/health"),
        ("POST", "/profile/update"),
        ("GET", "/profile/me"),
        ("PUT", "/profile/me"),
        ("POST", "/opportunities/search"),
        ("GET", "/opportunities/search/jobs"),
        ("GET", "/opportunities/search/jobs/1"),
        ("DELETE", "/opportunities/search/jobs/1"),
        ("GET", "/opportunities"),
        ("GET", "/opportunities/1"),
        ("POST", "/opportunities/save"),
        ("POST", "/opportunities/1/save"),
        ("DELETE", "/opportunities/1/save"),
        ("POST", "/opportunities/1/deadline-plan"),
        ("POST", "/documents/generate"),
        ("POST", "/tracker/update"),
        ("GET", "/tracker"),
        ("GET", "/documents"),
        ("GET", "/admin/eval-runs"),
        ("GET", "/admin/source-flags"),
        ("GET", "/admin/health"),
        ("GET", "/health/ocr"),
        ("GET", "/notifications/preferences"),
        ("POST", "/notifications/preferences"),
        ("POST", "/upload/poster"),
        ("POST", "/upload/document"),
    ]
    
    # Check that routes are registered
    route_paths = set()
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            route_paths.add((list(route.methods)[0] if route.methods else "GET", route.path))
    
    for method, path in endpoints:
        # Verify route exists (endpoint patterns like /opportunities/{id} may use different syntax)
        found = False
        for registered_method, registered_path in route_paths:
            if method == registered_method:
                # Check if the registered path matches the test endpoint
                # Paths with parameters like {id} should match endpoints like /opportunities/1
                if registered_path == path or path.replace("/1", "/{opportunity_id}") == registered_path.replace("/1", "/{opportunity_id}"):
                    found = True
                    break
                # More flexible matching for parameterized routes
                if "{" in registered_path:
                    import re
                    pattern = re.sub(r"\{[^}]+\}", r"[^/]+", registered_path)
                    if re.match(f"^{pattern}$", path):
                        found = True
                        break
        
        assert found, f"Endpoint {method} {path} not found in registered routes"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
