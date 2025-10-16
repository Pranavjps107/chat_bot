# src/tools/sql_agent.py
from typing import Dict, Any, List
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.agents import tool
import asyncio

class InvoiceSQLAgent:
    def __init__(self, supabase_tool):
        self.supabase_tool = supabase_tool
        self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0)
        
        self.system_prompt = """
        You are an SQL expert for a PostgreSQL invoice database. The database has these tables:
        
        1. invoices: Main invoice information
           - id (UUID), invoice_number (VARCHAR), invoice_date (DATE), due_date (DATE), 
           - invoice_type (VARCHAR), status (VARCHAR), total_amount (DECIMAL), currency (VARCHAR),
           - ocr_confidence_score (DECIMAL), created_at (TIMESTAMP), updated_at (TIMESTAMP)
        
        2. sellers: Seller/vendor information
           - id (UUID), invoice_id (UUID), name (VARCHAR), address (TEXT), 
           - contact_information (TEXT), tax_id (VARCHAR), email (VARCHAR), phone (VARCHAR)
        
        3. buyers: Customer information  
           - id (UUID), invoice_id (UUID), name (VARCHAR), address (TEXT),
           - contact_information (TEXT), tax_id (VARCHAR), email (VARCHAR), phone (VARCHAR)
        
        4. invoice_items: Line items
           - id (UUID), invoice_id (UUID), item_description (TEXT), item_code (VARCHAR),
           - quantity (DECIMAL), unit_price (DECIMAL), discount_percentage (DECIMAL),
           - tax_rate (DECIMAL), line_total (DECIMAL)
        
        5. invoice_summary: Totals and summary
           - id (UUID), invoice_id (UUID), subtotal (DECIMAL), total_discount (DECIMAL),
           - total_tax (DECIMAL), shipping_cost (DECIMAL), total_amount_due (DECIMAL)
        
        6. payment_information: Payment details
           - id (UUID), invoice_id (UUID), payment_terms (VARCHAR), payment_method (VARCHAR),
           - payment_status (VARCHAR), paid_amount (DECIMAL), payment_date (DATE)
        
        Generate PostgreSQL queries for user questions. 
        - Return ONLY the SQL query without any explanation or markdown
        - Use proper JOINs when data from multiple tables is needed
        - Use PostgreSQL syntax (e.g., :: for casting, ILIKE for case-insensitive search)
        - Always limit results to 100 unless specified otherwise
        - Format dates using TO_CHAR when needed for display
        
        Examples:
        - For "total sales this month": Use EXTRACT or DATE_TRUNC
        - For "unpaid invoices": JOIN with payment_information table
        - For "customer history": GROUP BY buyer information
        """
        
    async def generate_query(self, user_question: str) -> str:
        """Generate SQL query from natural language question"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("user", "{question}")
        ])
        
        chain = prompt | self.llm
        response = await chain.ainvoke({"question": user_question})
        
        # Extract SQL from response
        sql_query = response.content.strip()
        
        # Clean up any markdown or code blocks
        if "```sql" in sql_query:
            sql_query = sql_query.split("```sql")[1].split("```")[0]
        elif "```" in sql_query:
            sql_query = sql_query.split("```")[1].split("```")[0]
        
        # Remove any SELECT statement prefix text
        lines = sql_query.split('\n')
        for i, line in enumerate(lines):
            if line.strip().upper().startswith('SELECT'):
                sql_query = '\n'.join(lines[i:])
                break
                
        return sql_query.strip()
    
    async def execute_query(self, query: str) -> Dict[str, Any]:
        """Execute SQL query using Supabase tool"""
        return await self.supabase_tool.execute_query(query)
    
    async def answer_question(self, question: str) -> str:
        """Generate and execute query, then format answer"""
        
        try:
            # Generate SQL
            query = await self.generate_query(question)
            print(f"Generated Query: {query}")
            
            # Execute query
            result = await self.execute_query(query)
            
            if not result["success"]:
                return f"Error executing query: {result['error']}"
            
            # Format response based on the data
            if result["data"] is None or len(result["data"]) == 0:
                return "No data found for your query."
            
            # Use LLM to format the response nicely
            format_prompt = """
            Based on this SQL query result, provide a clear, concise answer to the user's question.
            
            Question: {question}
            Query Result: {result}
            
            Format the answer in a user-friendly way:
            - Use bullet points for lists
            - Format monetary values with currency symbols
            - Format dates in a readable format (e.g., Jan 15, 2024)
            - Provide summaries for large datasets
            - Include relevant totals or counts
            """
            
            prompt = ChatPromptTemplate.from_template(format_prompt)
            chain = prompt | self.llm
            
            response = await chain.ainvoke({
                "question": question,
                "result": result["data"][:10]  # Limit data sent to LLM
            })
            
            return response.content
            
        except Exception as e:
            return f"Error processing query: {str(e)}"