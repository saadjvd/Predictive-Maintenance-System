def test_health_check_returns_200(client):
    """Verify that the health check endpoint returns 200 and expected schema."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.get_json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert data["service"] == "PharmaPredict AI"
    assert "version" in data
    assert "timestamp" in data
    assert "database" in data
    assert data["database"] == "connected"
    assert "capabilities" in data
    assert isinstance(data["capabilities"], list)


def test_root_endpoint_returns_service_info(client):
    """Verify root index returns API service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert "service" in data
    assert data["service"] == "PharmaPredict AI"
    assert "/api/v1/health" in data["api_documentation"]


def test_nonexistent_endpoint_returns_404(client):
    """Verify standard 404 response structure."""
    response = client.get("/api/v1/nonexistent-route")
    assert response.status_code == 404
    data = response.get_json()
    assert data["error"] == "Not Found"

