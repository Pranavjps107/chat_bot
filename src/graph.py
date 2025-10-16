# src/graph.py
from langgraph.graph import END, StateGraph
from .nodes import InvoiceProcessingNodes
from .state import GraphState

class InvoiceProcessingWorkflow:
    def __init__(self):
        self.nodes = InvoiceProcessingNodes()
        self.app = self.build_graph()
    
    def build_graph(self):
        """Build the invoice processing workflow graph"""
        
        # Create the graph
        graph = StateGraph(GraphState)
        
        # Add nodes
        graph.add_node("perform_ocr", self.nodes.perform_ocr)
        graph.add_node("process_invoice_data", self.nodes.process_invoice_data)
        graph.add_node("validate_invoice", self.nodes.validate_invoice)
        graph.add_node("save_to_database", self.nodes.save_to_database)
        graph.add_node("process_user_query", self.nodes.process_user_query)
        
        # Set entry point
        graph.set_entry_point("perform_ocr")
        
        # Add edges
        graph.add_conditional_edges(
            "perform_ocr",
            self.nodes.check_ocr_status,
            {
                "ocr_success": "process_invoice_data",
                "ocr_failed": END
            }
        )
        
        graph.add_edge("process_invoice_data", "validate_invoice")
        
        graph.add_conditional_edges(
            "validate_invoice",
            self.nodes.check_validation_status,
            {
                "validation_passed": "save_to_database",
                "validation_warning": "save_to_database",
                "validation_failed": END
            }
        )
        
        graph.add_conditional_edges(
            "save_to_database",
            self.nodes.check_query_needed,
            {
                "process_query": "process_user_query",
                "skip_query": END
            }
        )
        
        graph.add_edge("process_user_query", END)
        
        return graph.compile()
    
    async def process_invoice(self, image_path: str, user_query: str = None):
        """Process an invoice image and optionally answer a query"""
        
        inputs = {
            "image_path": image_path,
            "user_query": user_query,
            "ocr_status": "pending",
            "db_status": "pending",
            "errors": [],
            "processing_logs": [],
            "query_results": []
        }
        
        # Run the workflow
        result = await self.app.ainvoke(inputs)
        
        return result