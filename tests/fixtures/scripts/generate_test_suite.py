#!/usr/bin/env python3
"""
Test suite generator script.

This script generates a comprehensive test suite with various scenarios:
- Multiple company configurations
- Different account types (micro, small, medium)
- Error scenarios and edge cases
- Performance test data
- Security test payloads

Usage:
    python generate_test_suite.py [--count N] [--output-dir DIR]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

# Add the parent directory to the path to import test_data_generator
sys.path.append(str(Path(__file__).parent.parent / "data"))
from test_data_generator import TestDataGenerator


def generate_company_scenarios() -> List[Dict]:
    """Generate various company testing scenarios"""
    generator = TestDataGenerator()
    
    scenarios = [
        # Standard scenarios
        {
            'name': 'micro_entity_standard',
            'config_type': 'micro',
            'company_type': 'micro',
            'description': 'Standard micro entity with minimal requirements'
        },
        {
            'name': 'small_company_complete',
            'config_type': 'complete', 
            'company_type': 'small',
            'description': 'Small company with full configuration'
        },
        {
            'name': 'minimal_config_test',
            'config_type': 'minimal',
            'company_type': 'micro',
            'description': 'Minimal configuration test'
        },
        
        # Edge cases
        {
            'name': 'company_with_leading_zeros',
            'config_type': 'complete',
            'company_type': 'small',
            'company_number': '00123456',
            'description': 'Company number with leading zeros'
        },
        {
            'name': 'long_company_name',
            'config_type': 'complete',
            'company_type': 'small',
            'overrides': {
                'company-name': 'VERY LONG COMPANY NAME FOR TESTING MAXIMUM LENGTH LIMITS AND EDGE CASES LIMITED'
            },
            'description': 'Company with very long name'
        },
        {
            'name': 'special_characters_contact',
            'config_type': 'complete',
            'company_type': 'small',
            'overrides': {
                'contact-name': "O'Brien & Associates",
                'email': 'test+special@example-domain.co.uk'
            },
            'description': 'Contact details with special characters'
        },
        
        # Different company types
        {
            'name': 'scottish_company',
            'config_type': 'complete',
            'company_type': 'small',
            'overrides': {
                'company-type': 'SC',
                'company-name': 'SCOTTISH TEST COMPANY LIMITED'
            },
            'description': 'Scottish company registration'
        },
        {
            'name': 'northern_ireland_company',
            'config_type': 'complete',
            'company_type': 'small',
            'overrides': {
                'company-type': 'NI',
                'company-name': 'NORTHERN IRELAND TEST COMPANY LIMITED'
            },
            'description': 'Northern Ireland company registration'
        },
        
        # Financial scenarios
        {
            'name': 'high_turnover_micro',
            'config_type': 'micro',
            'company_type': 'micro',
            'financial_overrides': {
                'turnover': 630000  # Near micro entity limit
            },
            'description': 'Micro entity with high turnover near limit'
        },
        {
            'name': 'loss_making_company',
            'config_type': 'complete',
            'company_type': 'small',
            'financial_overrides': {
                'profit_margin': -0.05  # Loss making
            },
            'description': 'Company with losses'
        },
        
        # Date scenarios
        {
            'name': 'year_end_march',
            'config_type': 'complete',
            'company_type': 'small',
            'overrides': {
                'made-up-date': '2024-03-31',
                'date-signed': '2024-06-30',
                'date': '2024-07-15'
            },
            'description': 'Company with March year end'
        },
        {
            'name': 'short_accounting_period',
            'config_type': 'complete',
            'company_type': 'small',
            'overrides': {
                'made-up-date': '2023-09-30'  # 9 month period
            },
            'description': 'Company with short accounting period'
        }
    ]
    
    return scenarios


def generate_error_scenarios() -> List[Dict]:
    """Generate error testing scenarios"""
    return [
        {
            'name': 'invalid_company_number',
            'config_type': 'invalid',
            'error_expected': True,
            'description': 'Invalid company number format'
        },
        {
            'name': 'empty_required_fields',
            'config_type': 'minimal',
            'overrides': {
                'presenter-id': '',
                'authentication': ''
            },
            'error_expected': True,
            'description': 'Empty required fields'
        },
        {
            'name': 'malformed_url',
            'config_type': 'complete',
            'overrides': {
                'url': 'not-a-valid-url'
            },
            'error_expected': True,
            'description': 'Malformed URL'
        },
        {
            'name': 'invalid_date_format',
            'config_type': 'complete',
            'overrides': {
                'made-up-date': '2023-13-32',  # Invalid date
                'date-signed': 'not-a-date'
            },
            'error_expected': True,
            'description': 'Invalid date formats'
        },
        {
            'name': 'oversized_data',
            'config_type': 'complete',
            'overrides': {
                'company-name': 'X' * 1000,  # Very long name
                'contact-name': 'Y' * 500
            },
            'error_expected': True,
            'description': 'Oversized field data'
        }
    ]


def generate_security_scenarios() -> List[Dict]:
    """Generate security testing scenarios"""
    return [
        {
            'name': 'sql_injection_attempt',
            'config_type': 'complete',
            'overrides': {
                'company-name': "'; DROP TABLE companies; --",
                'contact-name': "' OR 1=1 --"
            },
            'security_test': True,
            'description': 'SQL injection attempt in text fields'
        },
        {
            'name': 'xss_injection_attempt',
            'config_type': 'complete',
            'overrides': {
                'company-name': "<script>alert('xss')</script>",
                'email': "test@example.com<script>alert('xss')</script>"
            },
            'security_test': True,
            'description': 'XSS injection attempt'
        },
        {
            'name': 'xml_entity_injection',
            'config_type': 'complete',
            'overrides': {
                'company-name': "<!ENTITY xxe SYSTEM 'file:///etc/passwd'>TEST&xxe;",
            },
            'security_test': True,
            'description': 'XML external entity injection attempt'
        },
        {
            'name': 'unicode_normalization',
            'config_type': 'complete',
            'overrides': {
                'company-name': "CAFÉ COMPANY LIMITED",  # Unicode characters
                'contact-name': "José María García"
            },
            'security_test': True,
            'description': 'Unicode normalization test'
        },
        {
            'name': 'null_byte_injection',
            'config_type': 'complete',
            'overrides': {
                'presenter-id': "TEST\x00ADMIN",
                'authentication': "AUTH\x00BYPASS"
            },
            'security_test': True,
            'description': 'Null byte injection attempt'
        }
    ]


def generate_performance_scenarios() -> List[Dict]:
    """Generate performance testing scenarios"""
    return [
        {
            'name': 'large_accounts_file',
            'config_type': 'complete',
            'company_type': 'small',
            'performance_test': True,
            'description': 'Large accounts file for performance testing',
            'special_handling': 'generate_large_accounts'
        },
        {
            'name': 'concurrent_submissions',
            'config_type': 'complete',
            'company_type': 'small',
            'performance_test': True,
            'count': 50,  # Generate 50 similar configs
            'description': 'Multiple configs for concurrent testing'
        },
        {
            'name': 'rapid_sequential_requests',
            'config_type': 'micro',
            'company_type': 'micro',
            'performance_test': True,
            'count': 100,
            'description': 'Many configs for rapid sequential testing'
        }
    ]


def generate_test_suite(output_dir: Path, scenario_count: int = None):
    """Generate the complete test suite"""
    generator = TestDataGenerator(output_dir)
    
    # Create directory structure
    (output_dir / "configs").mkdir(exist_ok=True, parents=True)
    (output_dir / "accounts").mkdir(exist_ok=True, parents=True)
    (output_dir / "responses").mkdir(exist_ok=True, parents=True)
    (output_dir / "security").mkdir(exist_ok=True, parents=True)
    (output_dir / "performance").mkdir(exist_ok=True, parents=True)
    (output_dir / "errors").mkdir(exist_ok=True, parents=True)
    
    # Generate scenarios
    company_scenarios = generate_company_scenarios()
    error_scenarios = generate_error_scenarios()
    security_scenarios = generate_security_scenarios()
    performance_scenarios = generate_performance_scenarios()
    
    # Limit scenarios if requested
    if scenario_count:
        company_scenarios = company_scenarios[:scenario_count]
        error_scenarios = error_scenarios[:min(scenario_count // 2, len(error_scenarios))]
        security_scenarios = security_scenarios[:min(scenario_count // 3, len(security_scenarios))]
        performance_scenarios = performance_scenarios[:min(scenario_count // 4, len(performance_scenarios))]
    
    all_scenarios = {
        'company': company_scenarios,
        'error': error_scenarios,
        'security': security_scenarios,
        'performance': performance_scenarios
    }
    
    generated_files = {
        'configs': [],
        'accounts': [],
        'responses': [],
        'manifests': []
    }
    
    # Generate files for each scenario type
    for scenario_type, scenarios in all_scenarios.items():
        print(f"\nGenerating {scenario_type} scenarios...")
        
        for i, scenario in enumerate(scenarios):
            scenario_name = scenario['name']
            count = scenario.get('count', 1)
            
            # Generate multiple instances if count > 1
            for instance in range(count):
                if count > 1:
                    instance_name = f"{scenario_name}_{instance+1:03d}"
                else:
                    instance_name = scenario_name
                
                print(f"  Generating {instance_name}...")
                
                try:
                    # Generate configuration
                    config_overrides = scenario.get('overrides', {})
                    company_number = scenario.get('company_number')
                    if count > 1 and not company_number:
                        # Generate unique company number for each instance
                        company_number = generator.generate_company_number(f"{i+1:02d}{instance+1:02d}")
                    
                    config = generator.generate_config(
                        scenario.get('config_type', 'complete'),
                        company_number=company_number,
                        **config_overrides
                    )
                    
                    # Save configuration
                    config_subdir = scenario_type if scenario_type != 'company' else 'standard'
                    config_file = generator.save_test_data(
                        config, 
                        f"{instance_name}_config.json",
                        f"configs/{config_subdir}"
                    )
                    generated_files['configs'].append(str(config_file))
                    
                    # Generate accounts file (if not an error scenario)
                    if not scenario.get('error_expected', False):
                        company_type = scenario.get('company_type', 'small')
                        
                        # Handle special cases
                        if scenario.get('special_handling') == 'generate_large_accounts':
                            # Create a very large accounts file
                            accounts_html = generator.generate_accounts_html(
                                config['company-number'],
                                config.get('company-name', f'LARGE COMPANY {instance+1} LIMITED'),
                                company_type
                            )
                            # Add extra data to make it large
                            extra_notes = "\n    <div>" + "X" * 50000 + "</div>" * 10
                            accounts_html = accounts_html.replace("</body>", extra_notes + "\n</body>")
                        else:
                            accounts_html = generator.generate_accounts_html(
                                config['company-number'],
                                config.get('company-name', f'TEST COMPANY {instance+1} LIMITED'),
                                company_type
                            )
                        
                        # Apply financial overrides if specified
                        financial_overrides = scenario.get('financial_overrides', {})
                        if financial_overrides:
                            # This is a simplified implementation
                            # In a real scenario, you'd regenerate with specific financial data
                            pass
                        
                        # Save accounts file
                        accounts_subdir = scenario_type if scenario_type != 'company' else 'standard'
                        accounts_file = generator.save_test_data(
                            accounts_html,
                            f"{instance_name}_accounts.html", 
                            f"accounts/{accounts_subdir}"
                        )
                        generated_files['accounts'].append(str(accounts_file))
                    
                    # Generate sample responses
                    if scenario_type not in ['error', 'security']:
                        # Success response
                        success_response = generator.generate_response_xml(
                            'company_data_success',
                            company_number=config['company-number'],
                            company_name=config.get('company-name', 'Test Company Limited')
                        )
                        
                        response_file = generator.save_test_data(
                            success_response,
                            f"{instance_name}_success_response.xml",
                            f"responses/{config_subdir}"
                        )
                        generated_files['responses'].append(str(response_file))
                    
                    # Generate error responses for error scenarios
                    if scenario.get('error_expected', False):
                        error_response = generator.generate_response_xml(
                            'error',
                            error_code='100',
                            error_text='Validation error'
                        )
                        
                        error_file = generator.save_test_data(
                            error_response,
                            f"{instance_name}_error_response.xml",
                            f"responses/errors"
                        )
                        generated_files['responses'].append(str(error_file))
                
                except Exception as e:
                    print(f"    Error generating {instance_name}: {e}")
                    continue
    
    # Generate manifest file
    manifest = {
        'generated_at': generator.__class__.__name__,
        'total_scenarios': sum(len(scenarios) for scenarios in all_scenarios.values()),
        'scenario_types': {
            scenario_type: len(scenarios) 
            for scenario_type, scenarios in all_scenarios.items()
        },
        'files': generated_files,
        'scenarios': all_scenarios
    }
    
    manifest_file = generator.save_test_data(manifest, "test_suite_manifest.json")
    generated_files['manifests'].append(str(manifest_file))
    
    # Generate summary
    total_files = sum(len(files) for files in generated_files.values())
    print(f"\n✅ Test suite generation complete!")
    print(f"   Generated {total_files} files")
    print(f"   Configs: {len(generated_files['configs'])}")
    print(f"   Accounts: {len(generated_files['accounts'])}")
    print(f"   Responses: {len(generated_files['responses'])}")
    print(f"   Manifest: {manifest_file}")
    print(f"   Output directory: {output_dir}")
    
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive test suite for GnuCash CH Filing")
    parser.add_argument('--count', type=int, help='Limit number of scenarios per type')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).parent.parent,
                       help='Output directory for test files')
    
    args = parser.parse_args()
    
    print(f"Generating test suite in: {args.output_dir}")
    if args.count:
        print(f"Limited to {args.count} scenarios per type")
    
    manifest = generate_test_suite(args.output_dir, args.count)
    
    print(f"\nManifest saved to: test_suite_manifest.json")
    print("Use this manifest to reference generated test data in your tests.")


if __name__ == "__main__":
    main()