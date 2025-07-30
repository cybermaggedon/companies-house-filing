from typing import Dict, List, Optional
from datetime import datetime

class TestData:
    """Storage for test server data"""
    
    def __init__(self):
        self.reset()
        
    def reset(self):
        """Reset all stored data"""
        self.submissions: Dict[str, Dict] = {}
        self.transaction_counter = 0
        self.company_data = {
            "1234567": {
                "name": "TEST COMPANY LIMITED",
                "category": "Private Limited Company",
                "jurisdiction": "England/Wales",
                "trading": False,
                "made_up_date": "2023-12-31",
                "next_due_date": "2024-09-30",
                "address": {
                    "premise": "123",
                    "street": "Test Street",
                    "thoroughfare": "Test Area",
                    "post_town": "Test Town",
                    "postcode": "TE5 7ST",
                    "country": "United Kingdom"
                },
                "sic_codes": ["62012", "62020"]
            },
            "01234567": {
                "name": "TEST COMPANY LIMITED",
                "category": "Private Limited Company",
                "jurisdiction": "England/Wales",
                "trading": False,
                "made_up_date": "2023-12-31",
                "next_due_date": "2024-09-30",
                "address": {
                    "premise": "123",
                    "street": "Test Street",
                    "thoroughfare": "Test Area",
                    "post_town": "Test Town",
                    "postcode": "TE5 7ST",
                    "country": "United Kingdom"
                },
                "sic_codes": ["62012", "62020"]
            },
            "12345678": {
                "name": "TEST COMPANY LIMITED",
                "category": "Private Limited Company",
                "jurisdiction": "England/Wales",
                "trading": False,
                "made_up_date": "2023-12-31",
                "next_due_date": "2024-09-30",
                "address": {
                    "premise": "123",
                    "street": "Test Street",
                    "thoroughfare": "Test Area",
                    "post_town": "Test Town",
                    "postcode": "TE5 7ST",
                    "country": "United Kingdom"
                },
                "sic_codes": ["62012", "62020"]
            }
        }
        
    def add_submission(self, submission_id: str, status: str = "pending", 
                      company_number: str = None, data: str = None):
        """Add a submission to the data store"""
        self.submissions[submission_id] = {
            "id": submission_id,
            "status": status,
            "company_number": company_number,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
    def get_submission(self, submission_id: str) -> Optional[Dict]:
        """Get a submission by ID"""
        return self.submissions.get(submission_id)
        
    def get_all_submissions(self) -> List[Dict]:
        """Get all submissions"""
        return list(self.submissions.values())
        
    def update_submission_status(self, submission_id: str, status: str):
        """Update the status of a submission"""
        if submission_id in self.submissions:
            self.submissions[submission_id]["status"] = status
            
    def get_company_data(self, company_number: str) -> Optional[Dict]:
        """Get company data by number"""
        return self.company_data.get(company_number)
        
    def add_company_data(self, company_number: str, data: Dict):
        """Add or update company data"""
        self.company_data[company_number] = data
        
    def get_next_transaction_id(self) -> int:
        """Get the next transaction ID"""
        self.transaction_counter += 1
        return self.transaction_counter