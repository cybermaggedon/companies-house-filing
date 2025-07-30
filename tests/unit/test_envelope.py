import hashlib
import pytest
from lxml import etree, objectify

from ch_filing.envelope import Envelope
from ch_filing.state import State


class TestEnvelope:
    """Test the Envelope class for creating GovTalk message envelopes"""
    
    @pytest.fixture
    def test_state(self, tmp_path):
        """Create a test state with known configuration"""
        config_file = tmp_path / "test_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER",
            "authentication": "TEST_AUTH",
            "company-number": "12345678",
            "email": "test@example.com",
            "test-flag": "1"
        }
        
        # Write config as JSON
        import json
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "test_state.json"
        return State(str(config_file), str(state_file))
    
    @pytest.fixture
    def simple_content(self):
        """Create simple XML content for testing"""
        maker = objectify.ElementMaker(annotate=False)
        return maker.TestContent(
            maker.Field1("value1"),
            maker.Field2("value2")
        )
    
    def test_envelope_structure(self, test_state, simple_content):
        """Test that envelope creates correct XML structure"""
        envelope = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        # Check root element
        assert envelope.tag.endswith("GovTalkMessage")
        
        # Check envelope version
        assert str(envelope.EnvelopeVersion) == "1.0"
        
        # Check header structure
        assert hasattr(envelope, 'Header')
        assert hasattr(envelope.Header, 'MessageDetails')
        assert hasattr(envelope.Header, 'SenderDetails')
        
        # Check message details
        msg_details = envelope.Header.MessageDetails
        assert str(msg_details.Class) == "TestClass"
        assert str(msg_details.Qualifier) == "request"
        assert str(msg_details.GatewayTest) == "1"
        
        # Check transaction ID is numeric
        tx_id = str(msg_details.TransactionID)
        assert tx_id.isdigit()
        assert int(tx_id) > 0
    
    def test_authentication_hashing(self, test_state, simple_content):
        """Test that authentication values are correctly MD5 hashed"""
        envelope = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        sender_details = envelope.Header.SenderDetails.IDAuthentication
        
        # Calculate expected hashes
        expected_presenter_hash = hashlib.md5(b"TEST_PRESENTER").hexdigest()
        expected_auth_hash = hashlib.md5(b"TEST_AUTH").hexdigest()
        
        # Check hashes match
        assert str(sender_details.SenderID) == expected_presenter_hash
        assert str(sender_details.Authentication.Value) == expected_auth_hash
        assert str(sender_details.Authentication.Method) == "clear"
    
    def test_body_content_included(self, test_state, simple_content):
        """Test that the provided content is included in the body"""
        envelope = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        # Check body contains our content
        assert hasattr(envelope, 'Body')
        body_content = envelope.Body.getchildren()[0]
        
        # Check the content structure
        assert body_content.tag.endswith("TestContent")
        assert str(body_content.Field1) == "value1"
        assert str(body_content.Field2) == "value2"
    
    def test_namespace_handling(self, test_state, simple_content):
        """Test that namespaces are correctly set"""
        envelope = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        # Convert to string to check namespace declarations
        xml_string = etree.tostring(envelope, encoding='unicode')
        
        # Check that envelope namespace is declared
        assert 'xmlns="http://www.govtalk.gov.uk/CM/envelope"' in xml_string
        
        # Check schema location is set
        assert 'schemaLocation' in xml_string
        assert 'http://xmlgw.companieshouse.gov.uk/v2-1/schema/Egov_ch-v2-0.xsd' in xml_string
    
    def test_transaction_id_increment(self, test_state, simple_content):
        """Test that transaction ID increments with each call"""
        envelope1 = Envelope.create(test_state, simple_content, "TestClass", "request")
        envelope2 = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        tx_id1 = int(str(envelope1.Header.MessageDetails.TransactionID))
        tx_id2 = int(str(envelope2.Header.MessageDetails.TransactionID))
        
        assert tx_id2 == tx_id1 + 1
    
    def test_email_included(self, test_state, simple_content):
        """Test that email address is included in sender details"""
        envelope = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        email = str(envelope.Header.SenderDetails.EmailAddress)
        assert email == "test@example.com"
    
    def test_govtalk_details_structure(self, test_state, simple_content):
        """Test that GovTalkDetails has correct structure"""
        envelope = Envelope.create(test_state, simple_content, "TestClass", "request")
        
        # Check GovTalkDetails exists and has Keys element
        assert hasattr(envelope, 'GovTalkDetails')
        assert hasattr(envelope.GovTalkDetails, 'Keys')