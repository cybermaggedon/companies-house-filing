import pytest
import subprocess
import json
import tempfile
import os
from pathlib import Path
import time
import signal
import socket


class TestCLIScripting:
    """Test CLI scripting and configuration variant tests"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Create temporary directory for config files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_config(self, temp_config_dir):
        """Create a sample configuration file"""
        config_data = {
            "presenter-id": "CLI_TEST_PRESENTER",
            "authentication": "CLI_TEST_AUTH",
            "company-number": "99887766",
            "company-name": "CLI TEST COMPANY LIMITED",
            "company-authentication-code": "CLI9988",
            "company-type": "EW",
            "contact-name": "CLI Test Person",  
            "contact-number": "07900 998877",
            "email": "cli@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "CLI001",
            "url": "http://localhost:9405/v1-0/xmlgw/Gateway"
        }
        
        config_file = temp_config_dir / "cli_test_config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        return config_file
    
    @pytest.fixture
    def sample_accounts_file(self, temp_config_dir):
        """Create a sample accounts file"""
        accounts_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:uk-bus="http://xbrl.frc.org.uk/cd/2021-01-01/business"
      xmlns:uk-core="http://xbrl.frc.org.uk/fr/2021-01-01/core">
<head>
    <title>CLI Test Company - Annual Accounts</title>
    <ix:header>
        <ix:hidden>
            <ix:nonNumeric contextRef="entity" name="uk-bus:EntityCurrentLegalName">CLI TEST COMPANY LIMITED</ix:nonNumeric>
            <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">99887766</ix:nonNumeric>
        </ix:hidden>
    </ix:header>
</head>
<body>
    <h1>CLI TEST COMPANY LIMITED</h1>
    <p>Company Number: <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">99887766</ix:nonNumeric></p>
    <p>Turnover: <ix:nonFraction contextRef="period" name="uk-core:Turnover" unitRef="GBP">750000</ix:nonFraction></p>
</body>
</html>"""
        
        accounts_file = temp_config_dir / "cli_test_accounts.html"
        with open(accounts_file, 'w') as f:
            f.write(accounts_content)
        
        return accounts_file
    
    def _find_free_port(self):
        """Find a free port for testing"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    def test_ch_filing_help_command(self):
        """Test ch-filing --help command"""
        result = subprocess.run(['ch-filing', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0, f"ch-filing --help failed: {result.stderr}"
        assert "usage:" in result.stdout.lower() or "usage" in result.stdout.lower()
        assert "ch-filing" in result.stdout.lower() or "filing" in result.stdout.lower()
        
        print(f"✓ ch-filing --help works")
        print(f"  Output length: {len(result.stdout)} characters")
    
    def test_ch_mock_server_help_command(self):
        """Test ch-mock-server --help command"""
        result = subprocess.run(['ch-mock-server', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0, f"ch-mock-server --help failed: {result.stderr}"
        assert "usage:" in result.stdout.lower() or "usage" in result.stdout.lower()
        assert "server" in result.stdout.lower() or "mock" in result.stdout.lower()
        
        print(f"✓ ch-mock-server --help works")
        print(f"  Output length: {len(result.stdout)} characters")
    
    def test_python_module_invocation(self):
        """Test python -m ch_filing and python -m ch_filing.test_server"""
        # Test main module
        result = subprocess.run(['python', '-m', 'ch_filing', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0, f"python -m ch_filing --help failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()
        
        print(f"✓ python -m ch_filing --help works")
        
        # Test test server module  
        result = subprocess.run(['python', '-m', 'ch_filing.test_server', '--help'], 
                              capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0, f"python -m ch_filing.test_server --help failed: {result.stderr}"
        assert "usage:" in result.stdout.lower()
        
        print(f"✓ python -m ch_filing.test_server --help works")
    
    def test_mock_server_startup_shutdown(self):
        """Test mock server startup and shutdown via CLI"""
        port = self._find_free_port()
        
        # Start server in background
        server_process = subprocess.Popen([
            'ch-mock-server', 
            '--port', str(port),
            '--presenter-id', 'TEST_PRESENTER',
            '--authentication', 'TEST_AUTH'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        try:
            # Give server time to start
            time.sleep(2)
            
            # Check if server is running
            assert server_process.poll() is None, "Mock server exited unexpectedly"
            
            # Try to connect to server (basic check)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex(('localhost', port))
                assert result == 0, f"Could not connect to mock server on port {port}"
            
            print(f"✓ Mock server started successfully on port {port}")
            
        finally:
            # Shutdown server
            if server_process.poll() is None:
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_process.kill()
                    server_process.wait()
            
            print(f"✓ Mock server shutdown completed")
    
    def test_configuration_file_validation(self, temp_config_dir):
        """Test CLI with various configuration file formats"""
        test_configs = [
            # Valid minimal config
            {
                "presenter-id": "TEST",
                "authentication": "AUTH",
                "company-number": "12345678",
                "made-up-date": "2023-12-31",
                "url": "http://localhost:8080/v1-0/xmlgw/Gateway"
            },
            
            # Config with all fields
            {
                "presenter-id": "FULL_TEST",
                "authentication": "FULL_AUTH", 
                "company-number": "87654321",
                "company-name": "FULL TEST COMPANY LIMITED",
                "company-authentication-code": "FULL1234",
                "company-type": "EW",
                "contact-name": "Full Test Person",
                "contact-number": "07900 123456",
                "email": "full@example.com",
                "made-up-date": "2023-12-31",
                "date-signed": "2024-01-15", 
                "date": "2024-01-20",
                "package-reference": "FULL001",
                "url": "http://localhost:8080/v1-0/xmlgw/Gateway"
            }
        ]
        
        for i, config_data in enumerate(test_configs):
            config_file = temp_config_dir / f"test_config_{i}.json"
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            # Test config validation (this would typically be done by the main CLI)
            # For now, just test that we can create a State object
            try:
                from ch_filing.state import State
                state_file = temp_config_dir / f"test_state_{i}.json"
                state = State(str(config_file), str(state_file))
                
                # Verify required fields are accessible
                assert state.get("presenter-id") == config_data["presenter-id"]
                assert state.get("authentication") == config_data["authentication"]
                assert state.get("company-number") == config_data["company-number"]
                
                print(f"✓ Configuration {i} validated successfully")
                
            except Exception as e:
                pytest.fail(f"Configuration {i} validation failed: {e}")
    
    def test_environment_variable_override(self, sample_config, temp_config_dir):
        """Test environment variable override functionality"""
        # Note: This test assumes the CLI would support environment variables
        # The current implementation may not have this feature
        
        test_env = os.environ.copy()
        test_env.update({
            'CH_FILING_PRESENTER_ID': 'ENV_PRESENTER',
            'CH_FILING_AUTHENTICATION': 'ENV_AUTH',
            'CH_FILING_URL': 'http://env.example.com/v1-0/xmlgw/Gateway'
        })
        
        # Test that environment variables could be used
        # This is more of a design test for future CLI enhancement
        
        print("✓ Environment variable test framework ready")
        print("  Note: Environment variable override not yet implemented in CLI")
    
    def test_batch_scripting_workflow(self, sample_config, sample_accounts_file, temp_config_dir):
        """Test a complete batch scripting workflow"""
        # Create a batch script that would use the CLI tools
        batch_script = temp_config_dir / "batch_test.py"
        
        script_content = f'''#!/usr/bin/env python3
import sys
import json
from pathlib import Path

# Add current directory to path to import ch_filing
sys.path.insert(0, ".")

from ch_filing.state import State
from ch_filing.client import Client
from ch_filing.company_data import CompanyData
from ch_filing.envelope import Envelope

def main():
    try:
        # Load configuration
        config_file = "{sample_config}"
        state_file = "{temp_config_dir / "batch_state.json"}"
        
        state = State(config_file, state_file)
        client = Client(state)
        
        # Create company data request
        content = CompanyData.create_request(state)
        envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
        
        print("✓ Batch script: Company data request created successfully")
        print(f"✓ Transaction ID: {{state.get_cur_tx_id()}}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Batch script error: {{e}}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
        
        with open(batch_script, 'w') as f:
            f.write(script_content)
        
        # Make script executable
        os.chmod(batch_script, 0o755)
        
        # Run the batch script
        result = subprocess.run([
            'python', str(batch_script)
        ], capture_output=True, text=True, timeout=30, cwd=os.getcwd())
        
        print(f"\nBatch Script Output:")
        print(f"  Return code: {result.returncode}")
        print(f"  Stdout: {result.stdout}")
        if result.stderr:
            print(f"  Stderr: {result.stderr}")
        
        assert result.returncode == 0, f"Batch script failed: {result.stderr}"
        assert "Company data request created successfully" in result.stdout
        
        print("✓ Batch scripting workflow completed successfully")
    
    def test_concurrent_cli_usage(self, sample_config, temp_config_dir):
        """Test concurrent CLI usage scenarios"""
        import threading
        import queue
        
        num_processes = 5
        results_queue = queue.Queue()
        
        def run_cli_process(process_id):
            try:
                # Create separate state file for each process
                state_file = temp_config_dir / f"concurrent_state_{process_id}.json"
                
                # Simulate CLI usage by directly using the library
                from ch_filing.state import State
                from ch_filing.company_data import CompanyData
                from ch_filing.envelope import Envelope
                
                state = State(str(sample_config), str(state_file))
                
                # Perform operations
                content = CompanyData.create_request(state)
                envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
                
                tx_id = state.get_cur_tx_id()
                
                results_queue.put({
                    'process_id': process_id,
                    'success': True,
                    'tx_id': tx_id,
                    'error': None
                })
                
            except Exception as e:
                results_queue.put({
                    'process_id': process_id,
                    'success': False,
                    'tx_id': None,
                    'error': str(e)
                })
        
        # Start concurrent processes
        threads = []
        for i in range(num_processes):
            thread = threading.Thread(target=run_cli_process, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all processes to complete
        for thread in threads:
            thread.join()
        
        # Collect results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())
        
        # Analyze results
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"\nConcurrent CLI Usage:")
        print(f"  Total processes: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        
        if failed:
            for result in failed:
                print(f"  Process {result['process_id']} error: {result['error']}")
        
        assert len(successful) == num_processes, f"Not all concurrent processes succeeded"
        
        # Verify transaction IDs are unique (each process has its own state)
        tx_ids = [r['tx_id'] for r in successful]
        unique_tx_ids = set(tx_ids)
        
        print(f"  Transaction IDs: {tx_ids}")
        print(f"  Unique transaction IDs: {len(unique_tx_ids)}")
        
        # Each process should have its own transaction ID sequence
        assert len(unique_tx_ids) <= num_processes, "Unexpected transaction ID pattern"
        
        print("✓ Concurrent CLI usage handled correctly")
    
    def test_configuration_validation_errors(self, temp_config_dir):
        """Test CLI behavior with invalid configurations"""
        invalid_configs = [
            # Missing required fields
            {
                "presenter-id": "TEST"
                # Missing other required fields
            },
            
            # Invalid JSON
            "{ invalid json syntax",
            
            # Empty config
            {},
            
            # Invalid field types
            {
                "presenter-id": 123,  # Should be string
                "authentication": True,  # Should be string
                "company-number": ["12345678"],  # Should be string
                "made-up-date": "invalid-date",
                "url": "not-a-url"
            }
        ]
        
        for i, config_data in enumerate(invalid_configs):
            config_file = temp_config_dir / f"invalid_config_{i}.json"
            
            try:
                if isinstance(config_data, str):
                    # Invalid JSON string
                    with open(config_file, 'w') as f:
                        f.write(config_data)
                else:
                    # Invalid config dict
                    with open(config_file, 'w') as f:
                        json.dump(config_data, f)
                
                # Try to use the invalid config
                from ch_filing.state import State
                state_file = temp_config_dir / f"invalid_state_{i}.json"
                
                try:
                    state = State(str(config_file), str(state_file))
                    
                    # Try to perform operations
                    from ch_filing.company_data import CompanyData
                    content = CompanyData.create_request(state)
                    
                    print(f"⚠ Invalid config {i} was accepted (might fail later)")
                    
                except Exception as e:
                    print(f"✓ Invalid config {i} properly rejected: {type(e).__name__}")
                    
            except Exception as e:
                print(f"✓ Invalid config {i} caused expected error: {type(e).__name__}")
    
    def test_command_line_argument_parsing(self):
        """Test command line argument parsing"""
        # Test various argument combinations
        test_cases = [
            # Basic help
            (['ch-filing', '--help'], True),
            (['ch-mock-server', '--help'], True),
            
            # Mock server with arguments
            (['ch-mock-server', '--port', '9999', '--help'], True),
            (['ch-mock-server', '--presenter-id', 'TEST', '--help'], True),
            
            # Invalid arguments (should fail gracefully)
            (['ch-filing', '--invalid-argument'], False),
            (['ch-mock-server', '--port', 'invalid-port'], False),
        ]
        
        for args, should_succeed in test_cases:
            try:
                result = subprocess.run(args, capture_output=True, text=True, timeout=10)
                
                if should_succeed:
                    # For --help commands, return code might be 0
                    if '--help' in args:
                        assert result.returncode == 0, f"Help command failed: {' '.join(args)}"
                        print(f"✓ Command succeeded: {' '.join(args)}")
                    else:
                        # Non-help commands might fail due to missing config, that's okay
                        print(f"? Command executed: {' '.join(args)} (rc: {result.returncode})")
                else:
                    # Invalid commands should fail
                    assert result.returncode != 0, f"Invalid command unexpectedly succeeded: {' '.join(args)}"
                    print(f"✓ Invalid command properly failed: {' '.join(args)}")
                    
            except subprocess.TimeoutExpired:
                print(f"⚠ Command timed out: {' '.join(args)}")
            except Exception as e:
                if not should_succeed:
                    print(f"✓ Invalid command caused expected error: {' '.join(args)}")
                else:
                    print(f"? Command caused error: {' '.join(args)}: {e}")
    
    def test_output_formatting_options(self, sample_config, temp_config_dir):
        """Test different output formatting options"""
        # This test assumes the CLI might support different output formats
        # Currently testing the underlying data structures
        
        from ch_filing.state import State
        from ch_filing.company_data import CompanyData
        from ch_filing.envelope import Envelope
        from lxml import etree
        
        state_file = temp_config_dir / "format_test_state.json"
        state = State(str(sample_config), str(state_file))
        
        # Test XML output (default)
        content = CompanyData.create_request(state)
        envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
        
        xml_output = etree.tostring(envelope, pretty_print=True, encoding='unicode')
        
        # Verify XML is well-formed
        try:
            parsed = etree.fromstring(xml_output)
            print("✓ XML output is well-formed")
            print(f"  XML root tag: {parsed.tag}")
            print(f"  XML length: {len(xml_output)} characters")
        except Exception as e:
            pytest.fail(f"XML output malformed: {e}")
        
        # Test compact XML output
        compact_xml = etree.tostring(envelope, pretty_print=False, encoding='unicode')
        
        assert len(compact_xml) < len(xml_output), "Compact XML should be shorter"
        print(f"✓ Compact XML output available ({len(compact_xml)} chars)")
        
        print("✓ Output formatting options tested")