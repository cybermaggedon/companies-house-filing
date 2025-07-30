import http.server
import time
from lxml import etree, objectify
import hashlib
import base64
from .responses import ResponseBuilder

class RequestHandler(http.server.BaseHTTPRequestHandler):
    """Handle incoming requests to the test server"""
    
    def do_POST(self):
        """Handle POST requests"""
        if self.path != "/v1-0/xmlgw/Gateway":
            self.send_error(404, "Not Found")
            return
            
        # Add configurable delay if set
        if hasattr(self, 'config') and self.config.delay > 0:
            time.sleep(self.config.delay)
            
        try:
            # Read the request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # Parse the XML
            root = objectify.fromstring(post_data)
            
            # Validate authentication if not disabled
            if hasattr(self, 'config') and not self.config.fail_auth:
                if not self._validate_authentication(root):
                    response = ResponseBuilder.build_error_response(
                        502, "Authentication failure"
                    )
                    self._send_response(response)
                    return
                    
            # Route to appropriate handler based on message class
            message_class = str(root.Header.MessageDetails.Class)
            
            if message_class == "CompanyDataRequest":
                self._handle_company_data(root)
            elif message_class == "Accounts":
                self._handle_accounts_submission(root)
            elif message_class == "GetSubmissionStatus":
                self._handle_submission_status(root)
            elif message_class == "AccountsImage":
                self._handle_accounts_image(root)
            else:
                response = ResponseBuilder.build_error_response(
                    100, f"Unknown message class: {message_class}"
                )
                self._send_response(response)
                
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")
            
    def _validate_authentication(self, root) -> bool:
        """Validate the authentication in the request"""
        try:
            sender_id = str(root.Header.SenderDetails.IDAuthentication.SenderID)
            auth_value = str(root.Header.SenderDetails.IDAuthentication.Authentication.Value)
            
            # Calculate expected hashes
            expected_sender = hashlib.md5(
                self.config.presenter_id.encode('utf-8')
            ).hexdigest()
            expected_auth = hashlib.md5(
                self.config.authentication.encode('utf-8')
            ).hexdigest()
            
            return sender_id == expected_sender and auth_value == expected_auth
            
        except Exception:
            return False
            
    def _handle_company_data(self, root):
        """Handle CompanyDataRequest"""
        try:
            company_number = str(root.Body.CompanyDataRequest.CompanyNumber)
            auth_code = str(root.Body.CompanyDataRequest.CompanyAuthenticationCode)
            
            # Validate company auth code
            if hasattr(self, 'config') and auth_code != self.config.company_auth_code:
                response = ResponseBuilder.build_error_response(
                    502, "Invalid company authentication code"
                )
                self._send_response(response)
                return
                
            # Get company data
            company_data = self.config.data.get_company_data(company_number)
            if not company_data:
                response = ResponseBuilder.build_error_response(
                    100, f"Company not found: {company_number}"
                )
                self._send_response(response)
                return
                
            response = ResponseBuilder.build_company_data_response(
                company_number, company_data
            )
            self._send_response(response)
            
        except Exception as e:
            response = ResponseBuilder.build_error_response(
                100, f"Error processing request: {str(e)}"
            )
            self._send_response(response)
            
    def _handle_accounts_submission(self, root):
        """Handle Accounts submission"""
        try:
            submission_id = str(root.Body.FormSubmission.FormHeader.SubmissionNumber)
            company_number = str(root.Body.FormSubmission.FormHeader.CompanyNumber)
            
            # Extract the accounts data
            doc_data = str(root.Body.FormSubmission.Document.Data)
            
            # Store the submission
            self.config.data.add_submission(
                submission_id, "accepted", company_number, doc_data
            )
            
            response = ResponseBuilder.build_submission_response(submission_id)
            self._send_response(response)
            
        except Exception as e:
            response = ResponseBuilder.build_error_response(
                9999, f"Error processing accounts: {str(e)}"
            )
            self._send_response(response)
            
    def _handle_submission_status(self, root):
        """Handle GetSubmissionStatus request"""
        try:
            # Check if specific submission requested
            submission_id = None
            try:
                submission_id = str(root.Body.GetSubmissionStatus.SubmissionNumber)
            except AttributeError:
                pass
                
            if submission_id:
                # Get specific submission
                submission = self.config.data.get_submission(submission_id)
                if submission:
                    submissions = [submission]
                else:
                    submissions = []
            else:
                # Get all submissions
                submissions = self.config.data.get_all_submissions()
                
            response = ResponseBuilder.build_status_response(submissions)
            self._send_response(response)
            
        except Exception as e:
            response = ResponseBuilder.build_error_response(
                100, f"Error getting status: {str(e)}"
            )
            self._send_response(response)
            
    def _handle_accounts_image(self, root):
        """Handle AccountsImage request"""
        try:
            # For now, return a simple response indicating success
            response = ResponseBuilder.build_accounts_image_response()
            self._send_response(response)
            
        except Exception as e:
            response = ResponseBuilder.build_error_response(
                100, f"Error generating image: {str(e)}"
            )
            self._send_response(response)
            
    def _send_response(self, xml_content: str):
        """Send XML response"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/xml')
        self.send_header('Content-Length', str(len(xml_content)))
        self.end_headers()
        self.wfile.write(xml_content.encode('utf-8'))
        
    def log_message(self, format, *args):
        """Override to suppress default logging"""
        pass