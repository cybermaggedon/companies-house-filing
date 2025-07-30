import pytest
import json
import base64
from pathlib import Path

from ch_filing.test_server import MockServer
from ch_filing.client import Client, AuthenticationFailure, RequestFailure
from ch_filing.state import State
from ch_filing.envelope import Envelope
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus


class TestClientServerWorkflow:
    """Integration tests for complete client-server workflows"""
    
    @pytest.fixture
    def test_server(self):
        """Provide a test server for integration tests"""
        with MockServer(
            port=9304,  # Use fixed port for integration tests
            presenter_id="TEST_PRESENTER_INT",
            authentication="TEST_AUTH_INT",
            company_auth_code="INT1234"
        ) as server:
            yield server
    
    @pytest.fixture
    def test_config(self, test_server, tmp_path):
        """Create test configuration file"""
        config_file = tmp_path / "integration_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER_INT",
            "authentication": "TEST_AUTH_INT",
            "company-number": "12345678",
            "company-name": "INTEGRATION TEST COMPANY LIMITED",
            "company-authentication-code": "INT1234",
            "email": "integration@example.com",
            "company-type": "EW",
            "contact-name": "Test Integration User",
            "contact-number": "07900 555666",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "test-flag": "1",
            "package-reference": "INT0001",
            "url": test_server.get_url()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
            
        return str(config_file)
    
    @pytest.fixture
    def test_state(self, test_config, tmp_path):
        """Create test state"""
        state_file = tmp_path / "integration_state.json"
        return State(test_config, str(state_file))
    
    @pytest.fixture
    def test_client(self, test_state):
        """Create test client"""
        return Client(test_state)
    
    @pytest.fixture
    def sample_accounts_data(self, tmp_path):
        """Create sample iXBRL accounts data"""
        accounts_file = tmp_path / "integration_accounts.html"
        accounts_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head>
    <title>Integration Test Company Limited - Annual Accounts</title>
    <meta charset="utf-8"/>
</head>
<body>
    <div>
        <h1>Integration Test Company Limited</h1>
        <h2>Annual Accounts for the year ended 31 December 2023</h2>
        
        <div class="balance-sheet">
            <h3>Balance Sheet</h3>
            <table>
                <tr>
                    <td>Fixed Assets</td>
                    <td><ix:nonFraction name="uk-bus:FixedAssets" 
                        contextRef="period" unitRef="GBP" decimals="0">100000</ix:nonFraction></td>
                </tr>
                <tr>
                    <td>Current Assets</td>
                    <td><ix:nonFraction name="uk-bus:CurrentAssets" 
                        contextRef="period" unitRef="GBP" decimals="0">50000</ix:nonFraction></td>
                </tr>
                <tr>
                    <td>Total Assets</td>
                    <td><ix:nonFraction name="uk-bus:TotalAssets" 
                        contextRef="period" unitRef="GBP" decimals="0">150000</ix:nonFraction></td>
                </tr>
            </table>
        </div>
        
        <div class="profit-loss">
            <h3>Profit and Loss Account</h3>
            <table>
                <tr>
                    <td>Turnover</td>
                    <td><ix:nonFraction name="uk-bus:Turnover" 
                        contextRef="period" unitRef="GBP" decimals="0">250000</ix:nonFraction></td>
                </tr>
                <tr>
                    <td>Cost of Sales</td>
                    <td><ix:nonFraction name="uk-bus:CostSales" 
                        contextRef="period" unitRef="GBP" decimals="0">150000</ix:nonFraction></td>
                </tr>
                <tr>
                    <td>Gross Profit</td>
                    <td><ix:nonFraction name="uk-bus:GrossProfit" 
                        contextRef="period" unitRef="GBP" decimals="0">100000</ix:nonFraction></td>
                </tr>
            </table>
        </div>
        
        <!-- XBRL contexts and units -->
        <ix:resources>
            <ix:context id="period">
                <ix:entity>
                    <ix:identifier scheme="http://www.companieshouse.gov.uk/">12345678</ix:identifier>
                </ix:entity>
                <ix:period>
                    <ix:startDate>2023-01-01</ix:startDate>
                    <ix:endDate>2023-12-31</ix:endDate>
                </ix:period>
            </ix:context>
            <ix:unit id="GBP">
                <ix:measure>iso4217:GBP</ix:measure>
            </ix:unit>
        </ix:resources>
    </div>
