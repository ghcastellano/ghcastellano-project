
def test_app_imports_cleanly(client):
    """Ensures app starts without NameError/ImportError."""
    assert client is not None

def test_home_redirects_to_login(client):
    """Unauthenticated users should be redirected to login (auth middleware works)."""
    response = client.get('/', follow_redirects=True)
    assert response.status_code == 200
    assert b"Entrar" in response.data or b"Login" in response.data

def test_manager_dashboard_route_exists(client):
    """Verify manager route is registered (fixes 500 BuildError)."""
    # Just check if 401/302 is returned (route exists), not 404
    response = client.get('/dashboard/manager')
    assert response.status_code in [302, 401] 
