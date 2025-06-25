import pandas as pd
import anthropic
from typing import List, Dict, Optional
import json

class ProductTaxonomyClassifier:
    """
    A class to classify products into a hierarchical taxonomy using Claude API.
    
    The taxonomy has 3 levels:
    Level 1 -> Level 2 -> Level 3 -> Attributes with valid values
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the classifier with API key and taxonomy dataframe.
        
        Args:
            api_key (str): Anthropic API key
            taxonomy_df (pd.DataFrame): DataFrame with columns:
                ['level 1 category', 'level 2 category', 'level 3 category', 
                 'attribute', 'valid attribute values']
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.taxonomy_df = self._load_and_clean_taxonomy(pd.read_csv('resources/taxonomy.csv'))
        self.model = "claude-sonnet-4-20250514"

    def _load_and_clean_taxonomy(self, csv_df):
        """Load and clean the taxonomy CSV file."""
        df = csv_df
        
        # Replace NaN values with empty strings
        df = df.fillna('')
        
        # Convert all relevant columns to strings
        string_columns = ['level 1 category', 'level 2 category', 'level 3 category', 'attribute', 'valid attribute values']
        for col in string_columns:
            df[col] = df[col].astype(str)
        
        # Replace any 'nan' strings (from conversion) with empty strings
        for col in string_columns:
            df[col] = df[col].replace('nan', '')
        
        return df
        
    def _make_api_call(self, system_prompt: str, user_message: str) -> str:
        """
        Make a single API call to Claude.
        
        Args:
            system_prompt (str): System prompt for the API call
            user_message (str): User message to send
            
        Returns:
            str: Claude's response
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                max_tokens=500,
                messages=[{
                    "role": "user",
                    "content": user_message
                }]
            )
            
            assistant_message = response.content[0].text.strip()
            return assistant_message
            
        except Exception as e:
            raise Exception(f"API call failed: {str(e)}")
    
    def get_level_3_taxonomy(self, product_description: str) -> str:
        """
        Get level 3 category directly for a product description.
        
        Args:
            product_description (str): Description of the product to classify
            
        Returns:
            str: Selected level 3 category
        """
        # Get all unique level 3 categories
        level_3_options = self.taxonomy_df['level 3 category'].unique().tolist()
        # Remove empty strings if any
        level_3_options = [cat for cat in level_3_options if cat.strip()]
        
        system_prompt = """You are a product classification expert. Your task is to select the most appropriate Level 3 category for a given product description from a provided list of options. 

Level 3 categories are the most specific product categories in our taxonomy. Analyze the product description carefully and select the category that best matches the specific type of product being described.

Return ONLY the exact category name from the list, nothing else. Do not add explanations, quotes, or additional text."""
        
        user_message = f"""Product Description: {product_description}

Available Level 3 Categories:
{chr(10).join([f"- {cat}" for cat in level_3_options])}

Select the most appropriate Level 3 category from the list for this product."""
        
        selected_category = self._make_api_call(system_prompt, user_message)
        
        # Validate the response is in the available options
        if selected_category not in level_3_options:
            # Try to find a close match
            selected_category = self._find_closest_match(selected_category, level_3_options)
        
        return selected_category
    
    def get_parent_categories(self, level_3_category: str) -> tuple:
        """
        Get the parent level 1 and level 2 categories for a given level 3 category.
        
        Args:
            level_3_category (str): Selected level 3 category
            
        Returns:
            tuple: (level_1_category, level_2_category)
        """
        # Find the row with this level 3 category
        matching_rows = self.taxonomy_df[
            self.taxonomy_df['level 3 category'] == level_3_category
        ]
        
        if matching_rows.empty:
            raise ValueError(f"No matching row found for level 3 category: {level_3_category}")
        
        # Get the first matching row (they should all have the same level 1 and 2 for a given level 3)
        first_row = matching_rows.iloc[0]
        level_1_category = first_row['level 1 category']
        level_2_category = first_row['level 2 category']
        
        return level_1_category, level_2_category
    
    def get_attributes(self, level_3_taxonomy: str, product_description: str) -> Dict[str, str]:
        """
        Get attributes and their values for a given level 3 category using a single API call.
        
        Args:
            level_3_taxonomy (str): Selected level 3 category
            product_description (str): Original product description
            
        Returns:
            Dict[str, str]: Dictionary mapping attribute names to selected values
        """
        # Get attributes for the given level 3
        attributes_df = self.taxonomy_df[
            self.taxonomy_df['level 3 category'] == level_3_taxonomy
        ][['attribute', 'valid attribute values']].drop_duplicates()
        
        if attributes_df.empty:
            raise ValueError(f"No attributes found for level 3: {level_3_taxonomy}")
        
        # Build the attributes and their options for the API call
        attribute_options = {}
        attribute_list = []
        
        for _, row in attributes_df.iterrows():
            attribute = row['attribute']
            valid_values = row['valid attribute values']
            
            # Handle case where valid_values might be a string representation of a list
            if isinstance(valid_values, str):
                try:
                    # Try to parse as JSON/list
                    if valid_values.startswith('[') and valid_values.endswith(']'):
                        valid_values_list = json.loads(valid_values)
                    else:
                        # Assume semicolon-separated values
                        valid_values_list = [v.strip() for v in valid_values.split(';')]
                except:
                    # If parsing fails, treat as single value
                    valid_values_list = [valid_values]
            else:
                valid_values_list = [valid_values]
            
            attribute_options[attribute] = valid_values_list
            attribute_list.append(f"{attribute}: {', '.join(valid_values_list)}")
        
        system_prompt = """You are a product classification expert. Based on the product description, choose the most appropriate values for each attribute.

For each attribute:
- If a list of options is provided, select the most appropriate value from those options
- If no list is provided, generate an appropriate value based on the product description
- If you cannot determine an appropriate value, use 'N/A'

Return your response in the following JSON format:
{
    "attribute_name": "selected_value",
    "another_attribute": "selected_value"
}

Return ONLY the JSON object, nothing else."""
        
        # Build the attribute options text
        attributes_text = "\n".join([f"- {attr}" for attr in attribute_list])
        
        user_message = f"""Product Description: {product_description}

Please select appropriate values for each of the following attributes:

{attributes_text}

Return your selections in JSON format as specified."""
        
        response = self._make_api_call(system_prompt, user_message)
        
        # Parse the JSON response
        try:
            # Clean the response in case there are extra characters
            response = response.strip()
            if response.startswith('```json'):
                response = response.replace('```json', '').replace('```', '').strip()
            elif response.startswith('```'):
                response = response.replace('```', '').strip()
            
            selected_attributes = json.loads(response)
            
            # Validate that all expected attributes are present
            for attribute in attribute_options.keys():
                if attribute not in selected_attributes:
                    selected_attributes[attribute] = 'N/A'
            
            return selected_attributes
            
        except json.JSONDecodeError:
            # Fallback: if JSON parsing fails, return N/A for all attributes
            print(f"Warning: Could not parse JSON response: {response}")
            return {attr: 'N/A' for attr in attribute_options.keys()}
    
    def _find_closest_match(self, response: str, valid_options: List[str]) -> str:
        """
        Find the closest match from valid options if exact match not found.
        
        Args:
            response (str): Claude's response
            valid_options (List[str]): List of valid options
            
        Returns:
            str: Best matching option from the valid list
        """
        response_lower = response.lower().strip()
        
        # First try exact match (case insensitive)
        for option in valid_options:
            if option.lower() == response_lower:
                return option
        
        # Then try partial match
        for option in valid_options:
            if response_lower in option.lower() or option.lower() in response_lower:
                return option
        
        # If no match found, return the first option as fallback
        return valid_options[0] if valid_options else response
    
    def classify_product(self, product_description: str) -> Dict:
        """
        Complete classification of a product through all taxonomy levels.
        Uses exactly 2 API calls total: 1 for level 3 category, 1 for all attributes.
        
        Args:
            product_description (str): Description of the product to classify
            
        Returns:
            Dict: Complete classification results
        """
        try:
            # Get level 3 category directly (API call #1)
            level_3 = self.get_level_3_taxonomy(product_description)
            
            # Derive level 1 and 2 from the dataframe (no API calls)
            level_1, level_2 = self.get_parent_categories(level_3)
            
            # Get all attributes at once (API call #2)
            attributes = self.get_attributes(level_3, product_description)
            
            return {
                'product_description': product_description,
                'level_1_category': level_1,
                'level_2_category': level_2,
                'level_3_category': level_3,
                'attributes': attributes
            }
            
        except Exception as e:
            raise Exception(f"Classification failed: {str(e)}")
    
    def classify_product_categories_only(self, product_description: str) -> Dict:
        """
        Classification of a product through taxonomy levels only (no attributes).
        Uses only one API call.
        
        Args:
            product_description (str): Description of the product to classify
            
        Returns:
            Dict: Classification results without attributes
        """
        try:
            # Get level 3 category directly (single API call)
            level_3 = self.get_level_3_taxonomy(product_description)
            
            # Derive level 1 and 2 from the dataframe (no API calls)
            level_1, level_2 = self.get_parent_categories(level_3)
            
            return {
                'product_description': product_description,
                'level_1_category': level_1,
                'level_2_category': level_2,
                'level_3_category': level_3
            }
            
        except Exception as e:
            raise Exception(f"Classification failed: {str(e)}")