</body>
</html>"""
        
        accounts_file.write_text(accounts_content)
        return str(accounts_file), accounts_content
    
    def test_company_data_workflow(self, test_client, test_state, test_server):
        """Test complete company data retrieval workflow"""
        # Create CompanyDataRequest
        content = CompanyData.create_request(test_state)
        
        # Verify request structure before sending
        assert content.tag.endswith("CompanyDataRequest")
        assert str(content.CompanyNumber) == "12345678"
        assert str(content.CompanyAuthenticationCode) == "INT1234"
        assert str(content.MadeUpDate) == "2023-12-31"
        
        # Wrap in envelope
        envelope = Envelope.create(test_state, content, "CompanyDataRequest", "request")
        
        # Send request and get response
        response = test_client.call(test_state, envelope)
        
        # Verify response structure
        assert response.tag.endswith("GovTalkMessage")
        assert hasattr(response, 'Body')
        assert hasattr(response.Body, 'CompanyData')
        
        # Verify response content
        company_data = response.Body.CompanyData
        assert str(company_data.CompanyName) == "TEST COMPANY LIMITED"
        assert str(company_data.CompanyNumber) in ["12345678", "1234567"]  # Handle leading zero
        assert str(company_data.CompanyCategory) == "Private Limited Company"
        assert str(company_data.Jurisdiction) == "England/Wales"
        assert str(company_data.NextDueDate) == "2024-09-30"
        
        # Verify address structure
        address = company_data.RegisteredOfficeAddress
        assert str(address.Premise) == "123"
        assert str(address.Street) == "Test Street"
        assert str(address.PostTown) == "Test Town"
        assert str(address.Postcode) == "TE5 7ST"
        
        # Verify SIC codes
        sic_codes = [str(code) for code in company_data.SICCodes.SICCode]
        assert "62012" in sic_codes
        assert "62020" in sic_codes
    
    def test_accounts_submission_workflow(self, test_client, test_state, test_server, sample_accounts_data):
        """Test complete accounts submission workflow"""
        accounts_file, accounts_content = sample_accounts_data
        
        # Create accounts submission
        submission = Accounts.create_submission(test_state, accounts_file, accounts_content)
        
        # Verify submission structure
        assert submission.tag.endswith("FormSubmission")
        
        # Check FormHeader
        header = submission.FormHeader
        assert str(header.CompanyNumber) == "12345678"
        assert str(header.CompanyName) == "INTEGRATION TEST COMPANY LIMITED"
        assert str(header.CompanyType) == "EW"
        assert str(header.FormIdentifier) == "Accounts"
        assert str(header.ContactName) == "Test Integration User"
        assert str(header.ContactNumber) == "07900 555666"
        
        # Check Document
        doc = submission.Document
        submission_id = str(header.SubmissionNumber)
        
        # Verify base64 encoding of accounts data
        encoded_data = str(doc.Data)
        decoded_data = base64.b64decode(encoded_data).decode('utf-8')
        assert "Integration Test Company Limited" in decoded_data
        assert "150000" in decoded_data  # Total Assets
        
        # Wrap in envelope
        envelope = Envelope.create(test_state, submission, "Accounts", "request")
        
        # Send submission
        response = test_client.call(test_state, envelope)
        
        # Verify submission was accepted
        assert response.tag.endswith("GovTalkMessage")
        
        # Check that submission was stored in test server
        stored_submission = test_server.data.get_submission(submission_id)
        assert stored_submission is not None
        assert stored_submission["status"] == "accepted"
        assert stored_submission["company_number"] == "12345678"
        
        # Store submission_id for other tests to use
        self._last_submission_id = submission_id
    
    def test_submission_status_workflow(self, test_client, test_state, test_server, sample_accounts_data):
        """Test submission status checking workflow"""
        # First submit accounts to have something to check
        self.test_accounts_submission_workflow(
            test_client, test_state, test_server, sample_accounts_data
        )
        submission_id = self._last_submission_id
        
        # Create status request for specific submission
        status_request = SubmissionStatus.create_request(test_state, submission_id)
        
        # Verify request structure
        assert status_request.tag.endswith("GetSubmissionStatus")
        assert str(status_request.SubmissionNumber) == submission_id
        assert str(status_request.PresenterID) == "TEST_PRESENTER_INT"
        
        # Wrap in envelope
        envelope = Envelope.create(test_state, status_request, "GetSubmissionStatus", "request")
        
        # Send request
        response = test_client.call(test_state, envelope)
        
        # Verify response
        assert response.tag.endswith("GovTalkMessage")
        assert hasattr(response.Body, 'SubmissionStatus')
        
        # Check status details
        status_list = response.Body.SubmissionStatus.Status
        found_submission = False
        
        for status in status_list:
            if str(status.SubmissionNumber) == submission_id:
                assert str(status.StatusCode) == "accepted"
                found_submission = True
                break
        
        assert found_submission, f"Submission {submission_id} not found in status response"
    
    def test_get_all_submissions_status(self, test_client, test_state, test_server, sample_accounts_data):
        """Test getting status of all submissions"""
        # Submit multiple accounts to have multiple submissions
        self.test_accounts_submission_workflow(
            test_client, test_state, test_server, sample_accounts_data
        )
        submission_id1 = self._last_submission_id
        
        # Submit another one by creating a new submission
        accounts_file, accounts_content = sample_accounts_data
        submission2 = Accounts.create_submission(test_state, accounts_file, accounts_content)
        envelope2 = Envelope.create(test_state, submission2, "Accounts", "request")
        test_client.call(test_state, envelope2)
        submission_id2 = str(submission2.FormHeader.SubmissionNumber)
        
        # Create status request without specific submission ID
        status_request = SubmissionStatus.create_request(test_state)
        
        # Verify request structure
        assert status_request.tag.endswith("GetSubmissionStatus")
        assert str(status_request.PresenterID) == "TEST_PRESENTER_INT"
        
        # Should not have SubmissionNumber
        try:
            _ = status_request.SubmissionNumber
            pytest.fail("SubmissionNumber should not exist for all-submissions request")
        except AttributeError:
            pass  # Expected
        
        # Wrap in envelope
        envelope = Envelope.create(test_state, status_request, "GetSubmissionStatus", "request")
        
        # Send request
        response = test_client.call(test_state, envelope)
        
        # Verify response contains multiple submissions
        status_list = response.Body.SubmissionStatus.Status
        submission_ids = [str(status.SubmissionNumber) for status in status_list]
        
        assert submission_id1 in submission_ids
        assert submission_id2 in submission_ids
        assert len(submission_ids) >= 2
    
    def test_authentication_failure(self, test_server, tmp_path):
        """Test authentication failure handling"""
        # Create config with wrong authentication
        config_file = tmp_path / "bad_auth_config.json"
        config_data = {
            "presenter-id": "WRONG_PRESENTER",
            "authentication": "WRONG_AUTH",
            "company-number": "12345678",
            "company-authentication-code": "INT1234",
            "email": "test@example.com",
            "made-up-date": "2023-12-31",
            "test-flag": "1",
            "url": test_server.get_url()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "bad_auth_state.json"
        bad_state = State(str(config_file), str(state_file))
        bad_client = Client(bad_state)
        
        # Try to make a request
        content = CompanyData.create_request(bad_state)
        envelope = Envelope.create(bad_state, content, "CompanyDataRequest", "request")
        
        # Should raise AuthenticationFailure
        with pytest.raises(AuthenticationFailure):
            bad_client.call(bad_state, envelope)
    
    def test_company_auth_code_failure(self, test_server, tmp_path):
        """Test company authentication code failure"""
        # Create config with wrong company auth code
        config_file = tmp_path / "bad_company_auth_config.json"
        config_data = {
            "presenter-id": "TEST_PRESENTER_INT",
            "authentication": "TEST_AUTH_INT",
            "company-number": "12345678",
            "company-authentication-code": "WRONG_CODE",
            "email": "test@example.com",
            "made-up-date": "2023-12-31",
            "test-flag": "1",
            "url": test_server.get_url()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        state_file = tmp_path / "bad_company_auth_state.json"
        bad_state = State(str(config_file), str(state_file))
        bad_client = Client(bad_state)
        
        # Try to make a company data request
        content = CompanyData.create_request(bad_state)
        envelope = Envelope.create(bad_state, content, "CompanyDataRequest", "request")
        
        # Should raise AuthenticationFailure for invalid company auth code
        with pytest.raises(AuthenticationFailure):
            bad_client.call(bad_state, envelope)
    
    def test_server_delay_handling(self, tmp_path):
        """Test that client handles server delays correctly"""
        # Create server with delay
        with MockServer(
            port=9305,
            presenter_id="TEST_PRESENTER_DELAY",
            authentication="TEST_AUTH_DELAY",
            company_auth_code="DELAY1234",
            delay=0.1  # 100ms delay
        ) as delayed_server:
            
            # Create config
            config_file = tmp_path / "delay_config.json"
            config_data = {
                "presenter-id": "TEST_PRESENTER_DELAY",
                "authentication": "TEST_AUTH_DELAY",
                "company-number": "12345678",
                "company-authentication-code": "DELAY1234",
                "email": "test@example.com",
                "made-up-date": "2023-12-31",
                "test-flag": "1",
                "url": delayed_server.get_url()
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
                
            state_file = tmp_path / "delay_state.json"
            delay_state = State(str(config_file), str(state_file))
            delay_client = Client(delay_state)
            
            # Make request and measure time
            import time
            start_time = time.time()
            
            content = CompanyData.create_request(delay_state)
            envelope = Envelope.create(delay_state, content, "CompanyDataRequest", "request")
            response = delay_client.call(delay_state, envelope)
            
            elapsed_time = time.time() - start_time
            
            # Should have taken at least the delay time
            assert elapsed_time >= 0.1
            
            # Should still get valid response
            assert response.tag.endswith("GovTalkMessage")
            assert hasattr(response.Body, 'CompanyData')
    
    def test_transaction_id_persistence(self, test_client, test_state, test_server):
        """Test that transaction IDs persist and increment across requests"""
        # Make first request
        content1 = CompanyData.create_request(test_state)
        envelope1 = Envelope.create(test_state, content1, "CompanyDataRequest", "request")
        response1 = test_client.call(test_state, envelope1)
        
        tx_id1 = int(str(envelope1.Header.MessageDetails.TransactionID))
        
        # Make second request
        content2 = CompanyData.create_request(test_state)
        envelope2 = Envelope.create(test_state, content2, "CompanyDataRequest", "request")
        response2 = test_client.call(test_state, envelope2)
        
        tx_id2 = int(str(envelope2.Header.MessageDetails.TransactionID))
        
        # Transaction IDs should increment
        assert tx_id2 == tx_id1 + 1
        
        # Both responses should be valid
        assert hasattr(response1.Body, 'CompanyData')
        assert hasattr(response2.Body, 'CompanyData')