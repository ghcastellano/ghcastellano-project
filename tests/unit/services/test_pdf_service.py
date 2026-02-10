"""Tests for PDFService."""
import os
from unittest.mock import patch, MagicMock

import pytest

from src.services.pdf_service import PDFService


class TestEnrichData:
    """Tests for enrich_data method."""

    def test_empty_data_does_nothing(self):
        """Should handle empty dict without error (returns early)."""
        svc = PDFService()
        data = {}
        svc.enrich_data(data)
        # Empty dict is falsy, so enrich_data returns early without modifying
        assert 'areas_inspecionadas' not in data

    def test_none_data_does_nothing(self):
        """Should handle None gracefully."""
        svc = PDFService()
        svc.enrich_data(None)  # Should not raise

    def test_adds_missing_keys(self):
        """Should add default keys if missing."""
        svc = PDFService()
        data = {'areas_inspecionadas': []}
        svc.enrich_data(data)

        assert 'aproveitamento_geral' in data
        assert 'resumo_geral' in data
        assert data['total_pontuacao_obtida'] == 0

    def test_translates_open_status_to_nao_conforme(self):
        """Should translate OPEN status to 'Não Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'OPEN', 'pontuacao': 0}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Não Conforme'

    def test_translates_compliant_status(self):
        """Should translate COMPLIANT to 'Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'COMPLIANT', 'pontuacao': 10}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Conforme'

    def test_translates_conforme_status(self):
        """Should keep 'CONFORME' as 'Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'CONFORME', 'pontuacao': 10}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Conforme'

    def test_translates_partial_status(self):
        """Should translate PARTIAL to 'Parcialmente Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'PARTIAL', 'pontuacao': 5}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Parcialmente Conforme'

    def test_translates_resolved_status(self):
        """Should translate RESOLVED to 'Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'RESOLVED', 'pontuacao': 10}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Conforme'

    def test_translates_nao_conforme_with_accent(self):
        """Should translate 'NÃO CONFORME' to 'Não Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'NÃO CONFORME', 'pontuacao': 0}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Não Conforme'

    def test_translates_parcial_status(self):
        """Should translate status containing 'PARCIAL' to 'Parcialmente Conforme'."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': 'PARCIAL', 'pontuacao': 5}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Parcialmente Conforme'

    def test_conforme_with_zero_score_gets_max_score(self):
        """If status is Conforme but score is 0, set score to max_score."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_maxima_item': 10,
                'itens': [{'status': 'CONFORME', 'pontuacao': 0}],
            }],
        }
        svc.enrich_data(data)
        item = data['areas_inspecionadas'][0]['itens'][0]
        assert item['pontuacao'] == 10

    def test_conforme_with_partial_score_becomes_parcial(self):
        """If Conforme but score between 0 and max, reclassify as Parcialmente Conforme."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_maxima_item': 10,
                'itens': [{'status': 'CONFORME', 'pontuacao': 5}],
            }],
        }
        svc.enrich_data(data)
        item = data['areas_inspecionadas'][0]['itens'][0]
        assert item['status'] == 'Parcialmente Conforme'

    def test_parcial_with_zero_score_gets_half(self):
        """If Parcialmente Conforme with score 0, default to half of max."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_maxima_item': 10,
                'itens': [{'status': 'PARCIAL', 'pontuacao': 0}],
            }],
        }
        svc.enrich_data(data)
        item = data['areas_inspecionadas'][0]['itens'][0]
        assert item['pontuacao'] == 5.0

    def test_parcial_with_zero_score_custom_max(self):
        """If Parcialmente Conforme with score 0 and custom max, default to max/2."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_maxima_item': 20,
                'itens': [{'status': 'PARCIAL', 'pontuacao': 0}],
            }],
        }
        svc.enrich_data(data)
        item = data['areas_inspecionadas'][0]['itens'][0]
        assert item['pontuacao'] == 10.0

    def test_nao_conforme_with_partial_score_reclassified(self):
        """'Não Conforme' with score > 0 and < max becomes Parcialmente Conforme."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_maxima_item': 10,
                'itens': [{'status': 'NÃO CONFORME', 'pontuacao': 3}],
            }],
        }
        svc.enrich_data(data)
        item = data['areas_inspecionadas'][0]['itens'][0]
        assert item['status'] == 'Parcialmente Conforme'

    def test_preserves_ai_area_scores(self):
        """Should preserve AI-provided area scores (pontuacao_maxima > 0)."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_obtida': 35,
                'pontuacao_maxima': 50,
                'aproveitamento': 70.0,
                'itens': [{'status': 'CONFORME', 'pontuacao': 10}],
            }],
        }
        svc.enrich_data(data)
        area = data['areas_inspecionadas'][0]
        assert area['pontuacao_obtida'] == 35.0
        assert area['pontuacao_maxima'] == 50.0
        assert area['aproveitamento'] == 70.0

    def test_fallback_recalculates_area_scores(self):
        """Should recalculate area scores when pontuacao_maxima is 0 (legacy mode)."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_maxima': 0,
                'pontuacao_maxima_item': 10,
                'itens': [
                    {'status': 'CONFORME', 'pontuacao': 10},
                    {'status': 'CONFORME', 'pontuacao': 8},
                ],
            }],
        }
        svc.enrich_data(data)
        area = data['areas_inspecionadas'][0]
        assert area['pontuacao_obtida'] == 18.0
        assert area['pontuacao_maxima'] == 20.0
        assert area['aproveitamento'] == 90.0

    def test_global_percentage_from_top_level_scores(self):
        """Should use pontuacao_geral / pontuacao_maxima_geral for global percentage."""
        svc = PDFService()
        data = {
            'pontuacao_geral': 80,
            'pontuacao_maxima_geral': 100,
            'areas_inspecionadas': [{
                'pontuacao_obtida': 80,
                'pontuacao_maxima': 100,
                'aproveitamento': 80.0,
                'itens': [],
            }],
        }
        svc.enrich_data(data)
        assert data['aproveitamento_geral'] == 80.0

    def test_global_percentage_fallback_to_area_sums(self):
        """Should fallback to area sum totals when top-level scores missing."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'pontuacao_obtida': 40,
                'pontuacao_maxima': 50,
                'aproveitamento': 80.0,
                'itens': [],
            }, {
                'pontuacao_obtida': 30,
                'pontuacao_maxima': 50,
                'aproveitamento': 60.0,
                'itens': [],
            }],
        }
        svc.enrich_data(data)
        assert data['aproveitamento_geral'] == 70.0  # 70/100
        assert data['total_pontuacao_obtida'] == 70.0

    def test_global_percentage_zero_when_no_data(self):
        """Should return 0% when no areas have scores."""
        svc = PDFService()
        data = {'areas_inspecionadas': []}
        svc.enrich_data(data)
        assert data['aproveitamento_geral'] == 0

    def test_invalid_score_continues(self):
        """Should continue past items with invalid scores."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [
                    {'status': 'CONFORME', 'pontuacao': 'invalid'},
                    {'status': 'CONFORME', 'pontuacao': 10},
                ],
            }],
        }
        svc.enrich_data(data)
        # Should not raise, processes what it can

    def test_multiple_areas_accumulate(self):
        """Should accumulate scores across multiple areas."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [
                {
                    'pontuacao_obtida': 25,
                    'pontuacao_maxima': 50,
                    'aproveitamento': 50.0,
                    'itens': [],
                },
                {
                    'pontuacao_obtida': 45,
                    'pontuacao_maxima': 50,
                    'aproveitamento': 90.0,
                    'itens': [],
                },
            ],
        }
        svc.enrich_data(data)
        assert data['total_pontuacao_obtida'] == 70.0

    def test_none_status_defaults_to_open(self):
        """Should treat None status as OPEN."""
        svc = PDFService()
        data = {
            'areas_inspecionadas': [{
                'itens': [{'status': None, 'pontuacao': 0}],
            }],
        }
        svc.enrich_data(data)
        assert data['areas_inspecionadas'][0]['itens'][0]['status'] == 'Não Conforme'


class TestResolvePath:
    """Tests for resolve_path Jinja filter."""

    def test_empty_url_returns_empty_string(self):
        """Should return empty string for falsy input."""
        svc = PDFService()
        assert svc.resolve_path('') == ''
        assert svc.resolve_path(None) == ''

    def test_http_url_returned_as_is(self):
        """Should return HTTP URLs unchanged."""
        svc = PDFService()
        url = 'https://example.com/image.png'
        assert svc.resolve_path(url) == url

    def test_file_url_returned_as_is(self):
        """Should return file:// URLs unchanged."""
        svc = PDFService()
        url = 'file:///tmp/image.png'
        assert svc.resolve_path(url) == url

    def test_evidence_url_resolves_to_gcs(self):
        """Should resolve /evidence/ URLs via GCS resolver."""
        svc = PDFService()
        with patch.object(svc, '_resolve_evidence_from_gcs', return_value='file:///tmp/evidence/img.png') as mock_gcs:
            result = svc.resolve_path('/evidence/img.png')
            assert result == 'file:///tmp/evidence/img.png'
            mock_gcs.assert_called_once_with('img.png')

    def test_static_uploads_evidence_resolves_to_gcs(self):
        """Should resolve /static/uploads/evidence/ URLs via GCS resolver."""
        svc = PDFService()
        with patch.object(svc, '_resolve_evidence_from_gcs', return_value='file:///tmp/ev.png') as mock_gcs:
            result = svc.resolve_path('/static/uploads/evidence/ev.png')
            assert result == 'file:///tmp/ev.png'
            mock_gcs.assert_called_once_with('ev.png')

    def test_absolute_path_resolved_to_file_uri(self):
        """Should convert /static/logo.png to file:// URI."""
        svc = PDFService()
        result = svc.resolve_path('/static/logo.png')
        assert result.startswith('file://')
        assert 'static/logo.png' in result

    def test_relative_url_returned_as_is(self):
        """Should return relative URLs unchanged."""
        svc = PDFService()
        assert svc.resolve_path('images/photo.jpg') == 'images/photo.jpg'


