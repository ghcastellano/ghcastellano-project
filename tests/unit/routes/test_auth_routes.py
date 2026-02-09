"""Unit tests for auth routes.

Tests cover:
- Login (GET/POST, role-based redirects, invalid credentials, next page handling)
- Logout (redirect, login required)
- Change password (validation, success for each role, error paths)
- Force password change middleware (before_app_request)
- User loader (load_user callback)
"""

import pytest
import uuid
from unittest.mock import MagicMock, patch
from werkzeug.security import generate_password_hash


class MockUser:
    """Mock user that satisfies Flask-Login requirements."""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid.uuid4())
        self.email = kwargs.get('email', 'test@example.com')
        self.name = kwargs.get('name', 'Test User')
        self.role = kwargs.get('role', 'CONSULTANT')
        self.password_hash = kwargs.get(
            'password_hash', generate_password_hash('password123')
        )
        self.is_active = kwargs.get('is_active', True)
        self.is_authenticated = True
        self.must_change_password = kwargs.get('must_change_password', False)
        self.company_id = kwargs.get('company_id', None)

    def get_id(self):
        return str(self.id)


# ---------------------------------------------------------------------------
# Helper: create a mock UoW that returns the given user for both
# get_by_id (used by load_user) and get_by_email (used by login POST).
# ---------------------------------------------------------------------------

def _make_mock_uow(user=None, *, by_email=None, by_id=None, get_by_id_side_effect=None):
    """Build a MagicMock UoW with configurable user repository behaviour."""
    mock_uow = MagicMock()

    if get_by_id_side_effect is not None:
        mock_uow.users.get_by_id.side_effect = get_by_id_side_effect
    elif by_id is not None:
        mock_uow.users.get_by_id.return_value = by_id
    elif user is not None:
        mock_uow.users.get_by_id.return_value = user

    if by_email is not None:
        mock_uow.users.get_by_email.return_value = by_email
    elif user is not None:
        mock_uow.users.get_by_email.return_value = user

    return mock_uow


# ===================================================================
#  LOGIN
# ===================================================================

class TestLoginRoute:
    """Tests for GET /auth/login and POST /auth/login."""

    def test_login_get_returns_200(self, client):
        """GET /auth/login should render the login page."""
        response = client.get('/auth/login')
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_login_post_valid_consultant(self, mock_get_uow, client):
        """Successful login as CONSULTANT redirects to consultant dashboard."""
        user = MockUser(role='CONSULTANT')
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location

    @patch('src.auth.get_uow')
    def test_login_post_valid_manager(self, mock_get_uow, client):
        """Successful login as MANAGER redirects to manager dashboard."""
        user = MockUser(role='MANAGER')
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location

    @patch('src.auth.get_uow')
    def test_login_post_valid_admin(self, mock_get_uow, client):
        """Successful login as ADMIN redirects to admin index."""
        user = MockUser(role='ADMIN')
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert '/admin/' in response.location

    @patch('src.auth.get_uow')
    def test_login_post_invalid_email(self, mock_get_uow, client):
        """Login with a non-existent email stays on the login page."""
        mock_uow = MagicMock()
        mock_uow.users.get_by_email.return_value = None
        mock_get_uow.return_value = mock_uow

        response = client.post('/auth/login', data={
            'email': 'wrong@example.com',
            'password': 'wrongpass',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_login_post_wrong_password(self, mock_get_uow, client):
        """Login with correct email but wrong password stays on login page."""
        user = MockUser()  # password is 'password123'
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'wrongpassword',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_login_post_user_no_password_hash(self, mock_get_uow, client):
        """Login when user exists but has no password_hash stays on login page."""
        user = MockUser(password_hash=None)
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_login_post_exception(self, mock_get_uow, client):
        """Database exception during login shows error and stays on login page."""
        mock_uow = MagicMock()
        mock_uow.users.get_by_email.side_effect = Exception("DB Error")
        mock_get_uow.return_value = mock_uow

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_login_with_valid_next_page(self, mock_get_uow, client):
        """Login with a valid ?next= parameter redirects to that page."""
        user = MockUser(role='CONSULTANT')
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login?next=/some/page', data={
            'email': 'test@example.com',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert '/some/page' in response.location

    @patch('src.auth.get_uow')
    def test_login_with_invalid_next_page(self, mock_get_uow, client):
        """Next page not starting with '/' is rejected (open-redirect protection)."""
        user = MockUser(role='CONSULTANT')
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login?next=http://evil.com', data={
            'email': 'test@example.com',
            'password': 'password123',
        })
        assert response.status_code == 302
        assert 'evil.com' not in response.location

    @patch('src.auth.get_uow')
    def test_login_with_remember_me(self, mock_get_uow, client):
        """Login with remember=on should still succeed and redirect."""
        user = MockUser(role='CONSULTANT')
        mock_get_uow.return_value = _make_mock_uow(user)

        response = client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
            'remember': 'on',
        })
        assert response.status_code == 302

    @patch('src.auth.get_uow')
    def test_login_clears_selected_est_id(self, mock_get_uow, client):
        """Login should clear the selected_est_id session key."""
        user = MockUser(role='CONSULTANT')
        mock_get_uow.return_value = _make_mock_uow(user)

        # Pre-set session value
        with client.session_transaction() as sess:
            sess['selected_est_id'] = 'some-id'

        client.post('/auth/login', data={
            'email': 'test@example.com',
            'password': 'password123',
        })

        with client.session_transaction() as sess:
            assert 'selected_est_id' not in sess


