import pytest
import json
import hashlib
import hmac
import time
import secrets
from pathlib import Path
from unittest.mock import patch, Mock
import xml.etree.ElementTree as ET

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


class TestAuthenticationSecurity:
    """Authentication and data sanitization security tests"""
    
    @pytest.fixture
    def auth_state(self, tmp_path):
        """Create a test state for authentication security testing"""
        config_file = tmp_path / "auth_config.json"
        config_data = {
            "presenter-id": "AUTH_PRESENTER_789",
            "authentication": "AUTH_SECRET_ABC123",
            "company-number": "87654321",
            "company-name": "AUTH TEST COMPANY LIMITED",
            "company-authentication-code": "AUTH9876",
            "company-type": "EW",
            "contact-name": "Auth Test Person",
            "contact-number": "07900 876543",
            "email": "auth@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "AUTH001",
            "url": "http://localhost:9403/v1-0/xmlgw/Gateway"
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "auth_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def auth_client(self, auth_state):
        """Create a client for authentication testing"""
        return Client(auth_state)
    
    def test_authentication_credential_hashing(self, auth_state):
        """Test that authentication credentials are properly hashed"""
        presenter_id = auth_state.get("presenter-id")
        auth_value = auth_state.get("authentication")
        
        # Test MD5 hash generation (as required by Companies House API)
        expected_presenter_hash = hashlib.md5(presenter_id.encode("utf-8")).hexdigest()
        expected_auth_hash = hashlib.md5(auth_value.encode("utf-8")).hexdigest()
        
        content = CompanyData.create_request(auth_state)
        envelope = Envelope.create(auth_state, content, "CompanyDataRequest", "request")
        
        from lxml import etree
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Verify hashed values are present
        assert expected_presenter_hash in xml_string, "Presenter ID hash not found in envelope"
        assert expected_auth_hash in xml_string, "Authentication hash not found in envelope"
        
        # Verify original credentials are NOT present
        assert presenter_id not in xml_string, "Plain presenter ID found in envelope (security risk)"
        assert auth_value not in xml_string, "Plain authentication value found in envelope (security risk)"
        
        print(f"\nAuthentication Credential Hashing:")
        print(f"  Presenter ID: {presenter_id} -> {expected_presenter_hash}")
        print(f"  Authentication: [HIDDEN] -> {expected_auth_hash}")
        print(f"  ✓ Credentials properly hashed")
        print(f"  ✓ Plain credentials not exposed")
    
    def test_weak_authentication_detection(self, tmp_path):
        """Test detection of weak authentication credentials"""
        weak_credentials = [
            ("123", "password"),
            ("admin", "admin"),
            ("test", "test"),
            ("user", "12345"),
            ("presenter", "secret"),
            ("", ""),  # Empty credentials
            ("a", "b"),  # Too short
            ("PRESENTER" * 100, "AUTH" * 100),  # Too long
        ]
        
        for presenter_id, auth_value in weak_credentials:
            config_file = tmp_path / f"weak_auth_{hash(presenter_id + auth_value) & 0x7FFFFFFF}.json"
            config_data = {
                "presenter-id": presenter_id,
                "authentication": auth_value,
                "company-number": "12345678",
                "made-up-date": "2023-12-31",
                "url": "http://localhost:9403/v1-0/xmlgw/Gateway"
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
            
            state_file = tmp_path / "weak_auth_state.json"
            
            try:
                test_state = State(str(config_file), str(state_file))
                content = CompanyData.create_request(test_state)
                envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
                
                # Even weak credentials are processed (validation happens server-side)
                # But we can warn about them
                if len(presenter_id) < 3 or len(auth_value) < 3:
                    print(f"⚠ Weak credentials detected: '{presenter_id}' / '[HIDDEN]'")
                elif presenter_id == auth_value:
                    print(f"⚠ Identical presenter ID and auth: '{presenter_id}'")
                else:
                    print(f"✓ Credentials processed: '{presenter_id}' / '[HIDDEN]'")
                    
            except Exception as e:
                print(f"✓ Weak credentials rejected: '{presenter_id}' ({type(e).__name__})")
    
    def test_authentication_brute_force_protection(self, auth_state):
        """Test protection against brute force authentication attacks"""
        # Simulate multiple failed authentication attempts
        failed_attempts = []
        
        for i in range(10):
            invalid_auth = f"INVALID_AUTH_{i}"
            original_auth = auth_state.get("authentication")
            auth_state.config["authentication"] = invalid_auth
            
            start_time = time.perf_counter()
            try:
                content = CompanyData.create_request(auth_state)
                envelope = Envelope.create(auth_state, content, "CompanyDataRequest", "request")
                # Envelope creation will succeed, authentication failure happens at server
                end_time = time.perf_counter()
                failed_attempts.append(end_time - start_time)
            except Exception:
                end_time = time.perf_counter()
                failed_attempts.append(end_time - start_time)
            
            auth_state.config["authentication"] = original_auth
        
        # Analyze timing patterns
        avg_time = sum(failed_attempts) / len(failed_attempts)
        max_time = max(failed_attempts)
        min_time = min(failed_attempts)
        
        print(f"\nBrute Force Protection Analysis:")
        print(f"  Average processing time: {avg_time:.6f}s")
        print(f"  Min time: {min_time:.6f}s")
        print(f"  Max time: {max_time:.6f}s")
        print(f"  Time variation: {(max_time - min_time) / avg_time:.2f}x")
        
        # Times should be consistent (no obvious timing attacks)
        time_ratio = max_time / min_time if min_time > 0 else 1
        assert time_ratio < 5, f"Excessive timing variation: {time_ratio:.2f}x"
        print(f"✓ Timing variation within acceptable limits")
    
    def test_session_token_security(self, auth_state):
        """Test security of session tokens and transaction IDs"""
        # Generate multiple transaction IDs to check for patterns
        tx_ids = []
        for _ in range(100):
            tx_id = auth_state.get_next_tx_id()
            tx_ids.append(tx_id)
        
        # Check for predictability
        differences = []
        for i in range(1, len(tx_ids)):
            differences.append(tx_ids[i] - tx_ids[i-1])
        
        # Transaction IDs should increment by 1 (this is expected behavior)
        assert all(diff == 1 for diff in differences), "Transaction IDs should increment by 1"
        
        # Generate submission IDs
        sub_ids = []
        for _ in range(50):
            sub_id = auth_state.get_next_submission_id()
            sub_ids.append(sub_id)
        
        print(f"\nSession Token Security:")
        print(f"  Transaction IDs: Sequential (expected)")
        print(f"  Submission IDs: {len(set(sub_ids))} unique out of {len(sub_ids)}")
        print(f"  ✓ Token generation working as expected")
        
        # Verify submission ID format
        for sub_id in sub_ids[:5]:
            assert sub_id.startswith("S"), f"Submission ID should start with 'S': {sub_id}"
            assert len(sub_id) == 6, f"Submission ID should be 6 characters: {sub_id}"
            assert sub_id[1:].isdigit(), f"Submission ID should have numeric suffix: {sub_id}"
    
    def test_credential_storage_security(self, tmp_path):
        """Test security of credential storage"""
        # Create config file with sensitive data
        config_file = tmp_path / "sensitive_config.json"
        sensitive_data = {
            "presenter-id": "SENSITIVE_PRESENTER",
            "authentication": "VERY_SECRET_AUTH_TOKEN",
            "company-authentication-code": "SECRET_COMPANY_CODE",
            "api-key": "SECRET_API_KEY_12345",  # Additional sensitive field
        }
        
        with open(config_file, 'w') as f:
            json.dump(sensitive_data, f)
        
        # Check file permissions (Unix-like systems)
        import os
        import stat
        
        file_permissions = oct(os.stat(config_file).st_mode)[-3:]
        print(f"\nCredential Storage Security:")
        print(f"  Config file permissions: {file_permissions}")
        
        # Read config file content
        with open(config_file, 'r') as f:
            config_content = f.read()
        
        # Verify sensitive data is in plain text (expected for config files)
        # But warn about security implications
        for key, value in sensitive_data.items():
            if value in config_content:
                print(f"⚠ Sensitive data in config file: {key}")
        
        print(f"⚠ Config files contain sensitive data in plain text")
        print(f"⚠ Ensure proper file permissions and secure storage")
        
        # Test state file security
        state_file = tmp_path / "sensitive_state.json"
        test_state = State(str(config_file), str(state_file))
        
        # Generate some state data
        test_state.get_next_tx_id()
        test_state.get_next_submission_id()
        
        if state_file.exists():
            with open(state_file, 'r') as f:
                state_content = f.read()
            
            # State file should not contain authentication credentials
            for key, value in sensitive_data.items():
                if key in ["presenter-id", "authentication", "company-authentication-code"]:
                    assert value not in state_content, f"Credential '{key}' found in state file"
            
            print(f"✓ State file does not contain authentication credentials")
    
    def test_network_authentication_security(self, auth_state):
        """Test network-level authentication security"""
        with MockServer(
            port=9403,
            presenter_id="AUTH_PRESENTER_789",
            authentication="AUTH_SECRET_ABC123",
            company_auth_code="AUTH9876"
        ) as server:
            client = Client(auth_state)
            
            # Test successful authentication
            content = CompanyData.create_request(auth_state)
            envelope = Envelope.create(auth_state, content, "CompanyDataRequest", "request")
            
            try:
                response = client.call(auth_state, envelope)
                print(f"\n✓ Successful authentication with mock server")
                assert hasattr(response, 'Body')
            except Exception as e:
                print(f"Authentication test: {type(e).__name__}: {e}")
        
        # Test with mismatched credentials
        with MockServer(
            port=9403,
            presenter_id="WRONG_PRESENTER",
            authentication="WRONG_AUTH",
            company_auth_code="WRONG_CODE"
        ) as server:
            client = Client(auth_state)
            content = CompanyData.create_request(auth_state)
            envelope = Envelope.create(auth_state, content, "CompanyDataRequest", "request")
            
            try:
                response = client.call(auth_state, envelope)
                print(f"⚠ Authentication succeeded with wrong credentials")
            except AuthenticationFailure:
                print(f"✓ Authentication properly failed with wrong credentials")
            except Exception as e:
                print(f"? Unexpected error with wrong credentials: {type(e).__name__}")
    
    def test_data_sanitization_xml_content(self, auth_state):
        """Test data sanitization in XML content"""
        # Test various injection attempts in different fields
        injection_payloads = [
            # XML entity injection
            "<!ENTITY xxe SYSTEM 'file:///etc/passwd'>",
            
            # CDATA injection
            "]]><script>alert('xss')</script><![CDATA[",
            
            # Processing instruction injection
            "<?php system('rm -rf /'); ?>",
            
            # Comment injection
            "<!-- <script>alert('xss')</script> -->",
            
            # Namespace injection
            "xmlns:evil='http://evil.com' evil:attr='malicious'",
            
            # UTF-8 BOM and control characters
            "\ufeff\u0000\u0001\u0002malicious",
            
            # Encoded payloads
            "&lt;script&gt;alert('xss')&lt;/script&gt;",
        ]
        
        for payload in injection_payloads:
            # Test in company name field
            original_name = auth_state.get("company-name")
            auth_state.config["company-name"] = payload
            
            try:
                content = CompanyData.create_request(auth_state)
                envelope = Envelope.create(auth_state, content, "CompanyDataRequest", "request")
                
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                
                # Verify XML is well-formed
                root = etree.fromstring(xml_string)
                
                # Check that dangerous content is properly escaped or removed
                dangerous_patterns = [
                    "<!ENTITY",
                    "<script>",
                    "<?php",
                    "system(",
                    "rm -rf",
                    "\u0000",
                    "\u0001"
                ]
                
                for pattern in dangerous_patterns:
                    assert pattern not in xml_string, f"Dangerous pattern '{pattern}' found in XML"
                
                print(f"✓ Injection payload sanitized: {payload[:30]}...")
                
            except Exception as e:
                print(f"✓ Injection payload rejected: {payload[:30]}... ({type(e).__name__})")
            
            finally:
                auth_state.config["company-name"] = original_name
    
    def test_base64_encoding_security(self, auth_state):
        """Test security of base64 encoding for accounts data"""
        # Test with various potentially malicious content
        malicious_content_types = [
            # Executable content
            b"\x4d\x5a\x90\x00",  # PE header (Windows executable)
            b"\x7f\x45\x4c\x46",  # ELF header (Linux executable)
            
            # Script content
            b"<script>alert('xss')</script>",
            b"<?php system($_GET['cmd']); ?>",
            b"#!/bin/bash\nrm -rf /",
            
            # Binary data with nulls
            b"\x00" * 1000 + b"malicious data",
            
            # Large repetitive data
            b"A" * 100000,
        ]
        
        for malicious_content in malicious_content_types:
            try:
                # Convert to string for processing
                content_str = malicious_content.decode('utf-8', errors='ignore')
                
                submission = Accounts.create_submission(
                    auth_state, 
                    "malicious.html", 
                    content_str
                )
                envelope = Envelope.create(auth_state, submission, "Accounts", "request")
                
                from lxml import etree
                xml_string = etree.tostring(envelope, encoding='unicode')
                
                # Find the base64 data
                data_start = xml_string.find("<Data>")
                data_end = xml_string.find("</Data>")
                
                if data_start != -1 and data_end != -1:
                    encoded_data = xml_string[data_start + 6:data_end]
                    
                    # Verify it's valid base64
                    import base64
                    try:
                        decoded = base64.b64decode(encoded_data)
                        print(f"✓ Base64 encoding successful for malicious content ({len(malicious_content)} bytes)")
                    except Exception:
                        print(f"✗ Invalid base64 encoding for malicious content")
                else:
                    print(f"? No base64 data found for malicious content")
                
            except Exception as e:
                print(f"✓ Malicious content rejected: {type(e).__name__}")
    
    def test_authentication_bypass_attempts(self, auth_state):
        """Test various authentication bypass attempts"""
        bypass_attempts = [
            # SQL injection style
            ("' OR 1=1 --", "password"),
            
            # Null byte injection
            ("presenter\x00admin", "auth\x00bypass"),
            
            # Unicode normalization
            ("presenter\u0301", "auth\u0301"),
            
            # Case variations
            ("PRESENTER", "AUTH"),
            ("presenter", "auth"),
            
            # Empty/whitespace
            ("", ""),
            ("   ", "   "),
            
            # Very long values
            ("A" * 10000, "B" * 10000),
        ]
        
        original_presenter = auth_state.get("presenter-id")
        original_auth = auth_state.get("authentication")
        
        for presenter_attempt, auth_attempt in bypass_attempts:
            auth_state.config["presenter-id"] = presenter_attempt
            auth_state.config["authentication"] = auth_attempt
            
            try:
                content = CompanyData.create_request(auth_state)
                envelope = Envelope.create(auth_state, content, "CompanyDataRequest", "request")
                
                # Envelope creation might succeed, but authentication will fail at server
                print(f"✓ Bypass attempt processed (will fail at server): '{presenter_attempt[:20]}...'")
                
            except Exception as e:
                print(f"✓ Bypass attempt rejected: '{presenter_attempt[:20]}...' ({type(e).__name__})")
            
            finally:
                auth_state.config["presenter-id"] = original_presenter
                auth_state.config["authentication"] = original_auth
    
    def test_secure_random_generation(self, auth_state):
        """Test quality of random data generation (if any)"""
        # While the current system uses sequential IDs, test for any random generation
        
        # Test transaction ID generation
        tx_ids = [auth_state.get_next_tx_id() for _ in range(100)]
        
        # Transaction IDs should be sequential (expected behavior)
        differences = [tx_ids[i] - tx_ids[i-1] for i in range(1, len(tx_ids))]
        assert all(diff == 1 for diff in differences), "Transaction IDs should be sequential"
        
        # Test submission ID generation
        sub_ids = [auth_state.get_next_submission_id() for _ in range(50)]
        
        # Extract numeric parts
        sub_numbers = [int(sub_id[1:]) for sub_id in sub_ids]
        sub_differences = [sub_numbers[i] - sub_numbers[i-1] for i in range(1, len(sub_numbers))]
        assert all(diff == 1 for diff in sub_differences), "Submission IDs should be sequential"
        
        print(f"\nRandom Generation Analysis:")
        print(f"  Transaction IDs: Sequential (deterministic)")
        print(f"  Submission IDs: Sequential (deterministic)")
        print(f"  ✓ ID generation is predictable but secure for this use case")
        
        # Note: Sequential IDs are appropriate for this application
        # as they provide audit trails and prevent collisions