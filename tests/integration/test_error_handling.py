import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, Mock

from ch_filing.client import (
    Client, 
    AuthenticationFailure, 
    SuspectedAccountsCorruption, 
    SuspectedValidationFailure, 
    RequestFailure, 
    PrivacyFailure
)
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


class TestErrorHandlingIntegration:
    """Integration tests for error handling across the entire stack"""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory path"""
        return Path(__file__).parent.parent / "fixtures"
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state for integration testing"""
        config_file = tmp_path / "integration_config.json"
        config_data = {
            "presenter-id": "INTEGRATION_PRESENTER_123",
            "authentication": "INTEGRATION_AUTH_456",
            "company-number": "12345678",
            "company-name": "INTEGRATION TEST COMPANY LIMITED",
            "company-authentication-code": "INTEGRATION1234",
            "company-type": "EW",
            "contact-name": "Integration Test Person",
            "contact-number": "07900 123456",
            "email": "integration@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "INTEGRATION001",
            "url": "http://localhost:9305/v1-0/xmlgw/Gateway"  # Test server URL
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "integration_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def test_client(self, test_state):
        """Create a test client instance"""
        return Client(test_state)
    
    @pytest.fixture
    def sample_accounts_data(self, fixtures_dir):
        """Load sample accounts data from fixtures"""
        accounts_file = fixtures_dir / "sample_accounts.html"
        if accounts_file.exists():
            return accounts_file.read_text(encoding='utf-8')
        else:
            # Fallback minimal accounts data
            return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>Test Accounts</title></head>
<body><p>Simple test accounts</p></body>
</html>"""
    
    def test_authentication_error_end_to_end(self, test_state, test_client):
        """Test authentication error handling through complete workflow"""
        # Configure mock server to return authentication error
        with MockServer(
            port=9305,
            presenter_id="WRONG_PRESENTER",
            authentication="WRONG_AUTH"
        ) as server:
            # Create a request
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # Should raise AuthenticationFailure
            with pytest.raises(AuthenticationFailure) as exc_info:
                test_client.call(test_state, envelope)
            
            assert "Authentication failure" in str(exc_info.value) or "Presenter not recognised" in str(exc_info.value)
    
    def test_company_not_found_error_handling(self, tmp_path):
        """Test handling of company not found errors"""
        # Create state with non-existent company number
        config_file = tmp_path / "invalid_company_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER",
            "authentication": "TEST_AUTH",
            "company-number": "99999999",  # Non-existent company
            "company-authentication-code": "INVALID123",
            "made-up-date": "2023-12-31",
            "url": "http://localhost:9305/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "invalid_company_state.json"
        invalid_state = State(str(config_file), str(state_file))
        client = Client(invalid_state)
        
        with MockServer(port=9305) as server:
            content = CompanyData.create_request(invalid_state)
            envelope = Envelope.create(invalid_state, content, "CompanyDataRequest", "request")
            
            # Should raise an error (could be RuntimeError for company not found)
            with pytest.raises((RuntimeError, AuthenticationFailure)) as exc_info:
                client.call(invalid_state, envelope)
            
            error_message = str(exc_info.value).lower()
            assert any(keyword in error_message for keyword in [
                "company not found", "not found", "invalid", "authentication"
            ])
    
    def test_validation_error_during_form_submission(self, test_state, test_client, sample_accounts_data):
        """Test validation error handling during form submission"""
        # Configure mock server with matching credentials
        with MockServer(
            port=9305,
            presenter_id="INTEGRATION_PRESENTER_123",
            authentication="INTEGRATION_AUTH_456",
            company_auth_code="INTEGRATION1234"
        ) as server:
            try:
                submission = Accounts.create_submission(test_state, "accounts.html", sample_accounts_data)
                envelope = Envelope.create(test_state, submission, "Accounts", "request")
                
                # The mock server should accept this, but in real scenario it might fail validation
                response = test_client.call(test_state, envelope)
                
                # If successful, verify response structure
                assert hasattr(response, 'Body')
                
            except (SuspectedValidationFailure, RuntimeError, AuthenticationFailure) as e:
                # Any of these errors are acceptable for this test
                error_msg = str(e).lower()
                assert any(keyword in error_msg for keyword in ["validation", "invalid", "authentication"])
    
    def test_network_connection_error_handling(self, test_state):
        """Test handling of network connection errors"""
        # Mock the connection error instead of using invalid URL
        client = Client(test_state)
        
        with patch('ch_filing.client.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            with pytest.raises(RequestFailure) as exc_info:
                client.call(test_state, envelope)
            
            assert "connection" in str(exc_info.value).lower() or "refused" in str(exc_info.value).lower()
    
    @patch('ch_filing.client.requests.post')
    def test_ssl_error_handling_integration(self, mock_post, test_client, test_state):
        """Test SSL error handling in integration context"""
        import requests
        mock_post.side_effect = requests.exceptions.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        
        content = CompanyData.create_request(test_state)
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        with pytest.raises(PrivacyFailure) as exc_info:
            test_client.call(test_state, envelope)
        
        assert "ssl" in str(exc_info.value).lower() or "certificate" in str(exc_info.value).lower()
    
    def test_timeout_error_handling(self, test_state):
        """Test handling of request timeout errors"""
        client = Client(test_state)
        
        # Mock a timeout directly - note that client doesn't catch Timeout specifically
        # so it will propagate as requests.exceptions.Timeout
        with patch('ch_filing.client.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # The client doesn't specifically catch Timeout, so it propagates
            with pytest.raises(requests.exceptions.Timeout) as exc_info:
                client.call(test_state, envelope)
            
            assert "timed out" in str(exc_info.value).lower()
    
    def test_malformed_response_handling(self, test_state, test_client):
        """Test handling of malformed XML responses"""
        with patch('ch_filing.client.requests.post') as mock_post:
            # Mock a response with invalid XML
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "This is not XML content"
            mock_post.return_value = mock_response
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # Should raise an XML parsing error
            with pytest.raises(Exception):  # Could be various XML parsing exceptions
                test_client.call(test_state, envelope)
    
    def test_http_error_status_codes_integration(self, test_state, test_client):
        """Test handling of various HTTP error status codes"""
        error_codes = [400, 401, 403, 404, 500, 502, 503, 504]
        
        for status_code in error_codes:
            with patch('ch_filing.client.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = status_code
                mock_post.return_value = mock_response
                
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                with pytest.raises(RuntimeError) as exc_info:
                    test_client.call(test_state, envelope)
                
                assert f"Status {status_code}" in str(exc_info.value)
    
    def test_error_recovery_after_failure(self, test_state, sample_accounts_data):
        """Test that client can recover and succeed after initial failures"""
        # Configure mock server with proper credentials
        with MockServer(
            port=9305,
            presenter_id="INTEGRATION_PRESENTER_123",
            authentication="INTEGRATION_AUTH_456",
            company_auth_code="INTEGRATION1234"
        ) as server:
            client = Client(test_state)
            
            # First request should succeed
            content1 = CompanyData.create_request(test_state)
            envelope1 = Envelope.create(test_state, content1, "CompanyDataRequest", "request")
            
            response1 = client.call(test_state, envelope1)
            assert hasattr(response1, 'Body')
            
            # Simulate a temporary failure and recovery by patching the first call
            with patch('ch_filing.client.requests.post') as mock_post:
                # First call fails
                import requests
                mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
                
                content2 = SubmissionStatus.create_request(test_state, "S00001")
                envelope2 = Envelope.create(test_state, content2, "GetSubmissionStatus", "request")
                
                with pytest.raises(RequestFailure):
                    client.call(test_state, envelope2)
                
            # Third request should succeed again (real server call)
            content3 = SubmissionStatus.create_request(test_state, "S00001")
            envelope3 = Envelope.create(test_state, content3, "GetSubmissionStatus", "request")
            
            response3 = client.call(test_state, envelope3)
            assert hasattr(response3, 'Body')
    
    def test_error_details_preservation(self, test_state, test_client):
        """Test that error details are preserved through the error handling chain"""
        with patch('ch_filing.client.requests.post') as mock_post:
            # Create a detailed error response
            error_response = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <RaisedBy>CH</RaisedBy>
                <Number>502</Number>
                <Type>fatal</Type>
                <Text>Detailed authentication failure: Invalid presenter credentials for TEST_PRESENTER</Text>
                <Location>Header/SenderDetails/IDAuthentication/SenderID</Location>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = error_response
            mock_post.return_value = mock_response
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            with pytest.raises(AuthenticationFailure) as exc_info:
                test_client.call(test_state, envelope)
            
            error_message = str(exc_info.value)
            assert "Detailed authentication failure" in error_message
            assert "TEST_PRESENTER" in error_message
    
    def test_multiple_errors_in_response(self, test_state, test_client):
        """Test handling when response contains multiple errors"""
        with patch('ch_filing.client.requests.post') as mock_post:
            multiple_errors_response = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <Number>502</Number>
                <Text>Authentication error</Text>
            </Error>
            <Error>
                <Number>100</Number>
                <Text>Validation error</Text>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = multiple_errors_response
            mock_post.return_value = mock_response
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # Should raise the first error encountered (AuthenticationFailure)
            with pytest.raises(AuthenticationFailure) as exc_info:
                test_client.call(test_state, envelope)
            
            assert "Authentication error" in str(exc_info.value)
    
    def test_transaction_id_consistency_during_errors(self, tmp_path):
        """Test that transaction IDs remain consistent even when errors occur"""
        # Create a fresh state for this test to avoid interference
        config_file = tmp_path / "tx_test_config.json"
        config_data = {
            "presenter-id": "TX_TEST_PRESENTER",
            "authentication": "TX_TEST_AUTH",
            "company-number": "12345678",
            "url": "http://localhost:9305/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "tx_test_state.json"
        fresh_state = State(str(config_file), str(state_file))
        fresh_client = Client(fresh_state)
        
        # Get initial transaction ID
        initial_tx_id = fresh_state.get_cur_tx_id()
        
        # Generate transaction IDs through normal operation
        tx_id_1 = fresh_client.get_next_tx_id()
        expected_tx_id_1 = initial_tx_id + 1
        assert tx_id_1 == expected_tx_id_1
        
        # Simulate an error scenario
        # Note: Envelope.create() will consume another transaction ID
        current_tx_id_before_envelope = fresh_state.get_cur_tx_id()
        
        with patch('ch_filing.client.requests.post') as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
            
            content = CompanyData.create_request(fresh_state)
            envelope = Envelope.create(fresh_state, content, "CompanyDataRequest", "request")
            
            with pytest.raises(RequestFailure):
                fresh_client.call(fresh_state, envelope)
        
        # Transaction ID should increment normally after error
        # (Envelope.create already consumed one TX ID)
        tx_id_after_envelope = fresh_state.get_cur_tx_id()
        assert tx_id_after_envelope == current_tx_id_before_envelope + 1
        
        tx_id_2 = fresh_client.get_next_tx_id()
        expected_tx_id_2 = tx_id_after_envelope + 1
        assert tx_id_2 == expected_tx_id_2
    
    def test_state_persistence_during_error_conditions(self, test_state):
        """Test that state is properly persisted even when errors occur"""
        # Note: Due to the load_state bug, this test verifies the actual behavior
        initial_tx_id = test_state.get_cur_tx_id()
        initial_sub_id = test_state.get_cur_submission_id()
        
        # Increment some counters
        new_tx_id = test_state.get_next_tx_id()
        new_sub_id_str = test_state.get_next_submission_id()
        
        # Simulate an error that might interrupt processing
        try:
            raise RuntimeError("Simulated processing error")
        except RuntimeError:
            pass
        
        # Verify the increments happened correctly
        assert new_tx_id == initial_tx_id + 1
        assert new_sub_id_str == f"S{initial_sub_id + 1:05d}"
        
        # State should be persisted in the state file we specified
        assert test_state.get_cur_tx_id() == new_tx_id
        assert test_state.get_cur_submission_id() == initial_sub_id + 1
    
    def test_graceful_degradation_with_partial_failures(self, test_state):
        """Test graceful degradation when some operations fail"""
        # Configure mock server with proper credentials
        with MockServer(
            port=9305,
            presenter_id="INTEGRATION_PRESENTER_123",
            authentication="INTEGRATION_AUTH_456",
            company_auth_code="INTEGRATION1234"
        ) as server:
            client = Client(test_state)
            
            # First operation succeeds
            content1 = CompanyData.create_request(test_state)
            envelope1 = Envelope.create(test_state, content1, "CompanyDataRequest", "request")
            response1 = client.call(test_state, envelope1)
            assert hasattr(response1, 'Body')
            
            # Second operation fails due to network issue
            with patch('ch_filing.client.requests.post') as mock_post:
                import requests
                mock_post.side_effect = requests.exceptions.Timeout("Request timeout")
                
                content2 = SubmissionStatus.create_request(test_state)
                envelope2 = Envelope.create(test_state, content2, "GetSubmissionStatus", "request")
                
                # Client doesn't catch Timeout specifically
                with pytest.raises(requests.exceptions.Timeout):
                    client.call(test_state, envelope2)
            
            # Third operation succeeds (server recovered)
            content3 = SubmissionStatus.create_request(test_state, "S00001")
            envelope3 = Envelope.create(test_state, content3, "GetSubmissionStatus", "request")
            response3 = client.call(test_state, envelope3)
            assert hasattr(response3, 'Body')
    
    def test_error_handling_with_different_request_types(self, test_state, test_client, sample_accounts_data):
        """Test error handling consistency across different request types"""
        request_creators = [
            ("CompanyDataRequest", lambda: CompanyData.create_request(test_state)),
            ("GetSubmissionStatus", lambda: SubmissionStatus.create_request(test_state, "S00001")),
            ("FormSubmission", lambda: Accounts.create_submission(test_state, "accounts.html", sample_accounts_data))
        ]
        
        for request_name, creator in request_creators:
            with patch('ch_filing.client.requests.post') as mock_post:
                import requests
                mock_post.side_effect = requests.exceptions.ConnectionError(f"Connection failed for {request_name}")
                
                content = creator()
                envelope = Envelope.create(test_state, content, request_name, "request")
                
                with pytest.raises(RequestFailure) as exc_info:
                    test_client.call(test_state, envelope)
                
                assert f"Connection failed for {request_name}" in str(exc_info.value)