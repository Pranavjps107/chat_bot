# src/state.py
from typing import List, Dict, Any, Optional, Annotated
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from datetime import date, datetime
from decimal import Decimal
from operator import add

class OCRResult(BaseModel):
    """Raw OCR extraction result"""
    invoice_info: Dict[str, Any]
    table_info: Dict[str, Any]
    total_info: Dict[str, Any]
    confidence_scores: Dict[str, float]
    raw_text: str

class SellerInfo(BaseModel):
    name: str = ""
    address: str = ""
    contact_information: str = ""
    tax_id: str = ""
    email: str = ""
    phone: str = ""

class BuyerInfo(BaseModel):
    name: str = ""
    address: str = ""
    contact_information: str = ""
    tax_id: str = ""
    email: str = ""
    phone: str = ""

class InvoiceItem(BaseModel):
    item_description: str
    item_code: Optional[str] = None
    quantity: Decimal
    unit_price: Decimal
    discount_percentage: Optional[Decimal] = Decimal("0")
    discount_amount: Optional[Decimal] = Decimal("0")
    tax_rate: Optional[Decimal] = Decimal("0")
    tax_amount: Optional[Decimal] = Decimal("0")
    line_total: Decimal

class InvoiceSummary(BaseModel):
    subtotal: Decimal
    total_discount: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")
    shipping_cost: Decimal = Decimal("0")
    total_amount_due: Decimal

class ProcessedInvoice(BaseModel):
    invoice_number: str
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    invoice_type: str = "STANDARD"
    seller: SellerInfo
    buyer: BuyerInfo
    items: List[InvoiceItem]
    summary: InvoiceSummary
    payment_terms: Optional[str] = None
    payment_method: Optional[str] = None
    po_number: Optional[str] = None
    notes: Optional[str] = None
    ocr_confidence: float = 0.0

class ValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    suggestions: List[str] = []

class QueryResult(BaseModel):
    query: str
    result: Any
    execution_time: float
    success: bool
    error_message: Optional[str] = None

class GraphState(TypedDict):
    # Input
    image_path: str
    image_url: Optional[str]
    
    # OCR Processing
    ocr_result: Optional[OCRResult]
    ocr_status: str  # pending, processing, completed, failed
    
    # Data Processing
    processed_invoice: Optional[ProcessedInvoice]
    validation_result: Optional[ValidationResult]
    
    # Database Operations
    invoice_id: Optional[str]
    db_status: str  # pending, saving, saved, failed
    
    # SQL Query
    user_query: Optional[str]
    query_results: Annotated[List[QueryResult], add]
    
    # Error Handling
    errors: Annotated[List[str], add]
    processing_logs: Annotated[List[Dict[str, Any]], add]