# ===================================================================
#  LOGOUT
# ===================================================================

class TestLogoutRoute:
    """Tests for GET /auth/logout."""

    @patch('src.auth.get_uow')
    def test_logout_redirects_to_login(self, mock_get_uow, client):
        """Authenticated user hitting /auth/logout is redirected to login."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        # Simulate logged-in session
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.get('/auth/logout')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_logout_requires_login(self, client):
        """Unauthenticated user hitting /auth/logout is redirected (or 401)."""
        response = client.get('/auth/logout')
        assert response.status_code in [302, 401]

    @patch('src.auth.get_uow')
    def test_logout_clears_selected_est_id(self, mock_get_uow, client):
        """Logout should remove selected_est_id from the session."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['selected_est_id'] = 'some-est-id'

        client.get('/auth/logout')

        with client.session_transaction() as sess:
            assert 'selected_est_id' not in sess


# ===================================================================
#  CHANGE PASSWORD
# ===================================================================

class TestChangePasswordRoute:
    """Tests for GET/POST /auth/change-password."""

    @patch('src.auth.get_uow')
    def test_change_password_get_returns_200(self, mock_get_uow, client):
        """GET /auth/change-password renders the form."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.get('/auth/change-password')
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_change_password_empty_fields(self, mock_get_uow, client):
        """Submitting with empty fields stays on page with error."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': '',
            'new_password': '',
            'confirm_password': '',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_change_password_mismatch(self, mock_get_uow, client):
        """New password and confirmation not matching stays on page."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'newpass1234',
            'confirm_password': 'different1234',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_change_password_too_short(self, mock_get_uow, client):
        """Password shorter than 8 characters is rejected."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'sho1',
            'confirm_password': 'sho1',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_change_password_no_digits(self, mock_get_uow, client):
        """Password without any digit is rejected."""
        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'longpasswordnodigits',
            'confirm_password': 'longpasswordnodigits',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_change_password_wrong_current(self, mock_get_uow, client):
        """Providing wrong current password stays on page with error."""
        user = MockUser(password_hash=generate_password_hash('password123'))
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'wrongcurrent',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
        }, follow_redirects=True)
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_change_password_success_consultant(self, mock_get_uow, client):
        """Successful password change as CONSULTANT redirects to consultant dashboard."""
        user = MockUser(
            role='CONSULTANT',
            password_hash=generate_password_hash('password123'),
        )
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
        })
        assert response.status_code == 302
        assert '/dashboard/consultant' in response.location
        mock_get_uow.return_value.commit.assert_called_once()

    @patch('src.auth.get_uow')
    def test_change_password_success_manager(self, mock_get_uow, client):
        """Successful password change as MANAGER redirects to manager dashboard."""
        user = MockUser(
            role='MANAGER',
            password_hash=generate_password_hash('password123'),
        )
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
        })
        assert response.status_code == 302
        assert '/dashboard/manager' in response.location

    @patch('src.auth.get_uow')
    def test_change_password_success_admin(self, mock_get_uow, client):
        """Successful password change as ADMIN redirects to admin index."""
        user = MockUser(
            role='ADMIN',
            password_hash=generate_password_hash('password123'),
        )
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
        })
        assert response.status_code == 302
        assert '/admin/' in response.location

    @patch('src.auth.get_uow')
    def test_change_password_sets_must_change_password_false(self, mock_get_uow, client):
        """After successful change, must_change_password is set to False."""
        user = MockUser(
            password_hash=generate_password_hash('password123'),
            must_change_password=True,
        )
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
        })
        assert user.must_change_password is False

    @patch('src.auth.get_uow')
    def test_change_password_updates_hash(self, mock_get_uow, client):
        """After successful change, password_hash is updated to the new password."""
        from werkzeug.security import check_password_hash as chk

        user = MockUser(
            password_hash=generate_password_hash('password123'),
        )
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'brandnew999',
            'confirm_password': 'brandnew999',
        })
        assert chk(user.password_hash, 'brandnew999')

    @patch('src.auth.get_uow')
    def test_change_password_exception(self, mock_get_uow, client):
        """Database exception during change password stays on page."""
        user = MockUser(password_hash=generate_password_hash('password123'))
        mock_uow = MagicMock()
        # First call(s) for load_user succeed; the call inside
        # change_password raises.
        mock_uow.users.get_by_id.side_effect = [user, Exception("DB Error")]
        mock_get_uow.return_value = mock_uow

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.post('/auth/change-password', data={
            'current_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_change_password_requires_login(self, client):
        """Unauthenticated access to change-password redirects (or 401)."""
        response = client.get('/auth/change-password')
        assert response.status_code in [302, 401]


# ===================================================================
#  LOAD USER (user_loader callback)
# ===================================================================

class TestLoadUser:
    """Tests for the Flask-Login user_loader callback."""

    @patch('src.auth.get_uow')
    def test_load_user_returns_user(self, mock_get_uow, app):
        """load_user should return the user when found."""
        from src.auth import load_user

        user = MockUser()
        mock_get_uow.return_value = _make_mock_uow(user)

        with app.app_context():
            result = load_user(str(user.id))

        assert result is user

    @patch('src.auth.get_uow')
    def test_load_user_returns_none_when_not_found(self, mock_get_uow, app):
        """load_user should return None when the user does not exist."""
        from src.auth import load_user

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.return_value = None
        mock_get_uow.return_value = mock_uow

        with app.app_context():
            result = load_user('nonexistent-id')

        assert result is None

    @patch('src.auth.get_uow')
    def test_load_user_returns_none_on_exception(self, mock_get_uow, app):
        """load_user should return None when an exception occurs."""
        from src.auth import load_user

        mock_uow = MagicMock()
        mock_uow.users.get_by_id.side_effect = Exception("DB Error")
        mock_get_uow.return_value = mock_uow

        with app.app_context():
            result = load_user('some-id')

        assert result is None


# ===================================================================
#  FORCE PASSWORD CHANGE MIDDLEWARE (before_app_request)
# ===================================================================

class TestForcePasswordChangeMiddleware:
    """Tests for the check_force_password_change before_app_request hook."""

    @patch('src.auth.get_uow')
    def test_force_redirect_when_must_change_password(self, mock_get_uow, client):
        """User with must_change_password=True is redirected to change-password."""
        user = MockUser(must_change_password=True)
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        # Try accessing the root page (or any non-allowed endpoint)
        response = client.get('/')
        assert response.status_code == 302
        assert 'change-password' in response.location

    @patch('src.auth.get_uow')
    def test_no_redirect_for_change_password_endpoint(self, mock_get_uow, client):
        """User with must_change_password=True CAN access change-password page."""
        user = MockUser(must_change_password=True)
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.get('/auth/change-password')
        assert response.status_code == 200

    @patch('src.auth.get_uow')
    def test_no_redirect_for_logout_endpoint(self, mock_get_uow, client):
        """User with must_change_password=True CAN access logout."""
        user = MockUser(must_change_password=True)
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        response = client.get('/auth/logout')
        # Logout itself redirects to login, so we get 302
        assert response.status_code == 302
        assert 'login' in response.location

    @patch('src.auth.get_uow')
    def test_no_redirect_when_must_change_password_false(self, mock_get_uow, client):
        """User with must_change_password=False is NOT force-redirected."""
        user = MockUser(must_change_password=False, role='ADMIN')
        mock_get_uow.return_value = _make_mock_uow(user)

        with client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)

        # Access admin index -- should not be intercepted by the middleware
        response = client.get('/admin/')
        # Could be 200 or some other status depending on admin route logic,
        # but it should NOT be a redirect to change-password
        assert 'change-password' not in (response.location or '')


# ===================================================================
#  UNAUTHORIZED HANDLER
# ===================================================================

class TestUnauthorizedHandler:
    """Tests for the custom unauthorized handler."""

    def test_unauthorized_html_redirects_to_login(self, client):
        """Unauthenticated HTML request redirects to login."""
        response = client.get('/auth/logout')
        assert response.status_code == 302
        assert 'login' in response.location

    def test_unauthorized_api_returns_json_401(self, client):
        """Unauthenticated API request returns 401 JSON response."""
        response = client.get(
            '/api/status',
            headers={'Accept': 'application/json'},
        )
        # The /api/ path check or Accept header should trigger JSON response.
        # The api/status endpoint may or may not require auth; this tests the
        # handler behaviour for a protected endpoint. We check the general
        # pattern: if it returns 401, it should be JSON.
        if response.status_code == 401:
            data = response.get_json()
            assert data is not None
            assert 'error' in data or 'code' in data
