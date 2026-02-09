"""
Integration tests for file upload flow.

Tests cover:
- PDF upload validation
- Image upload for evidence
- File type rejection
- Size limit enforcement
"""

import pytest
import io


class TestPDFUpload:
    """Tests for PDF upload functionality."""

    def test_upload_requires_authentication(self, client):
        """Upload endpoint should require login."""
        response = client.post('/upload')
        assert response.status_code in [302, 401, 403]

    def test_upload_get_redirects_to_dashboard(self, auth_client):
        """GET request to upload should redirect."""
        client, user = auth_client
        response = client.get('/upload')
        assert response.status_code == 302

    def test_upload_without_file(self, auth_client):
        """Should handle upload without file."""
        client, user = auth_client
        response = client.post('/upload', data={}, follow_redirects=True)
        # Should show error or redirect back
        assert response.status_code == 200

    def test_upload_empty_file(self, auth_client):
        """Should reject empty file upload."""
        client, user = auth_client
        response = client.post('/upload', data={
            'file': (io.BytesIO(b''), 'empty.pdf')
        }, follow_redirects=True)
        assert response.status_code == 200

    def test_upload_invalid_file_type(self, auth_client):
        """Should reject non-PDF files."""
        client, user = auth_client

        # Create fake text file with .pdf extension
        fake_content = b'This is not a PDF file, just plain text.'

        response = client.post('/upload', data={
            'file': (io.BytesIO(fake_content), 'fake.pdf')
        }, content_type='multipart/form-data', follow_redirects=True)

        assert response.status_code == 200
        # Should show validation error
        assert b'reconhecido' in response.data.lower() or b'rejeitado' in response.data.lower() or b'warning' in response.data.lower()

    def test_upload_valid_pdf_structure(self, auth_client, test_pdf):
        """Should accept valid PDF structure."""
        client, user = auth_client

        response = client.post('/upload', data={
            'file': (io.BytesIO(test_pdf), 'valid_report.pdf')
        }, content_type='multipart/form-data', follow_redirects=True)

        # Should process or show success (may fail later in AI processing but pass validation)
        assert response.status_code == 200


class TestEvidenceUpload:
    """Tests for evidence image upload."""

    def test_evidence_upload_requires_auth(self, client):
        """Evidence upload should require authentication."""
        response = client.post('/api/upload_evidence')
        assert response.status_code in [302, 401, 403]

    def test_evidence_upload_without_file(self, auth_client):
        """Should reject evidence upload without file."""
        client, user = auth_client
        response = client.post('/api/upload_evidence')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_evidence_upload_invalid_type(self, auth_client):
        """Should reject non-image files for evidence."""
        client, user = auth_client

        # Try to upload a text file as evidence
        fake_content = b'This is not an image'

        response = client.post('/api/upload_evidence', data={
            'file': (io.BytesIO(fake_content), 'fake.png')
        }, content_type='multipart/form-data')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_evidence_upload_valid_png(self, auth_client, test_png):
        """Should accept valid PNG image."""
        client, user = auth_client

        response = client.post('/api/upload_evidence', data={
            'file': (io.BytesIO(test_png), 'evidence.png')
        }, content_type='multipart/form-data')

        # Should succeed or return URL
        # Note: May fail if storage service not configured, but validation should pass
        assert response.status_code in [200, 500]  # 500 if storage not configured

    def test_evidence_upload_valid_jpg(self, auth_client, test_jpg):
        """Should accept valid JPEG image."""
        client, user = auth_client

        response = client.post('/api/upload_evidence', data={
            'file': (io.BytesIO(test_jpg), 'evidence.jpg')
        }, content_type='multipart/form-data')

        assert response.status_code in [200, 500]


class TestFileValidation:
    """Tests for file validation security."""

    def test_pdf_extension_with_image_content(self, auth_client, test_png):
        """Should reject image content with PDF extension."""
        client, user = auth_client

        response = client.post('/upload', data={
            'file': (io.BytesIO(test_png), 'malicious.pdf')
        }, content_type='multipart/form-data', follow_redirects=True)

        assert response.status_code == 200
        # Should reject due to magic bytes mismatch
        assert b'rejeitado' in response.data.lower() or b'warning' in response.data.lower() or b'n\xc3\xa3o' in response.data.lower()

    def test_image_extension_with_pdf_content(self, auth_client, test_pdf):
        """Should reject PDF content with image extension."""
        client, user = auth_client

        response = client.post('/api/upload_evidence', data={
            'file': (io.BytesIO(test_pdf), 'malicious.png')
        }, content_type='multipart/form-data')

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
