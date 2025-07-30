import pytest
import json
import time
import threading
from pathlib import Path
from unittest.mock import patch, Mock
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
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


class TestNetworkResilienceIntegration:
    """Integration tests for network resilience and recovery patterns"""
    
    @pytest.fixture
    def fixtures_dir(self):
        """Get the fixtures directory path"""
        return Path(__file__).parent.parent / "fixtures"
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state for network resilience testing"""
        config_file = tmp_path / "network_config.json"
        config_data = {
            "presenter-id": "NETWORK_PRESENTER_123",
            "authentication": "NETWORK_AUTH_456",
            "company-number": "12345678",
            "company-name": "NETWORK TEST COMPANY LIMITED",
            "company-authentication-code": "NETWORK1234",
            "company-type": "EW",
            "contact-name": "Network Test Person",
            "contact-number": "07900 123456",
            "email": "network@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "NETWORK001",
            "url": "http://localhost:9306/v1-0/xmlgw/Gateway"  # Different port for network tests
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "network_state.json"
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
<head><title>Network Test Accounts</title></head>
<body><p>Simple network test accounts</p></body>
</html>"""
    
    def test_connection_retry_behavior(self, test_state, test_client):
        """Test that network connection failures are properly handled"""
        # Mock intermittent connection failures
        call_count = 0
        
        def mock_post_with_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise requests.exceptions.ConnectionError("Connection failed")
            else:
                # Third attempt succeeds
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>"""
                return mock_response
        
        with patch('ch_filing.client.requests.post', side_effect=mock_post_with_retry):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # Should fail immediately (no built-in retry in client)
            with pytest.raises(RequestFailure) as exc_info:
                test_client.call(test_state, envelope)
            
            assert "connection" in str(exc_info.value).lower()
            assert call_count == 1  # Only one attempt
    
    def test_slow_network_response_handling(self, test_state, test_client):
        """Test handling of slow network responses"""
        def slow_response(*args, **kwargs):
            time.sleep(0.1)  # Simulate slow response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>"""
            return mock_response
        
        with patch('ch_filing.client.requests.post', side_effect=slow_response):
            start_time = time.time()
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            response = test_client.call(test_state, envelope)
            
            end_time = time.time()
            
            # Verify response received despite delay
            assert hasattr(response, 'Body')
            assert end_time - start_time >= 0.1
    
    def test_network_timeout_scenarios(self, test_state, test_client):
        """Test various network timeout scenarios"""
        timeout_types = [
            ("connect_timeout", requests.exceptions.ConnectTimeout("Connection timeout")),
            ("read_timeout", requests.exceptions.ReadTimeout("Read timeout")),
            ("general_timeout", requests.exceptions.Timeout("General timeout"))
        ]
        
        for timeout_name, timeout_exception in timeout_types:
            with patch('ch_filing.client.requests.post', side_effect=timeout_exception):
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # Client doesn't catch specific timeout types - they propagate as-is
                with pytest.raises(type(timeout_exception)) as exc_info:
                    test_client.call(test_state, envelope)
                
                assert timeout_name.replace("_", " ") in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()
    
    def test_dns_resolution_failures(self, test_state):
        """Test handling of DNS resolution failures"""
        # Create client with invalid hostname
        invalid_state = State(test_state.config_file, test_state.state_file)
        invalid_state.set("url", "http://nonexistent.companieshouse.invalid/v1-0/xmlgw/Gateway")
        
        client = Client(invalid_state)
        
        content = CompanyData.create_request(invalid_state)
        envelope = Envelope.create(invalid_state, content, "CompanyDataRequest", "request")
        
        # Should raise RequestFailure due to connection error
        with pytest.raises(RequestFailure) as exc_info:
            client.call(invalid_state, envelope)
        
        error_message = str(exc_info.value).lower()
        assert any(keyword in error_message for keyword in [
            "name", "resolution", "connection", "failed", "unreachable"
        ])
    
    def test_server_unavailable_scenarios(self, test_state, test_client):
        """Test handling when server is completely unavailable"""
        # Test with server that immediately refuses connections
        unavailable_state = State(test_state.config_file, test_state.state_file)
        unavailable_state.set("url", "http://localhost:9999/v1-0/xmlgw/Gateway")  # Unused port
        
        unavailable_client = Client(unavailable_state)
        
        content = CompanyData.create_request(unavailable_state)
        envelope = Envelope.create(unavailable_state, content, "CompanyDataRequest", "request")
        
        with pytest.raises(RequestFailure) as exc_info:
            unavailable_client.call(unavailable_state, envelope)
        
        error_message = str(exc_info.value).lower()
        assert any(keyword in error_message for keyword in [
            "connection", "refused", "failed", "unreachable"
        ])
    
    def test_partial_response_handling(self, test_state, test_client):
        """Test handling of partial or incomplete responses"""
        incomplete_responses = [
            # Truncated XML
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?><GovTalkMessage",
            # Missing closing tags
            """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails>""",
            # Empty response
            "",
            # Non-XML response
            "HTTP 500 Internal Server Error\nServer is temporarily unavailable"
        ]
        
        for i, incomplete_response in enumerate(incomplete_responses):
            with patch('ch_filing.client.requests.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = incomplete_response
                mock_post.return_value = mock_response
                
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # Should raise an XML parsing exception
                with pytest.raises(Exception) as exc_info:
                    test_client.call(test_state, envelope)
                
                # Verify it's an XML-related error
                error_message = str(exc_info.value).lower()
                assert any(keyword in error_message for keyword in [
                    "xml", "parsing", "parse", "invalid", "syntax", "encoding"
                ]) or "lxml" in str(type(exc_info.value))
    
    def test_large_response_handling(self, test_state, test_client):
        """Test handling of unusually large responses"""
        # Create a large response with repeated elements
        large_body_content = "<LargeData>" + ("x" * 10000) + "</LargeData>" * 100
        large_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body>
        <CompanyDataResponse>
            <CompanyNumber>12345678</CompanyNumber>
            {large_body_content}
        </CompanyDataResponse>
    </Body>
</GovTalkMessage>"""
        
        with patch('ch_filing.client.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = large_response
            mock_post.return_value = mock_response
            
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # Should handle large response successfully
            response = test_client.call(test_state, envelope)
            assert hasattr(response, 'Body')
            assert hasattr(response.Body.CompanyDataResponse, 'CompanyNumber')
    
    def test_concurrent_request_handling(self, test_state):
        """Test handling of concurrent requests"""
        results = []
        errors = []
        
        def make_request(client, request_id):
            try:
                # Create unique state for each thread to avoid conflicts
                thread_state = State(test_state.config_file, test_state.state_file)
                
                content = CompanyData.create_request(thread_state)
                envelope = Envelope.create(thread_state, content, "CompanyDataRequest", "request")
                
                with patch('ch_filing.client.requests.post') as mock_post:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_response.text = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber><RequestID>{request_id}</RequestID></CompanyDataResponse></Body>
</GovTalkMessage>"""
                    mock_post.return_value = mock_response
                    
                    response = client.call(thread_state, envelope)
                    results.append((request_id, response))
                    
            except Exception as e:
                errors.append((request_id, str(e)))
        
        # Create multiple threads making concurrent requests
        threads = []
        clients = [Client(test_state) for _ in range(5)]
        
        for i, client in enumerate(clients):
            thread = threading.Thread(target=make_request, args=(client, f"req_{i}"))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify all requests succeeded
        assert len(errors) == 0, f"Concurrent requests failed: {errors}"
        assert len(results) == 5
        
        # Verify each response is unique
        request_ids = [result[0] for result in results]
        assert len(set(request_ids)) == 5
    
    def test_network_interface_changes(self, test_state, test_client):
        """Test resilience to network interface changes"""
        # Simulate network interface going down and coming back up
        call_count = 0
        
        def simulate_interface_change(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count == 1:
                # First call: interface down
                raise requests.exceptions.ConnectionError("Network is unreachable")
            elif call_count == 2:
                # Second call: interface coming back up
                raise requests.exceptions.ConnectionError("Connection temporarily unavailable")
            else:
                # Third call: interface back up
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>"""
                return mock_response
        
        with patch('ch_filing.client.requests.post', side_effect=simulate_interface_change):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # First attempt should fail
            with pytest.raises(RequestFailure) as exc_info:
                test_client.call(test_state, envelope)
            
            assert "unreachable" in str(exc_info.value).lower()
            assert call_count == 1
    
    def test_bandwidth_limited_scenarios(self, test_state, test_client):
        """Test behavior under bandwidth-limited conditions"""
        def simulate_slow_upload(*args, **kwargs):
            # Simulate slow upload by adding delay proportional to data size
            data = kwargs.get('data', b'')
            data_size = len(data) if data else 0
            
            # Simulate 1KB/s upload speed
            delay = min(data_size / 1000.0, 2.0)  # Cap at 2 seconds for test
            time.sleep(delay)
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>"""
            return mock_response
        
        with patch('ch_filing.client.requests.post', side_effect=simulate_slow_upload):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            start_time = time.time()
            response = test_client.call(test_state, envelope)
            end_time = time.time()
            
            # Should complete successfully despite slow upload
            assert hasattr(response, 'Body')
            # Should take measurable time due to simulated slow upload
            assert end_time - start_time > 0.0
    
    def test_proxy_connection_scenarios(self, test_state, test_client):
        """Test various proxy connection scenarios"""
        proxy_scenarios = [
            ("proxy_connection_error", requests.exceptions.ProxyError("Proxy connection failed")),
            ("proxy_auth_error", requests.exceptions.ProxyError("Proxy authentication required")),
            ("proxy_timeout", requests.exceptions.ConnectTimeout("Proxy timeout"))
        ]
        
        for scenario_name, proxy_exception in proxy_scenarios:
            with patch('ch_filing.client.requests.post', side_effect=proxy_exception):
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # Client should catch connection-related proxy errors as RequestFailure
                if isinstance(proxy_exception, (requests.exceptions.ProxyError, requests.exceptions.ConnectTimeout)):
                    if "connection" in str(proxy_exception).lower():
                        expected_exception = RequestFailure
                    else:
                        expected_exception = type(proxy_exception)
                else:
                    expected_exception = type(proxy_exception)
                
                with pytest.raises(expected_exception) as exc_info:
                    test_client.call(test_state, envelope)
                
                assert "proxy" in str(exc_info.value).lower() or "timeout" in str(exc_info.value).lower()
    
    def test_firewall_blocking_scenarios(self, test_state):
        """Test scenarios where firewall blocks connections"""
        # Simulate different firewall blocking behaviors
        firewall_errors = [
            requests.exceptions.ConnectionError("Connection refused by firewall"),
            requests.exceptions.ConnectionError("Connection reset by peer"),
            requests.exceptions.Timeout("Connection filtered by firewall")
        ]
        
        for firewall_error in firewall_errors:
            client = Client(test_state)
            
            with patch('ch_filing.client.requests.post', side_effect=firewall_error):
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                if isinstance(firewall_error, requests.exceptions.ConnectionError):
                    expected_exception = RequestFailure
                else:
                    expected_exception = type(firewall_error)
                
                with pytest.raises(expected_exception) as exc_info:
                    client.call(test_state, envelope)
                
                error_message = str(exc_info.value).lower()
                assert any(keyword in error_message for keyword in [
                    "connection", "refused", "reset", "filtered", "timeout"
                ])
    
    def test_mobile_network_connectivity_patterns(self, test_state, test_client):
        """Test patterns typical of mobile network connectivity"""
        # Simulate mobile network: intermittent connectivity with varying quality
        call_sequence = [
            ("weak_signal", requests.exceptions.Timeout("Weak signal timeout")),
            ("roaming_delay", 0.5),  # Delay in seconds
            ("connection_drop", requests.exceptions.ConnectionError("Connection dropped")),
            ("reconnect_success", "success")
        ]
        
        call_count = 0
        
        def mobile_network_simulation(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= len(call_sequence):
                scenario_name, scenario_action = call_sequence[call_count - 1]
                
                if isinstance(scenario_action, Exception):
                    raise scenario_action
                elif isinstance(scenario_action, (int, float)):
                    time.sleep(scenario_action)
                    # Continue to success case after delay
                
                # Success case
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>"""
                return mock_response
            
            # Fallback success
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>"""
            return mock_response
        
        with patch('ch_filing.client.requests.post', side_effect=mobile_network_simulation):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # First call should fail with timeout
            with pytest.raises(requests.exceptions.Timeout):
                test_client.call(test_state, envelope)
            
            assert call_count == 1
    
    def test_server_load_balancer_failover(self, test_state, test_client):
        """Test behavior when load balancer fails over to different servers"""
        server_responses = [
            # Server 1: Overloaded
            (503, "Service temporarily unavailable - server overloaded"),
            # Server 2: Maintenance
            (503, "Service unavailable - scheduled maintenance"),
            # Server 3: Success
            (200, """<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
    <EnvelopeVersion>2.0</EnvelopeVersion>
    <Header><MessageDetails><TransactionID>12345</TransactionID></MessageDetails></Header>
    <GovTalkDetails></GovTalkDetails>
    <Body><CompanyDataResponse><CompanyNumber>12345678</CompanyNumber></CompanyDataResponse></Body>
</GovTalkMessage>""")
        ]
        
        call_count = 0
        
        def load_balancer_simulation(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= len(server_responses):
                status_code, response_text = server_responses[call_count - 1]
            else:
                # Default to success
                status_code, response_text = server_responses[-1]
            
            mock_response = Mock()
            mock_response.status_code = status_code
            mock_response.text = response_text
            return mock_response
        
        with patch('ch_filing.client.requests.post', side_effect=load_balancer_simulation):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            # First attempt should fail with 503
            with pytest.raises(RuntimeError) as exc_info:
                test_client.call(test_state, envelope)
            
            assert "Status 503" in str(exc_info.value)
            assert call_count == 1
    
    def test_connection_pool_exhaustion(self, test_state):
        """Test behavior when connection pool is exhausted"""
        # Simulate connection pool exhaustion
        def pool_exhausted(*args, **kwargs):
            raise requests.exceptions.ConnectionError("HTTPSConnectionPool: pool exhausted")
        
        client = Client(test_state)
        
        with patch('ch_filing.client.requests.post', side_effect=pool_exhausted):
            content = CompanyData.create_request(test_state)
            envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
            
            with pytest.raises(RequestFailure) as exc_info:
                client.call(test_state, envelope)
            
            error_message = str(exc_info.value).lower()
            assert "pool" in error_message or "connection" in error_message
    
    def test_network_configuration_changes(self, test_state, test_client):
        """Test resilience to network configuration changes"""
        # Simulate various network configuration issues
        config_issues = [
            requests.exceptions.ConnectionError("Network configuration changed"),
            requests.exceptions.ConnectionError("Route to host unreachable"),
            requests.exceptions.ConnectionError("Address family not supported")
        ]
        
        for config_error in config_issues:
            with patch('ch_filing.client.requests.post', side_effect=config_error):
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                with pytest.raises(RequestFailure) as exc_info:
                    test_client.call(test_state, envelope)
                
                error_message = str(exc_info.value).lower()
                assert any(keyword in error_message for keyword in [
                    "network", "configuration", "route", "unreachable", "address", "family"
                ])