class TestResolveEvidenceFromGcs:
    """Tests for _resolve_evidence_from_gcs."""

    def test_returns_local_path_if_exists(self):
        """Should return local file path if evidence exists locally."""
        svc = PDFService()
        with patch('os.path.exists', side_effect=lambda p: 'evidence' in p and 'test.png' in p):
            result = svc._resolve_evidence_from_gcs('test.png')
            assert result.startswith('file://')
            assert 'test.png' in result

    @patch('os.path.exists', return_value=False)
    @patch.dict(os.environ, {'GCP_STORAGE_BUCKET': 'test-bucket'})
    def test_fetches_from_gcs_when_local_missing(self, mock_exists):
        """Should fetch from GCS when local file not found."""
        svc = PDFService()

        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_blob.download_to_filename = MagicMock()

        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        mock_client = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        with patch('src.services.pdf_service.os.path.exists', return_value=False), \
             patch('google.cloud.storage.Client', return_value=mock_client):
            result = svc._resolve_evidence_from_gcs('remote.png')
            assert result.startswith('file://')
            assert 'remote.png' in result

    @patch('os.path.exists', return_value=False)
    def test_returns_empty_when_not_found(self, mock_exists):
        """Should return empty string when evidence not found anywhere."""
        svc = PDFService()
        with patch.dict(os.environ, {}, clear=False):
            # Ensure GCP_STORAGE_BUCKET is not set
            os.environ.pop('GCP_STORAGE_BUCKET', None)
            result = svc._resolve_evidence_from_gcs('missing.png')
            assert result == ''

    @patch('os.path.exists', return_value=False)
    @patch.dict(os.environ, {'GCP_STORAGE_BUCKET': 'test-bucket'})
    def test_gcs_error_returns_empty(self, mock_exists):
        """Should return empty string on GCS error."""
        svc = PDFService()
        with patch('src.services.pdf_service.os.path.exists', return_value=False), \
             patch('google.cloud.storage.Client', side_effect=Exception("GCS unavailable")):
            result = svc._resolve_evidence_from_gcs('error.png')
            assert result == ''


