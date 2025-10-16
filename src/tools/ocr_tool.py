# src/tools/ocr_tool.py
import google.generativeai as genai
import base64
import json
import asyncio
from typing import Dict, Any
from PIL import Image
import io

class GeminiOCRTool:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        
    async def extract_invoice_data(self, image_path: str) -> Dict[str, Any]:
        """Extract structured invoice data from image using Gemini"""
        
        prompt = """
        Analyze this invoice image and extract ALL information in a structured format.
        
        Return a JSON object with the following structure:
        {
            "invoice_info": {
                "invoice_number": "string",
                "invoice_date": "YYYY-MM-DD",
                "due_date": "YYYY-MM-DD",
                "invoice_type": "string (STANDARD/PROFORMA/CREDIT/DEBIT)",
                "po_number": "string or null"
            },
            "seller": {
                "name": "string",
                "address": "string",
                "tax_id": "string",
                "email": "string",
                "phone": "string"
            },
            "buyer": {
                "name": "string",
                "address": "string", 
                "tax_id": "string",
                "email": "string",
                "phone": "string"
            },
            "items": [
                {
                    "description": "string",
                    "code": "string or null",
                    "quantity": number,
                    "unit_price": number,
                    "discount_percentage": number,
                    "tax_rate": number,
                    "line_total": number
                }
            ],
            "summary": {
                "subtotal": number,
                "total_discount": number,
                "total_tax": number,
                "shipping_cost": number,
                "total_amount_due": number
            },
            "payment": {
                "terms": "string",
                "method": "string",
                "bank_details": "string or null"
            },
            "additional": {
                "notes": "string or null",
                "terms_and_conditions": "string or null"
            },
            "confidence_scores": {
                "overall": number (0-100),
                "invoice_number": number,
                "amounts": number,
                "dates": number
            }
        }
        
        IMPORTANT:
        - Extract ALL visible text and data
        - For missing fields, use null
        - Ensure all amounts are numbers (remove currency symbols)
        - Dates must be in YYYY-MM-DD format
        - Include confidence scores for data accuracy
        - If table has empty cells, mark them as null
        """
        
        try:
            # Load and encode image
            with open(image_path, "rb") as image_file:
                image_bytes = image_file.read()
                base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Generate content
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, {'mime_type': 'image/png', 'data': base64_image}]
            )
            
            # Parse response
            text = response.text
            # Clean markdown formatting if present
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
                
            result = json.loads(text.strip())
            return result
            
        except Exception as e:
            raise Exception(f"OCR extraction failed: {str(e)}")