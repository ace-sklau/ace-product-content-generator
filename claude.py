import anthropic
import pandas as pd
import json
import os
from taxonomy import ProductTaxonomyClassifier
from typing import Optional, Dict, Any, List

class ClaudeQuery:
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize ClaudeQuery with API key.
        
        Args:
            api_key: Anthropic API key. If None, will try to get from environment variable.
        """
        if api_key is None:
            api_key = os.environ["ANTHROPIC_API_KEY"]
        df = pd.read_csv(os.path.join('resources', 'taxonomy.csv'))
        self.classifier = ProductTaxonomyClassifier(api_key=api_key, taxonomy_df=df)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.default_categories = [
            "Automotive, RV and Marine", "Home and Decor", "Outdoor Living", 
            "Lawn and Garden", "Heating and Cooling", "Plumbing", "Tools", 
            "Building Supplies", "Hardware", "Lighting and Electrical", 
            "Paint and Supplies", "Novelty", "Storage and Organization"
        ]

    def search(self, context: str = '', query: Optional[str] = None, 
               model: str = "claude-3-7-sonnet-20250219", temperature: float = 0.8) -> List[Dict[str, Any]]:
        """
        Generate product data using Claude API.
        
        Args:
            context: Product information to process
            query: Custom query override
            model: Claude model to use
            temperature: Response creativity (0.0-1.0)
            
        Returns:
            List of dictionaries containing product data
        """
        if query is None:
            query = self._build_default_query()
        
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=5000,
                temperature=temperature,
                system="You are an AI assistant for a marketing team. Your role is to create data for products to be ingested by backend processes",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query + str(context)
                            }
                        ]
                    }
                ]
            )
            
            # Extract text content from the response
            response_text = ""
            for content_block in message.content:
                if hasattr(content_block, 'text'):
                    response_text += content_block.text
            
            return self._parse_response(response_text)
            
        except Exception as e:
            print(f"Error in API call: {e}")
            return [e]

    def _build_default_query(self) -> str:
        """Build the default product data generation query."""
        categories_str = "; ".join(self.default_categories)
        
        return f"""
You create product data about new products that will be put onto the AceHardware website for wholesale sale. 
When generating the product data, please use concise description for each product and provide its product category from the following: {categories_str}. 
Also include a list of features of the product (in bullet format) and do not list the price for the product. 
Finally include the UPC and the manufacturer name (and manufacturer code). 

Structure the response as valid JSON with the following fields:
- UPC: item upc/ean code
- Vendor: vendor/manufacturer name
- Item_Number: manufacturer item/model number
- Product_Category: product category from the list above
- Product_Title: concise product title
- Product_Description: detailed product description
- Product_Features: array of key features
- Wholesale_Case_Weight: weight of each unit
- Wholesale_Case_Dimensions: dimensions of each unit

Return only valid JSON without any formatting indicators or additional text.

Use the following product information to produce this content:
"""

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        """
        Parse the Claude response and extract JSON data.
        
        Args:
            response_text: Raw response from Claude
            
        Returns:
            List of parsed product dictionaries
        """
        try:
            # Try to parse as single JSON object first
            if response_text.strip().startswith('{'):
                results = json.loads(response_text.strip())
                taxonomy = self.classify(str(results))
                print("TAXCONOMYO")
                print(taxonomy)
                return [results], taxonomy
            
            # Try to parse as JSON array
            elif response_text.strip().startswith('['):
                results = json.loads(response_text.strip())
                taxonomy = self.classify(str(results))
                print("TAXCONOMYO")
                print(taxonomy)
                return [results], taxonomy
            
            # Try to extract JSON from text
            else:
                # Look for JSON-like content between braces
                import re
                json_matches = re.findall(r'\{[^{}]*\}', response_text, re.DOTALL)
                results = []
                for match in json_matches:
                    try:
                        results.append(json.loads(match))
                    except json.JSONDecodeError:
                        continue
                taxonomy = self.classify(str(results))
                print("TAXCONOMYO")
                print(taxonomy)
                return results, taxonomy
                
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response text: {response_text[:500]}...")
            return []

    def generate_multiple_products(self, product_contexts: List[str], 
                                 batch_size: int = 5) -> List[Dict[str, Any]]:
        """
        Generate product data for multiple products.
        
        Args:
            product_contexts: List of product information strings
            batch_size: Number of products to process per API call
            
        Returns:
            List of all generated product data
        """
        all_results = []
        
        for i in range(0, len(product_contexts), batch_size):
            batch = product_contexts[i:i + batch_size]
            batch_context = "\n\n---NEXT PRODUCT---\n\n".join(batch)
            
            # Modify query to handle multiple products
            multi_query = self._build_default_query().replace(
                "Return only valid JSON", 
                "Return a JSON array containing one object for each product"
            )
            
            results = self.search(context=batch_context, query=multi_query)
            all_results.extend(results)
            
        return all_results
    
    def classify(self, product_description):
        print("=== Complete Product Classification ===")
        
        try:
            result = self.classifier.classify_product(product_description)
            print(f"Product: {result['product_description']}")
            print(f"Level 1: {result['level_1_category']}")
            print(f"Level 2: {result['level_2_category']}")
            print(f"Level 3: {result['level_3_category']}")
            print("Attributes:")
            for attr, value in result['attributes'].items():
                print(f"  - {attr}: {value}")
            return result
        
        except Exception as e:
            print(f"Classification error: {e}")     
            return ""   
        # Reset conversation for new product
        self.classifier.reset_conversation()