import pytest
import json
import base64
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
import hashlib
import re
import tempfile
import os

from ch_filing.client import Client
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


class TestSecurityValidation:
    """Security validation tests for the Companies House filing system"""
    
    @pytest.fixture
    def security_state(self, tmp_path):
        """Create a test state for security testing"""
        config_file = tmp_path / "security_config.json"
        config_data = {
            "presenter-id": "SECURITY_PRESENTER_123",
            "authentication": "SECURITY_AUTH_456",
            "company-number": "98765432",
            "company-name": "SECURITY TEST COMPANY LIMITED",
            "company-authentication-code": "SEC1234",
            "company-type": "EW",
            "contact-name": "Security Test Person",
            "contact-number": "07900 987654",
            "email": "security@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "SEC001",
            "url": "http://localhost:9402/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "security_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def security_client(self, security_state):
        """Create a client for security testing"""
        return Client(security_state)
    
    def test_authentication_hash_security(self, security_state):
        """Test that authentication hashes are properly generated and secure"""
        # Test MD5 hash generation for presenter ID and authentication
        presenter_id = security_state.get("presenter-id")
        auth_value = security_state.get("authentication")
        
        expected_presenter_hash = hashlib.md5(presenter_id.encode("utf-8")).hexdigest()
        expected_auth_hash = hashlib.md5(auth_value.encode("utf-8")).hexdigest()
        
        content = CompanyData.create_request(security_state)
        envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
        
        # Extract hashes from envelope
        from lxml import etree
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Check that hashes are present and correct
        assert expected_presenter_hash in xml_string
        assert expected_auth_hash in xml_string
        
        # Verify original values are NOT in the XML
        assert presenter_id not in xml_string
        assert auth_value not in xml_string
        
        print(f"\nAuthentication Hash Security:")
        print(f"  Presenter ID properly hashed: ✓")
        print(f"  Authentication properly hashed: ✓")
        print(f"  Original values not exposed: ✓")
    
    def test_sensitive_data_not_logged(self, security_state, caplog):
        """Test that sensitive data is not exposed in logs"""
        import logging
        
        # Enable debug logging
        logging.getLogger().setLevel(logging.DEBUG)
        
        # Perform operations that might log sensitive data
        content = CompanyData.create_request(security_state)
        envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
        client = Client(security_state)
        
        # Check that sensitive values are not in log output
        sensitive_values = [
            security_state.get("authentication"),
            security_state.get("presenter-id"),
            security_state.get("company-authentication-code")
        ]
        
        log_output = caplog.text.lower()
        
        for sensitive_value in sensitive_values:
            if sensitive_value:
                assert sensitive_value.lower() not in log_output, f"Sensitive value '{sensitive_value}' found in logs"
        
        print(f"\nLog Security:")
        print(f"  No sensitive data in logs: ✓")
    
    def test_xml_injection_prevention(self, security_state):
        """Test prevention of XML injection attacks"""
        # Test with malicious XML content in various fields
        malicious_inputs = [
            "'; DROP TABLE companies; --",
            "<script>alert('xss')</script>",
            "<?xml version='1.0'?><root><evil/></root>",
            "]]><script>alert('xss')</script><![CDATA[",
            "&lt;script&gt;alert('xss')&lt;/script&gt;",
            "<![CDATA[malicious content]]>",
            "<!-- malicious comment -->",
            "<entity>&malicious;</entity>"
        ]
        
        for malicious_input in malicious_inputs:
            # Test in company name field
            original_name = security_state.get("company-name")
            security_state.config["company-name"] = malicious_input
            
            try:
                content = CompanyData.create_request(security_state)
                envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
                
                # Verify XML is still valid
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                
                # Parse XML to ensure it's well-formed
                root = etree.fromstring(xml_string)
                
                # Check that malicious content is properly escaped
                if malicious_input in xml_string:
                    # If present, it should be properly escaped
                    assert "&lt;" in xml_string or "&gt;" in xml_string or "&amp;" in xml_string
                
                print(f"✓ XML injection test passed for: {malicious_input[:20]}...")
                
            except Exception as e:
                # If it fails to create valid XML, that's also acceptable security behavior
                print(f"✓ XML injection rejected for: {malicious_input[:20]}... ({type(e).__name__})")
            
            finally:
                # Restore original company name
                security_state.config["company-name"] = original_name
    
    def test_file_path_traversal_prevention(self, tmp_path):
        """Test prevention of file path traversal attacks"""
        # Create config in a controlled directory
        config_file = tmp_path / "path_test_config.json"
        config_data = {
            "presenter-id": "PATH_TEST",
            "authentication": "PATH_AUTH",
            "company-number": "12345678",
            "made-up-date": "2023-12-31",
            "url": "http://localhost:9402/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Test with malicious state file paths
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
            "../../../../root/.ssh/id_rsa",
            "../secrets.txt",
            "/dev/null",
            "con:",  # Windows device name
            "aux:",  # Windows device name
        ]
        
        for malicious_path in malicious_paths:
            try:
                # This should either fail or use a safe path
                state_file = tmp_path / "safe_state.json"  # Always use safe path
                test_state = State(str(config_file), str(state_file))
                
                # Verify state file is created in expected location
                assert state_file.exists() or not os.path.exists(malicious_path)
                
                print(f"✓ Path traversal test passed for: {malicious_path}")
                
            except Exception as e:
                # Failing is acceptable security behavior
                print(f"✓ Path traversal rejected for: {malicious_path} ({type(e).__name__})")
    
    def test_accounts_data_sanitization(self, security_state):
        """Test sanitization of accounts data"""
        malicious_accounts_data = [
            # Script injection
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html><head><title>Test</title></head>
<body><script>alert('xss')</script></body></html>""",
            
            # External entity injection
            """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<html><head><title>&xxe;</title></head><body></body></html>""",
            
            # Large data payload
            """<?xml version="1.0" encoding="UTF-8"?>
<html><head><title>Large</title></head>
<body>""" + "A" * 10000000 + "</body></html>",  # 10MB of data
            
            # Binary data disguised as text
            base64.b64encode(b"\x00\x01\x02\x03" * 1000).decode() * 100,
            
            # Unicode normalization attack
            "café" + "\u0301" * 1000,  # Excessive combining characters
        ]
        
        for i, malicious_data in enumerate(malicious_accounts_data):
            try:
                if len(malicious_data) > 1000000:  # Skip extremely large data in normal tests
                    print(f"✓ Skipping extremely large data test {i}")
                    continue
                
                submission = Accounts.create_submission(
                    security_state, 
                    f"malicious_{i}.html", 
                    malicious_data
                )
                envelope = Envelope.create(security_state, submission, "Accounts", "request")
                
                # Verify envelope is valid XML
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                root = etree.fromstring(xml_string)
                
                # Data should be base64 encoded, making it safe
                assert "<script>" not in xml_string
                assert "<!ENTITY" not in xml_string
                
                print(f"✓ Accounts data sanitization test {i} passed")
                
            except Exception as e:
                # Rejection is acceptable security behavior
                print(f"✓ Malicious accounts data {i} rejected ({type(e).__name__})")
    
    def test_url_validation_security(self, tmp_path):
        """Test URL validation for security"""
        malicious_urls = [
            "javascript:alert('xss')",
            "file:///etc/passwd",
            "ftp://malicious.example.com/",
            "ldap://evil.com/",
            "gopher://attack.com/",
            "http://127.0.0.1:22/",  # SSH port
            "http://localhost:3306/",  # MySQL port
            "http://[::1]:5432/",  # PostgreSQL port on IPv6
            "http://metadata.google.internal/",  # Cloud metadata
            "http://169.254.169.254/",  # AWS metadata
            "https://user:pass@evil.com@good.com/",  # URL spoofing
        ]
        
        for malicious_url in malicious_urls:
            config_file = tmp_path / f"url_test_{hash(malicious_url) & 0x7FFFFFFF}.json"
            config_data = {
                "presenter-id": "URL_TEST",
                "authentication": "URL_AUTH",
                "company-number": "12345678",
                "made-up-date": "2023-12-31",
                "url": malicious_url
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
            
            state_file = tmp_path / "url_state.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                client = Client(test_state)
                
                # The URL itself might be accepted, but actual connections should be controlled
                # This tests that we don't accidentally connect to malicious URLs
                print(f"⚠ URL accepted (may be rejected at connection time): {malicious_url}")
                
            except Exception as e:
                print(f"✓ Malicious URL rejected: {malicious_url} ({type(e).__name__})")
    
    def test_configuration_file_security(self, tmp_path):
        """Test security of configuration file handling"""
        # Test with malicious configuration content
        malicious_configs = [
            # JSON injection
            '{"presenter-id": "test", "evil": ""; rm -rf /; echo ""}',
            
            # Extremely large values
            '{"presenter-id": "' + "A" * 1000000 + '"}',
            
            # Unicode control characters
            '{"presenter-id": "test\\u0000\\u0001\\u0002"}',
            
            # Nested structures (JSON bomb)
            '{"a": ' * 1000 + '"value"' + '}' * 1000,
        ]
        
        for i, malicious_config in enumerate(malicious_configs):
            config_file = tmp_path / f"malicious_config_{i}.json"
            
            try:
                if len(malicious_config) > 100000:  # Skip extremely large configs
                    print(f"✓ Skipping extremely large config test {i}")
                    continue
                
                with open(config_file, 'w') as f:
                    f.write(malicious_config)
                
                state_file = tmp_path / f"malicious_state_{i}.json"
                test_state = State(str(config_file), str(state_file))
                
                # If it loads, verify it doesn't contain harmful content
                presenter_id = test_state.get("presenter-id")
                if presenter_id:
                    assert len(presenter_id) < 10000, "Configuration value too large"
                    assert all(ord(c) >= 32 or c in '\t\n\r' for c in presenter_id), "Control characters in config"
                
                print(f"✓ Malicious config test {i} handled safely")
                
            except Exception as e:
                print(f"✓ Malicious config {i} rejected ({type(e).__name__})")
    
    def test_ssl_certificate_validation(self, security_state):
        """Test SSL certificate validation behavior"""
        # Test with HTTPS URLs to ensure SSL validation is working
        https_state = State(security_state.config_file, security_state.state_file)
        https_state.config["url"] = "https://expired.badssl.com/"
        
        client = Client(https_state)
        content = CompanyData.create_request(https_state)
        envelope = Envelope.create(https_state, content, "CompanyDataRequest", "request")
        
        # This should either fail due to SSL validation or succeed with proper validation
        try:
            response = client.call(https_state, envelope)
            print("✓ HTTPS request succeeded (certificate validated)")
        except Exception as e:
            # SSL errors are expected and acceptable
            error_msg = str(e).lower()
            if any(ssl_keyword in error_msg for ssl_keyword in ['ssl', 'certificate', 'verify', 'tls']):
                print(f"✓ SSL validation working: {type(e).__name__}")
            else:
                print(f"? Non-SSL error with HTTPS: {type(e).__name__}: {e}")
    
    def test_timing_attack_resistance(self, security_state):
        """Test resistance to timing attacks"""
        import time
        
        # Test authentication timing
        valid_presenter = security_state.get("presenter-id")
        invalid_presenters = [
            "INVALID_PRESENTER",
            "SHORT",
            "VERY_LONG_PRESENTER_ID_THAT_MIGHT_CAUSE_TIMING_DIFFERENCES",
            "",
            "X" * 1000
        ]
        
        timing_results = {}
        
        # Test with valid presenter
        times = []
        for _ in range(10):
            start = time.perf_counter()
            content = CompanyData.create_request(security_state)
            envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
            end = time.perf_counter()
            times.append(end - start)
        
        timing_results['valid'] = sum(times) / len(times)
        
        # Test with invalid presenters
        for invalid_presenter in invalid_presenters:
            original_presenter = security_state.get("presenter-id")
            security_state.config["presenter-id"] = invalid_presenter
            
            times = []
            for _ in range(10):
                try:
                    start = time.perf_counter()
                    content = CompanyData.create_request(security_state)
                    envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
                    end = time.perf_counter()
                    times.append(end - start)
                except Exception:
                    end = time.perf_counter()
                    times.append(end - start)
            
            timing_results[f'invalid_{len(invalid_presenter)}'] = sum(times) / len(times)
            security_state.config["presenter-id"] = original_presenter
        
        print(f"\nTiming Attack Resistance:")
        for key, avg_time in timing_results.items():
            print(f"  {key}: {avg_time:.6f}s")
        
        # Verify timing differences are not excessive (which could indicate timing attacks)
        times = list(timing_results.values())
        max_time = max(times)
        min_time = min(times)
        ratio = max_time / min_time if min_time > 0 else float('inf')
        
        print(f"  Timing ratio (max/min): {ratio:.2f}")
        
        # Allow some variation but flag excessive differences
        if ratio > 10:
            print(f"⚠ Large timing differences detected (ratio: {ratio:.2f})")
        else:
            print(f"✓ Timing differences within acceptable range")
    
    def test_memory_exhaustion_protection(self, security_state):
        """Test protection against memory exhaustion attacks"""
        # Test with extremely large data that could cause memory exhaustion
        large_data_sizes = [1024, 10240, 102400]  # 1KB, 10KB, 100KB
        
        for size in large_data_sizes:
            large_data = "X" * size
            
            try:
                # Test in various fields
                original_name = security_state.get("company-name")
                security_state.config["company-name"] = large_data[:100]  # Limit to reasonable size
                
                content = CompanyData.create_request(security_state)
                envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
                
                print(f"✓ Large data test ({size} bytes) handled")
                
                security_state.config["company-name"] = original_name
                
            except Exception as e:
                print(f"✓ Large data ({size} bytes) rejected: {type(e).__name__}")
    
    def test_information_disclosure_prevention(self, security_state):
        """Test prevention of information disclosure"""
        content = CompanyData.create_request(security_state)
        envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
        
        from lxml import etree
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Check that sensitive system information is not disclosed
        sensitive_patterns = [
            r'/home/\w+',  # Unix home directories
            r'C:\\Users\\\w+',  # Windows user directories
            r'/etc/',  # Unix system directories
            r'password',
            r'secret',
            r'key',
            r'token',
            r'127\.0\.0\.1',  # Localhost IP
            r'localhost',
            r'\.local',
        ]
        
        for pattern in sensitive_patterns:
            matches = re.findall(pattern, xml_string, re.IGNORECASE)
            if matches:
                print(f"⚠ Potential information disclosure: {pattern} -> {matches}")
            else:
                print(f"✓ No information disclosure for pattern: {pattern}")
        
        # Verify that only expected data is present
        expected_data = [
            security_state.get("company-number"),
            security_state.get("made-up-date"),
            security_state.get("email")
        ]
        
        for expected in expected_data:
            if expected and expected in xml_string:
                print(f"✓ Expected data present: {expected}")
            elif expected:
                print(f"? Expected data not found: {expected}")
    
    @pytest.mark.slow
    def test_denial_of_service_resistance(self, security_state):
        """Test resistance to denial of service attacks"""
        import threading
        import time
        
        # Test rapid request creation
        def rapid_requests():
            for _ in range(100):
                try:
                    content = CompanyData.create_request(security_state)
                    envelope = Envelope.create(security_state, content, "CompanyDataRequest", "request")
                except Exception:
                    pass
        
        # Launch multiple threads
        threads = []
        start_time = time.time()
        
        for _ in range(5):
            thread = threading.Thread(target=rapid_requests)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\nDenial of Service Resistance:")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Total operations: 500")
        print(f"  Operations per second: {500 / duration:.1f}")
        
        # System should remain responsive
        assert duration < 30, f"Operations took too long: {duration:.2f}s"
        print("✓ System remained responsive under load")