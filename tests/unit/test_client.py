import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from lxml import objectify, etree
import requests

from ch_filing.client import (
    Client, 
    AuthenticationFailure, 
    SuspectedAccountsCorruption, 
    SuspectedValidationFailure, 
    RequestFailure, 
    PrivacyFailure
)
from ch_filing.state import State


class TestClient:
    """Test the Client class for HTTP communication and error handling"""
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state for client testing"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "url": "https://test.companieshouse.gov.uk/v1-0/xmlgw/Gateway",
            "presenter-id": "TEST_PRESENTER_123",
            "authentication": "TEST_AUTH_456",
            "company-number": "12345678"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "test_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def test_client(self, test_state):
        """Create a test client instance"""
        return Client(test_state)
    
    @pytest.fixture
    def sample_envelope(self):
        """Create a sample XML envelope for testing"""
        maker = objectify.ElementMaker(
            annotate=False,
            namespace="http://www.govtalk.gov.uk/CM/envelope",
            nsmap={None: "http://www.govtalk.gov.uk/CM/envelope"}
        )
        
        envelope = maker.GovTalkMessage(
            maker.EnvelopeVersion("2.0"),
            maker.Header(
                maker.MessageDetails(
                    maker.Class("TestClass"),
                    maker.Qualifier("request"),
                    maker.TransactionID("123")
                )
            ),
            maker.GovTalkDetails(
                maker.Keys(),
            ),
            maker.Body(
                maker.TestContent("Sample content")
            )
        )
        
        return envelope
    
    @pytest.fixture
    def successful_response_xml(self):
        """Create a sample successful response XML"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header>
        <MessageDetails>
            <Class>TestClass</Class>
            <Qualifier>response</Qualifier>
            <TransactionID>123</TransactionID>
        </MessageDetails>
    </Header>
    <GovTalkDetails>
        <Keys/>
    </GovTalkDetails>
    <Body>
        <SuccessResponse>
            <Message>Request processed successfully</Message>
        </SuccessResponse>
    </Body>
</GovTalkMessage>"""
    
    @pytest.fixture
    def error_response_xml(self):
        """Create a sample error response XML with authentication failure"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header>
        <MessageDetails>
            <Class>TestClass</Class>
            <Qualifier>error</Qualifier>
            <TransactionID>123</TransactionID>
        </MessageDetails>
    </Header>
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <RaisedBy>CH</RaisedBy>
                <Number>502</Number>
                <Type>fatal</Type>
                <Text>Authentication failure</Text>
                <Location>Header/SenderDetails/IDAuthentication</Location>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
    
    def test_client_initialization(self, test_state):
        """Test Client initialization with state"""
        client = Client(test_state)
        
        assert client.state is test_state
    
    def test_get_next_tx_id_delegation(self, test_client):
        """Test that get_next_tx_id() delegates to state"""
        initial_tx_id = test_client.state.get_cur_tx_id()
        
        next_id = test_client.get_next_tx_id()
        
        assert next_id == initial_tx_id + 1
        assert test_client.state.get_cur_tx_id() == initial_tx_id + 1
    
    @patch('ch_filing.client.requests.post')
    def test_successful_call(self, mock_post, test_client, sample_envelope, successful_response_xml):
        """Test successful HTTP call and response parsing"""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = successful_response_xml
        mock_post.return_value = mock_response
        
        # Make the call
        result = test_client.call(test_client.state, sample_envelope)
        
        # Verify request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        assert call_args[1]['data'] is not None  # XML data was sent
        assert call_args[1]['headers']['Content-Type'] == 'text/xml'
        
        # Check that XML declaration is included
        sent_data = call_args[1]['data']
        assert b'<?xml version=' in sent_data
        
        # Verify response parsing
        assert hasattr(result, 'Body')
        assert hasattr(result.Body, 'SuccessResponse')
        assert str(result.Body.SuccessResponse.Message) == "Request processed successfully"
    
    @patch('ch_filing.client.requests.post')
    def test_authentication_failure_error(self, mock_post, test_client, sample_envelope, error_response_xml):
        """Test authentication failure error handling (error 502)"""
        # Setup mock response with error
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = error_response_xml
        mock_post.return_value = mock_response
        
        # Should raise AuthenticationFailure
        with pytest.raises(AuthenticationFailure) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "Authentication failure" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_suspected_accounts_corruption_error(self, mock_post, test_client, sample_envelope):
        """Test suspected accounts corruption error handling (error 9999)"""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <Number>9999</Number>
                <Text>Suspected accounts corruption</Text>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = error_xml
        mock_post.return_value = mock_response
        
        with pytest.raises(SuspectedAccountsCorruption) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "Suspected accounts corruption" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_suspected_validation_failure_error(self, mock_post, test_client, sample_envelope):
        """Test suspected validation failure error handling (error 100)"""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <Number>100</Number>
                <Text>Validation failure detected</Text>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = error_xml
        mock_post.return_value = mock_response
        
        with pytest.raises(SuspectedValidationFailure) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "Validation failure detected" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_generic_error_handling(self, mock_post, test_client, sample_envelope):
        """Test generic error handling for unknown error codes"""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <Number>999</Number>
                <Text>Unknown error occurred</Text>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = error_xml
        mock_post.return_value = mock_response
        
        with pytest.raises(RuntimeError) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "Unknown error occurred" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_multiple_errors_handling(self, mock_post, test_client, sample_envelope):
        """Test handling when multiple errors are present (should raise first one)"""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <Number>502</Number>
                <Text>First error - authentication</Text>
            </Error>
            <Error>
                <Number>100</Number>
                <Text>Second error - validation</Text>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
    <Body/>
</GovTalkMessage>"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = error_xml
        mock_post.return_value = mock_response
        
        # Should raise the first error (AuthenticationFailure)
        with pytest.raises(AuthenticationFailure) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "First error - authentication" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_ssl_error_handling(self, mock_post, test_client, sample_envelope):
        """Test SSL error handling"""
        mock_post.side_effect = requests.exceptions.SSLError("SSL certificate verification failed")
        
        with pytest.raises(PrivacyFailure) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "SSL certificate verification failed" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_connection_error_handling(self, mock_post, test_client, sample_envelope):
        """Test connection error handling"""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        with pytest.raises(RequestFailure) as exc_info:
            test_client.call(test_client.state, sample_envelope)
        
        assert "Connection refused" in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_http_error_status_codes(self, mock_post, test_client, sample_envelope):
        """Test handling of non-200 HTTP status codes"""
        test_cases = [
            (400, "Status 400"),
            (401, "Status 401"),
            (403, "Status 403"),
            (404, "Status 404"),
            (500, "Status 500"),
            (503, "Status 503"),
        ]
        
        for status_code, expected_message in test_cases:
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_post.return_value = mock_response
            
            with pytest.raises(RuntimeError) as exc_info:
                test_client.call(test_client.state, sample_envelope)
            
            assert expected_message in str(exc_info.value)
    
    @patch('ch_filing.client.requests.post')
    def test_xml_serialization_in_request(self, mock_post, test_client, sample_envelope, successful_response_xml):
        """Test that XML is properly serialized in the request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = successful_response_xml
        mock_post.return_value = mock_response
        
        test_client.call(test_client.state, sample_envelope)
        
        # Verify the sent data
        call_args = mock_post.call_args
        sent_data = call_args[1]['data']
        
        # Should be bytes
        assert isinstance(sent_data, bytes)
        
        # Should contain XML declaration
        assert sent_data.startswith(b'<?xml version=')
        
        # Should contain the envelope content
        assert b'GovTalkMessage' in sent_data
        assert b'TestContent' in sent_data
        assert b'Sample content' in sent_data
    
    @patch('ch_filing.client.requests.post')
    def test_response_without_errors(self, mock_post, test_client, sample_envelope):
        """Test response parsing when no errors are present"""
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <Body>
        <SuccessData>Content without errors</SuccessData>
    </Body>
