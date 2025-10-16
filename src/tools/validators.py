# src/tools/validators.py
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, date
import re

class InvoiceValidator:
    """Validate invoice data for completeness and accuracy"""
    
    async def validate(self, invoice_data: Any) -> Any:
        """Comprehensive invoice validation"""
        from ..state import ValidationResult
        
        errors = []
        warnings = []
        suggestions = []
        
        # 1. Validate required fields
        if not invoice_data.invoice_number:
            errors.append("Invoice number is required")
        
        if not invoice_data.invoice_date:
            warnings.append("Invoice date is missing")
        
        # 2. Validate invoice number format
        if invoice_data.invoice_number and not self._validate_invoice_number(invoice_data.invoice_number):
            warnings.append("Invoice number format may be incorrect")
        
        # 3. Validate dates
        if invoice_data.invoice_date and invoice_data.due_date:
            if invoice_data.due_date < invoice_data.invoice_date:
                errors.append("Due date cannot be before invoice date")
        
        # 4. Validate amounts
        if invoice_data.summary:
            if not self._validate_totals(invoice_data):
                warnings.append("Invoice totals may not add up correctly")
        
        # 5. Validate seller/buyer info
        if not invoice_data.seller or not invoice_data.seller.name:
            warnings.append("Seller information is incomplete")
        
        if not invoice_data.buyer or not invoice_data.buyer.name:
            warnings.append("Buyer information is incomplete")
        
        # 6. Validate email formats
        if invoice_data.seller and invoice_data.seller.email:
            if not self._validate_email(invoice_data.seller.email):
                warnings.append("Seller email format is invalid")
        
        if invoice_data.buyer and invoice_data.buyer.email:
            if not self._validate_email(invoice_data.buyer.email):
                warnings.append("Buyer email format is invalid")
        
        # 7. Validate line items
        if not invoice_data.items or len(invoice_data.items) == 0:
            errors.append("Invoice must have at least one line item")
        else:
            for i, item in enumerate(invoice_data.items):
                if item.quantity <= 0:
                    errors.append(f"Item {i+1}: Quantity must be positive")
                if item.unit_price < 0:
                    errors.append(f"Item {i+1}: Unit price cannot be negative")
        
        # Generate suggestions
        if invoice_data.ocr_confidence < 80:
            suggestions.append("OCR confidence is low. Manual review recommended.")
        
        if not invoice_data.payment_terms:
            suggestions.append("Consider adding payment terms")
        
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def _validate_invoice_number(self, invoice_number: str) -> bool:
        """Validate invoice number format"""
        # Basic validation - can be customized
        pattern = r'^[A-Z0-9\-/]+$'
        return bool(re.match(pattern, invoice_number.upper()))
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_totals(self, invoice_data: Any) -> bool:
        """Validate that invoice totals add up correctly"""
        try:
            # Calculate expected totals
            calculated_subtotal = Decimal(0)
            calculated_tax = Decimal(0)
            
            for item in invoice_data.items:
                line_total = Decimal(str(item.quantity)) * Decimal(str(item.unit_price))
                if item.discount_percentage:
                    line_total *= (Decimal(100) - Decimal(str(item.discount_percentage))) / Decimal(100)
                
                calculated_subtotal += line_total
                
                if item.tax_rate:
                    calculated_tax += line_total * Decimal(str(item.tax_rate)) / Decimal(100)
            
            # Compare with provided totals (allow small margin for rounding)
            provided_subtotal = Decimal(str(invoice_data.summary.subtotal))
            provided_tax = Decimal(str(invoice_data.summary.total_tax))
            
            subtotal_diff = abs(calculated_subtotal - provided_subtotal)
            tax_diff = abs(calculated_tax - provided_tax)
            
            return subtotal_diff < Decimal("0.10") and tax_diff < Decimal("0.10")
            
        except Exception:
            return False