class TestPDFServiceInit:
    """Tests for PDFService initialization."""

    def test_default_template_dir(self):
        """Should use 'src/templates' as default template dir."""
        svc = PDFService()
        assert 'src/templates' in svc.template_dir or 'templates' in svc.template_dir

    def test_absolute_template_dir(self):
        """Should keep absolute paths as-is."""
        svc = PDFService(template_dir='/absolute/path/templates')
        assert svc.template_dir == '/absolute/path/templates'

    def test_relative_template_dir_made_absolute(self):
        """Should convert relative paths to absolute."""
        svc = PDFService(template_dir='custom/templates')
        assert os.path.isabs(svc.template_dir)

    def test_jinja_env_has_resolve_path_filter(self):
        """Should register resolve_path as Jinja filter."""
        svc = PDFService()
        assert 'resolve_path' in svc.jinja_env.filters

    def test_jinja_env_has_autoescape(self):
        """Should have autoescape=True."""
        svc = PDFService()
        assert svc.jinja_env.autoescape is True


class TestGeneratePdfBytes:
    """Tests for generate_pdf_bytes."""

    def test_raises_on_missing_template(self):
        """Should raise when template doesn't exist."""
        svc = PDFService(template_dir='/nonexistent/templates')
        with pytest.raises(Exception):
            svc.generate_pdf_bytes({}, template_name='nonexistent.html')

    @patch('src.services.pdf_service.HTML')
    def test_calls_weasyprint_with_enriched_data(self, mock_html_cls):
        """Should call enrich_data and render via WeasyPrint."""
        svc = PDFService()

        mock_template = MagicMock()
        mock_template.render.return_value = '<html>test</html>'
        svc.jinja_env = MagicMock()
        svc.jinja_env.get_template.return_value = mock_template

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = b'%PDF-fake'
        mock_html_cls.return_value = mock_html_instance

        data = {'areas_inspecionadas': []}
        with patch.object(svc, 'enrich_data') as mock_enrich, \
             patch('os.path.exists', return_value=False):
            result = svc.generate_pdf_bytes(data)

        mock_enrich.assert_called_once_with(data)
        assert result == b'%PDF-fake'

    @patch('src.services.pdf_service.HTML')
    @patch('src.services.pdf_service.CSS')
    def test_includes_stylesheet_when_exists(self, mock_css_cls, mock_html_cls):
        """Should include style.css if it exists."""
        svc = PDFService()

        mock_template = MagicMock()
        mock_template.render.return_value = '<html>test</html>'
        svc.jinja_env = MagicMock()
        svc.jinja_env.get_template.return_value = mock_template

        mock_html_instance = MagicMock()
        mock_html_instance.write_pdf.return_value = b'%PDF-fake'
        mock_html_cls.return_value = mock_html_instance

        with patch.object(svc, 'enrich_data'), \
             patch('os.path.exists', return_value=True):
            svc.generate_pdf_bytes({})

        mock_css_cls.assert_called_once()
        write_pdf_call = mock_html_instance.write_pdf.call_args
        assert len(write_pdf_call[1]['stylesheets']) == 1