</GovTalkMessage>"""
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = response_xml
        mock_post.return_value = mock_response
        
        # Should not raise any exception
        result = test_client.call(test_client.state, sample_envelope)
        
        assert hasattr(result, 'Body')
        assert str(result.Body.SuccessData) == "Content without errors"
    
    @patch('ch_filing.client.requests.post')
    def test_malformed_xml_response(self, mock_post, test_client, sample_envelope):
        """Test handling of malformed XML response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "{ this is not XML }"
        mock_post.return_value = mock_response
        
        # Should raise an XML parsing error
        with pytest.raises(Exception):  # lxml will raise various XML parsing exceptions
            test_client.call(test_client.state, sample_envelope)
    
    @patch('ch_filing.client.requests.post')
    def test_empty_response(self, mock_post, test_client, sample_envelope):
        """Test handling of empty response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception):  # XML parsing should fail
            test_client.call(test_client.state, sample_envelope)
    
    def test_review_errors_with_valid_error_structure(self, test_client):
        """Test the review_errors method directly with valid error structure"""
        error_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <GovTalkErrors>
            <Error>
                <Number>502</Number>
                <Text>Direct authentication test</Text>
            </Error>
        </GovTalkErrors>
    </GovTalkDetails>
</GovTalkMessage>"""
        
        root = objectify.fromstring(error_xml.encode('utf-8'))
        
        with pytest.raises(AuthenticationFailure) as exc_info:
            test_client.review_errors(root)
        
        assert "Direct authentication test" in str(exc_info.value)
    
    def test_review_errors_without_errors(self, test_client):
        """Test the review_errors method with response that has no errors"""
        success_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <Keys/>
    </GovTalkDetails>
    <Body>
        <Success>No errors here</Success>
    </Body>
