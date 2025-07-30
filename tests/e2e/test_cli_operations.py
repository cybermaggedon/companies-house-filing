import pytest
import subprocess
import json
import re
from pathlib import Path

from ch_filing.test_server import MockServer


class TestCLIOperations:
    """End-to-end tests for CLI operations using actual ch-filing command"""
    
    @pytest.fixture
    def mock_server(self):
        """Start mock server for e2e tests"""
        with MockServer(
            port=9306,  # Different port for e2e tests
            presenter_id="E2E_PRESENTER",
            authentication="E2E_AUTH",
            company_auth_code="E2E1234"
        ) as server:
            yield server
    
    @pytest.fixture
    def test_config_file(self, mock_server, tmp_path):
        """Create test configuration file for CLI"""
        config_file = tmp_path / "e2e_config.json"
        config_data = {
            "presenter-id": "E2E_PRESENTER",
            "authentication": "E2E_AUTH",
            "company-number": "12345678",
            "company-name": "E2E TEST COMPANY LIMITED",
            "company-authentication-code": "E2E1234",
            "email": "e2e@example.com",
            "company-type": "EW",
            "contact-name": "E2E Test User",
            "contact-number": "07900 777888",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "test-flag": "1",
            "package-reference": "E2E001",
            "url": mock_server.get_url()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
            
        return str(config_file)
    
    @pytest.fixture
    def test_state_file(self, tmp_path):
        """Create test state file path"""
        return str(tmp_path / "e2e_state.json")
    
    @pytest.fixture
    def test_accounts_file(self, tmp_path):
        """Create test accounts file for CLI"""
        accounts_file = tmp_path / "e2e_accounts.html"
        accounts_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head>
    <title>E2E Test Company Limited - Annual Accounts</title>
    <meta charset="utf-8"/>
</head>
<body>
    <div>
        <h1>E2E Test Company Limited</h1>
        <h2>Annual Accounts for the year ended 31 December 2023</h2>
        
        <div class="company-info">
            <p>Company Number: <ix:nonNumeric name="uk-bus:EntityCurrentLegalOrRegisteredName" 
               contextRef="period">12345678</ix:nonNumeric></p>
            <p>Company Name: <ix:nonNumeric name="uk-bus:EntityCurrentLegalOrRegisteredName" 
               contextRef="period">E2E Test Company Limited</ix:nonNumeric></p>
        </div>
        
        <div class="balance-sheet">
            <h3>Balance Sheet as at 31 December 2023</h3>
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Amount (£)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Fixed Assets</td>
                        <td><ix:nonFraction name="uk-bus:FixedAssets" 
                            contextRef="period" unitRef="GBP" decimals="0">75000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td>Current Assets</td>
                        <td><ix:nonFraction name="uk-bus:CurrentAssets" 
                            contextRef="period" unitRef="GBP" decimals="0">25000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td><strong>Total Assets</strong></td>
                        <td><strong><ix:nonFraction name="uk-bus:TotalAssets" 
                            contextRef="period" unitRef="GBP" decimals="0">100000</ix:nonFraction></strong></td>
                    </tr>
                    <tr>
                        <td>Current Liabilities</td>
                        <td><ix:nonFraction name="uk-bus:CurrentLiabilities" 
                            contextRef="period" unitRef="GBP" decimals="0">20000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td><strong>Net Assets</strong></td>
                        <td><strong><ix:nonFraction name="uk-bus:NetAssetsLiabilities" 
                            contextRef="period" unitRef="GBP" decimals="0">80000</ix:nonFraction></strong></td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <div class="profit-loss">
            <h3>Profit and Loss Account for the year ended 31 December 2023</h3>
            <table>
                <thead>
                    <tr>
                        <th>Item</th>
                        <th>Amount (£)</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Turnover</td>
                        <td><ix:nonFraction name="uk-bus:Turnover" 
                            contextRef="period" unitRef="GBP" decimals="0">200000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td>Cost of Sales</td>
                        <td><ix:nonFraction name="uk-bus:CostSales" 
                            contextRef="period" unitRef="GBP" decimals="0">120000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td>Gross Profit</td>
                        <td><ix:nonFraction name="uk-bus:GrossProfit" 
                            contextRef="period" unitRef="GBP" decimals="0">80000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td>Administrative Expenses</td>
                        <td><ix:nonFraction name="uk-bus:AdministrativeExpenses" 
                            contextRef="period" unitRef="GBP" decimals="0">60000</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td><strong>Operating Profit</strong></td>
                        <td><strong><ix:nonFraction name="uk-bus:OperatingProfitLoss" 
                            contextRef="period" unitRef="GBP" decimals="0">20000</ix:nonFraction></strong></td>
                    </tr>
                    <tr>
                        <td>Tax on Profit</td>
                        <td><ix:nonFraction name="uk-bus:TaxOnProfitOrLossOnOrdinaryActivities" 
                            contextRef="period" unitRef="GBP" decimals="0">3800</ix:nonFraction></td>
                    </tr>
                    <tr>
                        <td><strong>Profit for Financial Year</strong></td>
                        <td><strong><ix:nonFraction name="uk-bus:ProfitLossForPeriod" 
                            contextRef="period" unitRef="GBP" decimals="0">16200</ix:nonFraction></strong></td>
                    </tr>
                </tbody>
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
        return str(accounts_file)
    
    def run_cli_command(self, *args):
        """Run ch-filing CLI command and return result"""
        cmd = ["ch-filing"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        return result
    
    def test_cli_help(self):
        """Test CLI help command"""
        result = self.run_cli_command("--help")
        
        assert result.returncode == 0
        assert "Submittion to HMRC Corporation Tax API" in result.stdout
        assert "--config" in result.stdout
        assert "--get-company-data" in result.stdout
        assert "--submit-accounts" in result.stdout
        assert "--get-submission-status" in result.stdout
    
    def test_company_data_cli_workflow(self, mock_server, test_config_file, test_state_file):
        """Test complete company data retrieval via CLI"""
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--get-company-data"
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Check output contains expected company information
        assert "Company: TEST COMPANY LIMITED" in result.stdout
        assert "Number: 12345678" in result.stdout or "Number: 1234567" in result.stdout
        assert "Category: Private Limited Company" in result.stdout
        assert "Jurisdiction: England/Wales" in result.stdout
        assert "Next due date: 2024-09-30" in result.stdout
        
        # Check address information
        assert "Registered Office:" in result.stdout
        assert "Premise: 123" in result.stdout
        assert "Street: Test Street" in result.stdout
        assert "Post town: Test Town" in result.stdout
        assert "Postcode: TE5 7ST" in result.stdout
        
        # Check SIC codes
        assert "SIC codes:" in result.stdout
        assert "62012" in result.stdout
        assert "62020" in result.stdout
    
    def test_accounts_submission_cli_workflow(self, mock_server, test_config_file, test_state_file, test_accounts_file):
        """Test complete accounts submission via CLI"""
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--accounts", test_accounts_file,
            "--submit-accounts"
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Check successful submission output
        assert "Submission completed." in result.stdout
        assert "Submission ID is:" in result.stdout
        
        # Extract submission ID for verification
        submission_id_match = re.search(r"Submission ID is: (S\d+)", result.stdout)
        assert submission_id_match, "Could not find submission ID in output"
        submission_id = submission_id_match.group(1)
        
        # Verify submission was stored in mock server
        stored_submission = mock_server.data.get_submission(submission_id)
        assert stored_submission is not None
        assert stored_submission["status"] == "accepted"
        assert stored_submission["company_number"] == "12345678"
        
        # Store submission_id for use by other tests  
        self._last_submission_id = submission_id
    
    def test_submission_status_cli_workflow(self, mock_server, test_config_file, test_state_file, test_accounts_file):
        """Test submission status checking via CLI"""
        # First submit accounts to have something to check status for
        self.test_accounts_submission_cli_workflow(
            mock_server, test_config_file, test_state_file, test_accounts_file
        )
        submission_id = self._last_submission_id
        
        # Check status of specific submission
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--submission-id", submission_id,
            "--get-submission-status"
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert f"{submission_id}: accepted" in result.stdout
    
    def test_get_all_submissions_status_cli(self, mock_server, test_config_file, test_state_file, test_accounts_file):
        """Test getting status of all submissions via CLI"""
        # Submit accounts to have submissions to check
        self.test_accounts_submission_cli_workflow(
            mock_server, test_config_file, test_state_file, test_accounts_file
        )
        submission_id = self._last_submission_id
        
        # Get all submission statuses
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--get-submission-status"  # No specific submission ID
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert f"{submission_id}: accepted" in result.stdout
    
    def test_accounts_image_cli_workflow(self, mock_server, test_config_file, test_state_file, test_accounts_file):
        """Test accounts image generation via CLI"""
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--accounts", test_accounts_file,
            "--accounts-image"
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        
        # Check that some response was received (accounts image may be minimal output)
        # Just verify no error occurred
        assert "Exception:" not in result.stdout
    
    def test_cli_missing_config_file(self, tmp_path):
        """Test CLI behavior with missing config file"""
        missing_config = str(tmp_path / "missing_config.json")
        
        result = self.run_cli_command(
            "--config", missing_config,
            "--get-company-data"
        )
        
        # CLI handles errors gracefully and shows user-friendly message
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        assert "No such file or directory" in result.stdout
    
    def test_cli_invalid_config_file(self, tmp_path):
        """Test CLI behavior with invalid config file"""
        invalid_config = tmp_path / "invalid_config.json"
        invalid_config.write_text("{ invalid json }")
        
        result = self.run_cli_command(
            "--config", str(invalid_config),
            "--get-company-data"
        )
        
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        assert "Expecting property name" in result.stdout
    
    def test_cli_missing_accounts_file(self, test_config_file, test_state_file, tmp_path):
        """Test CLI behavior when accounts file is missing"""
        missing_accounts = str(tmp_path / "missing_accounts.html")
        
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--accounts", missing_accounts,
            "--submit-accounts"
        )
        
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        assert "No such file or directory" in result.stdout
    
    def test_cli_authentication_failure(self, tmp_path):
        """Test CLI behavior with authentication failure"""
        # Create config with wrong credentials
        bad_config = tmp_path / "bad_config.json"
        config_data = {
            "presenter-id": "WRONG_PRESENTER",
            "authentication": "WRONG_AUTH",
            "company-number": "12345678",
            "company-authentication-code": "WRONG1234",
            "email": "test@example.com",
            "made-up-date": "2023-12-31",
            "test-flag": "1",
            "url": "http://localhost:9306/v1-0/xmlgw/Gateway"  # Non-existent server
        }
        
        with open(bad_config, 'w') as f:
            json.dump(config_data, f)
        
        state_file = str(tmp_path / "bad_state.json")
        
        result = self.run_cli_command(
            "--config", str(bad_config),
            "--state", state_file,
            "--get-company-data"
        )
        
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        # Could be connection error or authentication error
        assert any(phrase in result.stdout for phrase in ["Connection refused", "Authentication", "Service problems"])
    
    def test_cli_no_operation_specified(self, test_config_file, test_state_file):
        """Test CLI behavior when no operation is specified"""
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file
        )
        
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        assert "Need to specify an operation to perform" in result.stdout
    
    def test_cli_submit_accounts_without_file(self, test_config_file, test_state_file):
        """Test CLI behavior when submitting accounts without specifying file"""
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--submit-accounts"
        )
        
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        assert "--accounts must be specified" in result.stdout
    
    def test_cli_accounts_image_without_file(self, test_config_file, test_state_file):
        """Test CLI behavior when requesting accounts image without specifying file"""
        result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--accounts-image"
        )
        
        assert result.returncode == 0  # CLI doesn't crash
        assert "Exception:" in result.stdout
        assert "--accounts must be specified" in result.stdout
    
    def test_cli_custom_config_and_state_paths(self, mock_server, tmp_path, test_accounts_file):
        """Test CLI with custom config and state file paths"""
        # Create config in custom location
        custom_config_dir = tmp_path / "custom" / "config"
        custom_config_dir.mkdir(parents=True)
        config_file = custom_config_dir / "my_config.json"
        
        config_data = {
            "presenter-id": "E2E_PRESENTER",
            "authentication": "E2E_AUTH",
            "company-number": "12345678",
            "company-authentication-code": "E2E1234",
            "email": "custom@example.com",
            "made-up-date": "2023-12-31",
            "test-flag": "1",
            "url": mock_server.get_url()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
        
        # Use custom state location
        custom_state_dir = tmp_path / "custom" / "state"
        custom_state_dir.mkdir(parents=True)
        state_file = custom_state_dir / "my_state.json"
        
        # Test with custom paths
        result = self.run_cli_command(
            "--config", str(config_file),
            "--state", str(state_file),
            "--get-company-data"
        )
        
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Company: TEST COMPANY LIMITED" in result.stdout
        
        # Verify state file was created
        assert state_file.exists()
        
        # Verify state contains transaction data
        with open(state_file) as f:
            state_data = json.load(f)
        assert "transaction-id" in state_data
        assert state_data["transaction-id"] > 0
    
    def test_complete_filing_workflow_e2e(self, mock_server, test_config_file, test_state_file, test_accounts_file):
        """Test complete end-to-end filing workflow using CLI commands"""
        # Step 1: Get company data to verify authentication
        company_result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--get-company-data"
        )
        
        assert company_result.returncode == 0
        assert "Company: TEST COMPANY LIMITED" in company_result.stdout
        
        # Step 2: Submit accounts
        submit_result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--accounts", test_accounts_file,
            "--submit-accounts"
        )
        
        assert submit_result.returncode == 0
        assert "Submission completed." in submit_result.stdout
        
        # Extract submission ID
        submission_id_match = re.search(r"Submission ID is: (S\d+)", submit_result.stdout)
        assert submission_id_match
        submission_id = submission_id_match.group(1)
        
        # Step 3: Check submission status
        status_result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--submission-id", submission_id,
            "--get-submission-status"
        )
        
        assert status_result.returncode == 0
        assert f"{submission_id}: accepted" in status_result.stdout
        
        # Step 4: Generate accounts image
        image_result = self.run_cli_command(
            "--config", test_config_file,
            "--state", test_state_file,
            "--accounts", test_accounts_file,
            "--accounts-image"
        )
        
        assert image_result.returncode == 0
        
        # Verify state file contains incremented transaction IDs
        with open(test_state_file) as f:
            final_state = json.load(f)
        
        # Should have multiple transactions (company data, submit, status, image)
        assert final_state["transaction-id"] >= 4
        assert final_state["submission-id"] >= 1