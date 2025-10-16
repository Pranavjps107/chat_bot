# src/nodes.py
from colorama import Fore, Style
from typing import Dict, Any
import asyncio
from .state import GraphState, OCRResult, ProcessedInvoice, ValidationResult, QueryResult
from .tools.ocr_tool import GeminiOCRTool
from .tools.supabase_tool import SupabaseTool
from .tools.sql_agent import InvoiceSQLAgent
from .tools.validators import InvoiceValidator
import os
from datetime import datetime

class InvoiceProcessingNodes:
    def __init__(self):
        self.ocr_tool = GeminiOCRTool(api_key=os.getenv("GOOGLE_API_KEY"))
        self.supabase_tool = SupabaseTool()
        self.sql_agent = InvoiceSQLAgent(self.supabase_tool.client)
        self.validator = InvoiceValidator()
    
    async def perform_ocr(self, state: GraphState) -> Dict[str, Any]:
        """Extract invoice data using OCR"""
        print(Fore.YELLOW + "🔍 Performing OCR on invoice image..." + Style.RESET_ALL)
        
        try:
            # Extract data from image
            ocr_data = await self.ocr_tool.extract_invoice_data(state["image_path"])
            
            # Create OCR result
            ocr_result = OCRResult(
                invoice_info=ocr_data.get("invoice_info", {}),
                table_info=ocr_data.get("items", []),
                total_info=ocr_data.get("summary", {}),
                confidence_scores=ocr_data.get("confidence_scores", {}),
                raw_text=str(ocr_data)
            )
            
            print(Fore.GREEN + f"✅ OCR completed with {ocr_result.confidence_scores.get('overall', 0)}% confidence" + Style.RESET_ALL)
            
            return {
                "ocr_result": ocr_result,
                "ocr_status": "completed",
                "processing_logs": [{
                    "step": "OCR",
                    "status": "success",
                    "timestamp": datetime.now().isoformat(),
                    "confidence": ocr_result.confidence_scores
                }]
            }
            
        except Exception as e:
            print(Fore.RED + f"❌ OCR failed: {str(e)}" + Style.RESET_ALL)
            return {
                "ocr_status": "failed",
                "errors": [f"OCR Error: {str(e)}"],
                "processing_logs": [{
                    "step": "OCR",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }]
            }
    
    async def process_invoice_data(self, state: GraphState) -> Dict[str, Any]:
        """Process and structure the OCR result"""
        print(Fore.YELLOW + "⚙️ Processing invoice data..." + Style.RESET_ALL)
        
        try:
            ocr_result = state["ocr_result"]
            
            # Convert to ProcessedInvoice format
            # This would include data transformation and cleaning
            processed = ProcessedInvoice(
                invoice_number=ocr_result.invoice_info.get("invoice_number"),
                invoice_date=ocr_result.invoice_info.get("invoice_date"),
                due_date=ocr_result.invoice_info.get("due_date"),
                # ... map all fields
            )
            
            print(Fore.GREEN + "✅ Invoice data processed successfully" + Style.RESET_ALL)
            
            return {
                "processed_invoice": processed,
                "processing_logs": [{
                    "step": "PROCESS_DATA",
                    "status": "success",
                    "timestamp": datetime.now().isoformat()
                }]
            }
            
        except Exception as e:
            print(Fore.RED + f"❌ Processing failed: {str(e)}" + Style.RESET_ALL)
            return {
                "errors": [f"Processing Error: {str(e)}"],
                "processing_logs": [{
                    "step": "PROCESS_DATA",
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }]
            }
    
    async def validate_invoice(self, state: GraphState) -> Dict[str, Any]:
        """Validate the processed invoice data"""
        print(Fore.YELLOW + "✔️ Validating invoice data..." + Style.RESET_ALL)
        
        try:
            validation_result = await self.validator.validate(state["processed_invoice"])
            
            if validation_result.is_valid:
                print(Fore.GREEN + "✅ Validation passed" + Style.RESET_ALL)
            else:
                print(Fore.YELLOW + f"⚠️ Validation warnings: {validation_result.warnings}" + Style.RESET_ALL)
            
            return {
                "validation_result": validation_result,
                "processing_logs": [{
                    "step": "VALIDATE",
                    "status": "success" if validation_result.is_valid else "warning",
                    "details": validation_result.dict(),
                    "timestamp": datetime.now().isoformat()
                }]
            }
            
        except Exception as e:
            print(Fore.RED + f"❌ Validation failed: {str(e)}" + Style.RESET_ALL)
            return {
                "errors": [f"Validation Error: {str(e)}"]
            }
    
    async def save_to_database(self, state: GraphState) -> Dict[str, Any]:
        """Save the validated invoice to Supabase"""
        print(Fore.YELLOW + "💾 Saving invoice to database..." + Style.RESET_ALL)
        
        try:
            # Convert OCR result to format expected by Supabase tool
            invoice_data = state["ocr_result"].__dict__ if state["ocr_result"] else {}
            
            invoice_id = await self.supabase_tool.save_invoice(invoice_data)
            
            print(Fore.GREEN + f"✅ Invoice saved with ID: {invoice_id}" + Style.RESET_ALL)
            
            return {
                "invoice_id": invoice_id,
                "db_status": "saved",
                "processing_logs": [{
                    "step": "SAVE_DATABASE",
                    "status": "success",
                    "invoice_id": invoice_id,
                    "timestamp": datetime.now().isoformat()
                }]
            }
            
        except Exception as e:
            print(Fore.RED + f"❌ Database save failed: {str(e)}" + Style.RESET_ALL)
            return {
                "db_status": "failed",
                "errors": [f"Database Error: {str(e)}"]
            }
    
    async def process_user_query(self, state: GraphState) -> Dict[str, Any]:
        """Process user's SQL query about invoices"""
        print(Fore.YELLOW + "🔍 Processing user query..." + Style.RESET_ALL)
        
        try:
            user_query = state.get("user_query")
            if not user_query:
                return {}
            
            # Get answer from SQL agent
            answer = await self.sql_agent.answer_question(user_query)
            
            query_result = QueryResult(
                query=user_query,
                result=answer,
                execution_time=0.0,  # You can add timing
                success=True
            )
            
            print(Fore.GREEN + "✅ Query processed successfully" + Style.RESET_ALL)
            
            return {
                "query_results": [query_result]
            }
            
        except Exception as e:
            print(Fore.RED + f"❌ Query failed: {str(e)}" + Style.RESET_ALL)
            
            query_result = QueryResult(
                query=state.get("user_query", ""),
                result=None,
                execution_time=0.0,
                # src/nodes.py (continued)
                success=False,
                error_message=str(e)
            )
            
            return {
                "query_results": [query_result],
                "errors": [f"Query Error: {str(e)}"]
            }
    
    @staticmethod
    def check_ocr_status(state: GraphState) -> str:
        """Check if OCR was successful"""
        if state.get("ocr_status") == "completed":
            return "ocr_success"
        else:
            return "ocr_failed"
    
    @staticmethod
    def check_validation_status(state: GraphState) -> str:
        """Check if validation passed"""
        validation_result = state.get("validation_result")
        if validation_result and validation_result.is_valid:
            return "validation_passed"
        elif validation_result and not validation_result.is_valid and not validation_result.errors:
            return "validation_warning"
        else:
            return "validation_failed"
    
    @staticmethod
    def check_query_needed(state: GraphState) -> str:
        """Check if user has a query to process"""
        if state.get("user_query"):
            return "process_query"
        else:
            return "skip_query"