</GovTalkMessage>"""
        
        root = objectify.fromstring(success_xml.encode('utf-8'))
        
        # Should not raise any exception
        test_client.review_errors(root)
    
    def test_review_errors_with_malformed_error_structure(self, test_client):
        """Test review_errors with malformed error structure"""
        malformed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <GovTalkDetails>
        <SomethingElse>Not errors</SomethingElse>
    </GovTalkDetails>
</GovTalkMessage>"""
        
        root = objectify.fromstring(malformed_xml.encode('utf-8'))
        
        # Should not raise any exception due to try/catch in review_errors
        test_client.review_errors(root)
    
    @patch('ch_filing.client.requests.post')
    def test_url_from_state(self, mock_post, test_client, sample_envelope, successful_response_xml):
        """Test that the correct URL from state is used for requests"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = successful_response_xml
        mock_post.return_value = mock_response
        
        test_client.call(test_client.state, sample_envelope)
        
        # Verify URL was taken from state
        call_args = mock_post.call_args
        called_url = call_args[0][0]  # First positional argument
        expected_url = test_client.state.get("url")
        
        assert called_url == expected_url
        assert "test.companieshouse.gov.uk" in called_url
    
    @patch('ch_filing.client.requests.post')
    def test_content_type_header(self, mock_post, test_client, sample_envelope, successful_response_xml):
        """Test that correct Content-Type header is set"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = successful_response_xml
        mock_post.return_value = mock_response
        
        test_client.call(test_client.state, sample_envelope)
        
        call_args = mock_post.call_args
        headers = call_args[1]['headers']
        
        assert headers['Content-Type'] == 'text/xml'
    
    def test_exception_classes_inheritance(self):
        """Test that custom exception classes inherit from correct base classes"""
        assert issubclass(AuthenticationFailure, RuntimeError)
        assert issubclass(SuspectedAccountsCorruption, RuntimeError)
        assert issubclass(SuspectedValidationFailure, RuntimeError)
        assert issubclass(RequestFailure, RuntimeError)
        assert issubclass(PrivacyFailure, RuntimeError)
    
    def test_exception_classes_instantiation(self):
        """Test that custom exception classes can be instantiated with messages"""
        auth_error = AuthenticationFailure("Auth failed")
        assert str(auth_error) == "Auth failed"
        
        corruption_error = SuspectedAccountsCorruption("Data corrupted")
        assert str(corruption_error) == "Data corrupted"
        
        validation_error = SuspectedValidationFailure("Validation failed")
        assert str(validation_error) == "Validation failed"
        
        request_error = RequestFailure("Request failed")
        assert str(request_error) == "Request failed"
        
        privacy_error = PrivacyFailure("Privacy issue")
        assert str(privacy_error) == "Privacy issue"