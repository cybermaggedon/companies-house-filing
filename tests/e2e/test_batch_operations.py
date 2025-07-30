import pytest
import json
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import tempfile
import shutil

from ch_filing.client import Client
from ch_filing.state import State
from ch_filing.company_data import CompanyData
from ch_filing.form_submission import Accounts
from ch_filing.submission_status import SubmissionStatus
from ch_filing.envelope import Envelope
from ch_filing.test_server import MockServer


@dataclass
class BatchOperationResult:
    """Result of a batch operation"""
    operation_type: str
    success: bool
    duration: float
    error: Optional[str] = None
    response_data: Optional[Any] = None


class TestBatchOperations:
    """Extended end-to-end tests for batch operations"""
    
    @pytest.fixture
    def batch_state_template(self, tmp_path):
        """Create a template state for batch operations"""
        config_template = {
            "presenter-id": "BATCH_PRESENTER_999",
            "authentication": "BATCH_AUTH_XYZ789",
            "company-number": "11111111",
            "company-name": "BATCH TEST COMPANY LIMITED",
            "company-authentication-code": "BATCH999",
            "company-type": "EW",
            "contact-name": "Batch Test Person",
            "contact-number": "07900 111111",
            "email": "batch@example.com",
            "made-up-date": "2023-12-31",
            "date-signed": "2024-01-15",
            "date": "2024-01-20",
            "package-reference": "BATCH001",
            "url": "http://localhost:9404/v1-0/xmlgw/Gateway"
        }
        return config_template
    
    @pytest.fixture
    def sample_accounts_data(self):
        """Create sample accounts data for batch testing"""
        return """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:uk-bus="http://xbrl.frc.org.uk/cd/2021-01-01/business"
      xmlns:uk-core="http://xbrl.frc.org.uk/fr/2021-01-01/core">
<head>
    <title>Batch Test Company - Annual Accounts</title>
    <ix:header>
        <ix:hidden>
            <ix:nonNumeric contextRef="entity" name="uk-bus:EntityCurrentLegalName">BATCH TEST COMPANY LIMITED</ix:nonNumeric>
            <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">11111111</ix:nonNumeric>
        </ix:hidden>
    </ix:header>
</head>
<body>
    <h1>BATCH TEST COMPANY LIMITED</h1>
    <p>Company Number: <ix:nonNumeric contextRef="entity" name="uk-bus:CompaniesHouseRegisteredNumber">11111111</ix:nonNumeric></p>
    <p>Turnover: <ix:nonFraction contextRef="period" name="uk-core:Turnover" unitRef="GBP">500000</ix:nonFraction></p>
    <p>Total Assets: <ix:nonFraction contextRef="period" name="uk-core:TotalCurrentAssets" unitRef="GBP">100000</ix:nonFraction></p>
</body>
</html>"""
    
    def _create_isolated_state(self, config_template: Dict, tmp_path: Path, identifier: str) -> State:
        """Create an isolated state for batch testing"""
        config_file = tmp_path / f"batch_config_{identifier}.json"
        state_file = tmp_path / f"batch_state_{identifier}.json"
        
        # Customize config for this batch item
        config = config_template.copy()
        config["company-number"] = str(int(config["company-number"]) + hash(identifier) % 1000000).zfill(8)
        config["company-name"] = f"BATCH COMPANY {identifier} LIMITED"
        config["package-reference"] = f"BATCH{identifier:03d}"
        
        with open(config_file, 'w') as f:
            json.dump(config, f)
        
        return State(str(config_file), str(state_file))
    
    def test_multiple_company_data_requests(self, batch_state_template, tmp_path):
        """Test batch processing of multiple company data requests"""
        num_companies = 20
        results = []
        
        with MockServer(
            port=9404,
            presenter_id="BATCH_PRESENTER_999",
            authentication="BATCH_AUTH_XYZ789",
            company_auth_code="BATCH999"
        ) as server:
            
            def process_company(company_id: int) -> BatchOperationResult:
                try:
                    start_time = time.time()
                    
                    # Create isolated state
                    state = self._create_isolated_state(batch_state_template, tmp_path, f"comp{company_id}")
                    client = Client(state)
                    
                    # Create and send request
                    content = CompanyData.create_request(state)
                    envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
                    response = client.call(state, envelope)
                    
                    duration = time.time() - start_time
                    
                    return BatchOperationResult(
                        operation_type="company_data",
                        success=True,
                        duration=duration,
                        response_data=response
                    )
                    
                except Exception as e:
                    duration = time.time() - start_time
                    return BatchOperationResult(
                        operation_type="company_data",
                        success=False,
                        duration=duration,
                        error=str(e)
                    )
            
            # Process in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(process_company, i) for i in range(num_companies)]
                results = [future.result() for future in as_completed(futures)]
        
        # Analyze results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        avg_duration = sum(r.duration for r in successful) / len(successful) if successful else 0
        total_duration = max(r.duration for r in results) if results else 0
        
        print(f"\nBatch Company Data Requests:")
        print(f"  Total requests: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Success rate: {len(successful) / len(results) * 100:.1f}%")
        print(f"  Average duration: {avg_duration:.3f}s")
        print(f"  Total duration: {total_duration:.3f}s")
        print(f"  Throughput: {len(successful) / total_duration:.1f} req/sec")
        
        # Assertions
        assert len(successful) >= num_companies * 0.9, f"Too many failures: {len(failed)} out of {num_companies}"
        assert avg_duration < 1.0, f"Average request too slow: {avg_duration:.3f}s"
        
        # Print any errors
        for result in failed:
            print(f"  Error: {result.error}")
    
    def test_batch_accounts_submission(self, batch_state_template, tmp_path, sample_accounts_data):
        """Test batch submission of multiple accounts"""
        num_submissions = 10
        results = []
        
        with MockServer(
            port=9404,
            presenter_id="BATCH_PRESENTER_999",
            authentication="BATCH_AUTH_XYZ789",
            company_auth_code="BATCH999"
        ) as server:
            
            def submit_accounts(submission_id: int) -> BatchOperationResult:
                try:
                    start_time = time.time()
                    
                    # Create isolated state
                    state = self._create_isolated_state(batch_state_template, tmp_path, f"sub{submission_id}")
                    client = Client(state)
                    
                    # Create and send submission
                    submission = Accounts.create_submission(
                        state, 
                        f"batch_accounts_{submission_id}.html", 
                        sample_accounts_data
                    )
                    envelope = Envelope.create(state, submission, "Accounts", "request")
                    response = client.call(state, envelope)
                    
                    duration = time.time() - start_time
                    
                    return BatchOperationResult(
                        operation_type="accounts_submission",
                        success=True,
                        duration=duration,
                        response_data=response
                    )
                    
                except Exception as e:
                    duration = time.time() - start_time
                    return BatchOperationResult(
                        operation_type="accounts_submission",
                        success=False,
                        duration=duration,
                        error=str(e)
                    )
            
            # Process submissions with some delay to avoid overwhelming
            for i in range(num_submissions):
                result = submit_accounts(i)
                results.append(result)
                if i < num_submissions - 1:
                    time.sleep(0.1)  # Small delay between submissions
        
        # Analyze results
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        avg_duration = sum(r.duration for r in successful) / len(successful) if successful else 0
        total_duration = sum(r.duration for r in results)
        
        print(f"\nBatch Accounts Submissions:")
        print(f"  Total submissions: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Success rate: {len(successful) / len(results) * 100:.1f}%")
        print(f"  Average duration: {avg_duration:.3f}s")
        print(f"  Total duration: {total_duration:.3f}s")
        
        # Assertions
        assert len(successful) >= num_submissions * 0.8, f"Too many submission failures: {len(failed)}"
        assert avg_duration < 2.0, f"Average submission too slow: {avg_duration:.3f}s"
    
    def test_mixed_operation_workflow(self, batch_state_template, tmp_path, sample_accounts_data):
        """Test a complete workflow with mixed operations"""
        num_companies = 5
        results = []
        
        with MockServer(
            port=9404,
            presenter_id="BATCH_PRESENTER_999",
            authentication="BATCH_AUTH_XYZ789",
            company_auth_code="BATCH999"
        ) as server:
            
            def complete_workflow(company_id: int) -> List[BatchOperationResult]:
                workflow_results = []
                
                try:
                    # Create isolated state
                    state = self._create_isolated_state(batch_state_template, tmp_path, f"wf{company_id}")
                    client = Client(state)
                    
                    # Step 1: Company data request
                    start_time = time.time()
                    content = CompanyData.create_request(state)
                    envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
                    response = client.call(state, envelope)
                    duration = time.time() - start_time
                    
                    workflow_results.append(BatchOperationResult(
                        operation_type="company_data",
                        success=True,
                        duration=duration,
                        response_data=response
                    ))
                    
                    # Step 2: Accounts submission
                    start_time = time.time()
                    submission = Accounts.create_submission(
                        state, 
                        f"workflow_accounts_{company_id}.html", 
                        sample_accounts_data
                    )
                    envelope = Envelope.create(state, submission, "Accounts", "request")
                    response = client.call(state, envelope)
                    duration = time.time() - start_time
                    
                    workflow_results.append(BatchOperationResult(
                        operation_type="accounts_submission",
                        success=True,
                        duration=duration,
                        response_data=response
                    ))
                    
                    # Step 3: Multiple status checks
                    for i in range(3):
                        start_time = time.time()
                        status_content = SubmissionStatus.create_request(state, f"S{i+1:05d}")
                        envelope = Envelope.create(state, status_content, "GetSubmissionStatus", "request")
                        response = client.call(state, envelope)
                        duration = time.time() - start_time
                        
                        workflow_results.append(BatchOperationResult(
                            operation_type="status_check",
                            success=True,
                            duration=duration,
                            response_data=response
                        ))
                    
                except Exception as e:
                    workflow_results.append(BatchOperationResult(
                        operation_type="workflow_error",
                        success=False,
                        duration=0,
                        error=str(e)
                    ))
                
                return workflow_results
            
            # Execute workflows in parallel
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(complete_workflow, i) for i in range(num_companies)]
                all_results = []
                for future in as_completed(futures):
                    all_results.extend(future.result())
        
        # Analyze results by operation type
        by_operation = {}
        for result in all_results:
            op_type = result.operation_type
            if op_type not in by_operation:
                by_operation[op_type] = []
            by_operation[op_type].append(result)
        
        print(f"\nMixed Operation Workflow:")
        for op_type, results in by_operation.items():
            successful = [r for r in results if r.success]
            failed = [r for r in results if not r.success]
            avg_duration = sum(r.duration for r in successful) / len(successful) if successful else 0
            
            print(f"  {op_type.replace('_', ' ').title()}:")
            print(f"    Total: {len(results)}")
            print(f"    Successful: {len(successful)}")
            print(f"    Failed: {len(failed)}")
            print(f"    Average duration: {avg_duration:.3f}s")
        
        # Overall success rate should be high
        total_operations = len(all_results)
        successful_operations = len([r for r in all_results if r.success])
        success_rate = successful_operations / total_operations if total_operations > 0 else 0
        
        print(f"  Overall success rate: {success_rate * 100:.1f}%")
        assert success_rate >= 0.8, f"Overall success rate too low: {success_rate:.1%}"
    
    def test_concurrent_state_management(self, batch_state_template, tmp_path):
        """Test concurrent access to state management"""
        num_threads = 10
        operations_per_thread = 20
        results = []
        
        # Create a shared state
        shared_state = self._create_isolated_state(batch_state_template, tmp_path, "shared")
        
        def state_operations(thread_id: int) -> List[BatchOperationResult]:
            thread_results = []
            
            for i in range(operations_per_thread):
                try:
                    start_time = time.time()
                    
                    # Mix of state operations
                    if i % 3 == 0:
                        tx_id = shared_state.get_next_tx_id()
                        operation = f"tx_id_{tx_id}"
                    elif i % 3 == 1:
                        sub_id = shared_state.get_next_submission_id()
                        operation = f"sub_id_{sub_id}"
                    else:
                        cur_tx = shared_state.get_cur_tx_id()
                        cur_sub = shared_state.get_cur_submission_id()
                        operation = f"current_{cur_tx}_{cur_sub}"
                    
                    duration = time.time() - start_time
                    
                    thread_results.append(BatchOperationResult(
                        operation_type="state_operation",
                        success=True,
                        duration=duration,
                        response_data=operation
                    ))
                    
                except Exception as e:
                    duration = time.time() - start_time
                    thread_results.append(BatchOperationResult(
                        operation_type="state_operation",
                        success=False,
                        duration=duration,
                        error=str(e)
                    ))
                
                # Small delay to increase chance of concurrent access
                time.sleep(0.001)
            
            return thread_results
        
        # Run concurrent state operations
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(state_operations, i) for i in range(num_threads)]
            all_results = []
            for future in as_completed(futures):
                all_results.extend(future.result())
        
        # Analyze state consistency
        successful = [r for r in all_results if r.success]
        failed = [r for r in all_results if not r.success]
        
        print(f"\nConcurrent State Management:")
        print(f"  Total operations: {len(all_results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Success rate: {len(successful) / len(all_results) * 100:.1f}%")
        
        # Check final state consistency
        final_tx_id = shared_state.get_cur_tx_id()
        final_sub_id = shared_state.get_cur_submission_id()
        
        print(f"  Final transaction ID: {final_tx_id}")
        print(f"  Final submission ID: {final_sub_id}")
        
        # Transaction and submission IDs should be consistent with operations performed
        expected_tx_increments = len([r for r in successful if "tx_id_" in str(r.response_data)])
        expected_sub_increments = len([r for r in successful if "sub_id_" in str(r.response_data)])
        
        print(f"  Expected TX increments: {expected_tx_increments}")
        print(f"  Expected SUB increments: {expected_sub_increments}")
        
        # State should be consistent (allowing for initial values)
        assert final_tx_id >= expected_tx_increments, "Transaction ID inconsistency detected"
        assert final_sub_id >= expected_sub_increments, "Submission ID inconsistency detected"
        
        # Most operations should succeed
        assert len(successful) >= len(all_results) * 0.9, "Too many state operation failures"
    
    @pytest.mark.slow
    def test_long_running_batch_process(self, batch_state_template, tmp_path):
        """Test long-running batch process stability"""
        duration_seconds = 120  # 2 minutes
        batch_size = 5
        batches_processed = 0
        total_operations = 0
        all_results = []
        
        with MockServer(
            port=9404,
            presenter_id="BATCH_PRESENTER_999",
            authentication="BATCH_AUTH_XYZ789",
            company_auth_code="BATCH999"
        ) as server:
            
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                batch_results = []
                
                # Process a batch of operations
                for i in range(batch_size):
                    try:
                        operation_start = time.time()
                        
                        # Create isolated state for this operation
                        state = self._create_isolated_state(
                            batch_state_template, 
                            tmp_path, 
                            f"long_{batches_processed}_{i}"
                        )
                        client = Client(state)
                        
                        # Alternate between different operation types
                        if i % 2 == 0:
                            content = CompanyData.create_request(state)
                            envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
                            operation_type = "company_data"
                        else:
                            status_content = SubmissionStatus.create_request(state, f"S{i+1:05d}")
                            envelope = Envelope.create(state, status_content, "GetSubmissionStatus", "request")
                            operation_type = "status_check"
                        
                        response = client.call(state, envelope)
                        duration = time.time() - operation_start
                        
                        batch_results.append(BatchOperationResult(
                            operation_type=operation_type,
                            success=True,
                            duration=duration,
                            response_data=response
                        ))
                        
                    except Exception as e:
                        duration = time.time() - operation_start
                        batch_results.append(BatchOperationResult(
                            operation_type="error",
                            success=False,
                            duration=duration,
                            error=str(e)
                        ))
                
                all_results.extend(batch_results)
                batches_processed += 1
                total_operations += len(batch_results)
                
                # Brief pause between batches
                time.sleep(1.0)
                
                # Progress update every 10 batches
                if batches_processed % 10 == 0:
                    elapsed = time.time() - start_time
                    print(f"  Processed {batches_processed} batches ({total_operations} operations) in {elapsed:.1f}s")
        
        # Final analysis
        successful = [r for r in all_results if r.success]
        failed = [r for r in all_results if not r.success]
        total_time = time.time() - start_time
        
        print(f"\nLong Running Batch Process:")
        print(f"  Duration: {total_time:.1f}s")
        print(f"  Batches processed: {batches_processed}")
        print(f"  Total operations: {total_operations}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Success rate: {len(successful) / total_operations * 100:.1f}%")
        print(f"  Operations per second: {total_operations / total_time:.1f}")
        
        # Performance should remain stable
        assert len(successful) >= total_operations * 0.8, "Success rate too low for long running process"
        assert total_operations / total_time >= 1.0, "Throughput too low for long running process"
    
    def test_batch_error_recovery(self, batch_state_template, tmp_path):
        """Test error recovery in batch operations"""
        num_operations = 20
        results = []
        
        # Create a mix of valid and invalid configurations
        def create_operation_state(op_id: int) -> State:
            if op_id % 4 == 0:  # Every 4th operation will have invalid config
                config = batch_state_template.copy()
                config["company-number"] = ""  # Invalid company number
                return self._create_isolated_state(config, tmp_path, f"invalid_{op_id}")
            else:
                return self._create_isolated_state(batch_state_template, tmp_path, f"valid_{op_id}")
        
        with MockServer(
            port=9404,
            presenter_id="BATCH_PRESENTER_999",
            authentication="BATCH_AUTH_XYZ789",
            company_auth_code="BATCH999"
        ) as server:
            
            for op_id in range(num_operations):
                try:
                    start_time = time.time()
                    
                    state = create_operation_state(op_id)
                    client = Client(state)
                    
                    # Try to create and send request
                    content = CompanyData.create_request(state)
                    envelope = Envelope.create(state, content, "CompanyDataRequest", "request")
                    response = client.call(state, envelope)
                    
                    duration = time.time() - start_time
                    
                    results.append(BatchOperationResult(
                        operation_type="recovery_test",
                        success=True,
                        duration=duration,
                        response_data=response
                    ))
                    
                except Exception as e:
                    duration = time.time() - start_time
                    results.append(BatchOperationResult(
                        operation_type="recovery_test",
                        success=False,
                        duration=duration,
                        error=str(e)
                    ))
                
                # Continue processing even after errors
                time.sleep(0.1)
        
        # Analyze error recovery
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print(f"\nBatch Error Recovery:")
        print(f"  Total operations: {len(results)}")
        print(f"  Successful: {len(successful)}")
        print(f"  Failed: {len(failed)}")
        print(f"  Success rate: {len(successful) / len(results) * 100:.1f}%")
        
        # We expect about 75% success rate (every 4th operation fails)
        expected_success_rate = 0.75
        actual_success_rate = len(successful) / len(results)
        
        print(f"  Expected success rate: {expected_success_rate * 100:.1f}%")
        print(f"  Actual success rate: {actual_success_rate * 100:.1f}%")
        
        # Success rate should be close to expected (allowing for some variation)
        assert abs(actual_success_rate - expected_success_rate) < 0.2, \
            f"Success rate deviation too large: expected {expected_success_rate:.1%}, got {actual_success_rate:.1%}"
        
        # System should continue processing after errors
        assert len(results) == num_operations, "Not all operations were processed"
        
        print("✓ Batch processing continued successfully despite errors")