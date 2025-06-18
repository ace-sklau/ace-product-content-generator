import json
import requests
from typing import Dict, Any, Tuple
from dataclasses import dataclass
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class JudgeResult:
    """Structure for judge evaluation results"""
    score: float
    comments: str
    factual_accuracy: float
    hallucination_check: float
    tone_appropriateness: float

class LLMProductJudge:
    """
    LLM Judge for evaluating product descriptions against metadata
    using Databricks API with Llama 4 Maverick
    """
    
    def __init__(self, databricks_endpoint: str, api_token: str):
        """
        Initialize the judge with Databricks API credentials
        
        Args:
            databricks_endpoint: Databricks serving endpoint URL
            api_token: Databricks API token
        """
        self.endpoint = databricks_endpoint
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def _call_llama_api(self, prompt: str) -> str:
        """
        Make API call to Databricks Llama 4 Maverick endpoint
        
        Args:
            prompt: The prompt to send to the model
            
        Returns:
            Model response text
        """
        payload = {
            "inputs": prompt,
            "parameters": {
                "temperature": 0.1,  # Low temperature for consistent judging
                "max_tokens": 500,
                "top_p": 0.9
            }
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            # Extract text from response (format may vary based on Databricks setup)
            if 'predictions' in result:
                return result['predictions'][0]['output']
            elif 'choices' in result:
                return result['choices'][0]['text']
            else:
                return result.get('output', str(result))
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API call failed: {e}")
            raise Exception(f"Failed to call Databricks API: {e}")
    
    def _create_judge_prompt(self, metadata: Dict[str, Any], description: str) -> str:
        """
        Create a comprehensive prompt for the LLM judge
        
        Args:
            metadata: Product metadata dictionary
            description: Product description text
            
        Returns:
            Formatted prompt string
        """
        metadata_str = json.dumps(metadata, indent=2)
        
        prompt = f"""You are an expert product evaluation judge. Your task is to evaluate a product description against its metadata across three key dimensions:

1. FACTUAL ACCURACY: How well does the description match the facts in the metadata?
2. HALLUCINATION CHECK: Are there any false claims or invented details not supported by the metadata?
3. TONE APPROPRIATENESS: Is the tone suitable for a customer-facing retail environment?

PRODUCT METADATA:
{metadata_str}

PRODUCT DESCRIPTION:
{description}

Please evaluate and provide your assessment in the following JSON format:
{{
    "factual_accuracy": <score 0.0-1.0>,
    "hallucination_check": <score 0.0-1.0, where 1.0 means no hallucinations>,
    "tone_appropriateness": <score 0.0-1.0>,
    "overall_score": <average score 0.0-1.0>,
    "comments": "<specific feedback and suggested improvements>"
}}

EVALUATION CRITERIA:
- Factual Accuracy: Check if description aligns with metadata facts (price, features, specifications, etc.)
- Hallucination Check: Identify any claims not supported by metadata (1.0 = no false claims, 0.0 = many false claims)
- Tone Appropriateness: Assess if language is professional, engaging, and suitable for retail customers

Provide constructive feedback in comments focusing on specific improvements needed.

Response (JSON only):"""
        
        return prompt
    
    def judge_product_description(self, metadata: Dict[str, Any], description: str) -> Dict[str, Any]:
        """
        Main method to judge a product description against its metadata
        
        Args:
            metadata: Dictionary containing product metadata
            description: Product description string to evaluate
            
        Returns:
            Dictionary containing evaluation results
        """
        try:
            # Create and send prompt to LLM
            prompt = self._create_judge_prompt(metadata, description)
            response = self._call_llama_api(prompt)
            
            # Parse JSON response
            try:
                # Clean response in case there's extra text
                response = response.strip()
                if response.startswith('```json'):
                    response = response[7:-3]
                elif response.startswith('```'):
                    response = response[3:-3]
                
                result = json.loads(response)
                
                # Validate and ensure all required fields exist
                required_fields = ['factual_accuracy', 'hallucination_check', 'tone_appropriateness', 'overall_score', 'comments']
                for field in required_fields:
                    if field not in result:
                        result[field] = 0.0 if field != 'comments' else "Evaluation incomplete"
                
                # Ensure scores are within valid range
                for score_field in ['factual_accuracy', 'hallucination_check', 'tone_appropriateness', 'overall_score']:
                    if score_field in result:
                        result[score_field] = max(0.0, min(1.0, float(result[score_field])))
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {response}")
                
                # Return fallback result
                return {
                    "factual_accuracy": 0.0,
                    "hallucination_check": 0.0,
                    "tone_appropriateness": 0.0,
                    "overall_score": 0.0,
                    "comments": f"Failed to parse evaluation response. Raw response: {response[:200]}..."
                }
                
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return {
                "factual_accuracy": 0.0,
                "hallucination_check": 0.0,
                "tone_appropriateness": 0.0,
                "overall_score": 0.0,
                "comments": f"Evaluation failed due to error: {str(e)}"
            }

# Example usage and testing
def main():
    """Example usage of the LLM Product Judge"""
    
    # Initialize judge with your Databricks credentials
    judge = LLMProductJudge(
        databricks_endpoint="https://adb-439895488707306.6.azuredatabricks.net/serving-endpoints/databricks-llama-4-maverick/invocations",
        api_token="your-databricks-api-token"
    )
    
    # Example product metadata
    sample_metadata = {
        "product_id": "LAPTOP-001",
        "name": "UltraBook Pro 15",
        "category": "Laptops",
        "price": 1299.99,
        "brand": "TechCorp",
        "specifications": {
            "screen_size": "15.6 inches",
            "processor": "Intel i7-12700H",
            "ram": "16GB DDR4",
            "storage": "512GB SSD",
            "graphics": "Intel Iris Xe",
            "battery_life": "up to 10 hours",
            "weight": "3.5 lbs"
        },
        "features": ["Backlit keyboard", "Fingerprint scanner", "USB-C charging"],
        "warranty": "2 years"
    }
    
    # Example product description
    sample_description = """
    The UltraBook Pro 15 is the perfect laptop for professionals and students alike. 
    Featuring a powerful Intel i7 processor and 16GB of RAM, this laptop delivers 
    exceptional performance for multitasking and demanding applications. The stunning 
    15.6-inch display provides crystal-clear visuals, while the 512GB SSD ensures 
    fast boot times and ample storage. With up to 10 hours of battery life, you can 
    work all day without worry. Additional features include a backlit keyboard for 
    typing in low light and a fingerprint scanner for secure access.
    """
    
    # Evaluate the product description
    result = judge.judge_product_description(sample_metadata, sample_description)
    
    # Display results
    print("Product Description Evaluation Results:")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()