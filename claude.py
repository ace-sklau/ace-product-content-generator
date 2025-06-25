import anthropic
import json
from typing import Optional, Dict, Any, List
import streamlit as st

class ClaudeQuery:
    def __init__(self, api_key: Optional[str] = None):
        if api_key is None:
            api_key = st.secrets["ANTHROPIC_API_KEY"]
        self.client = anthropic.Anthropic(api_key=api_key)

    def search(self, query: str, context: str = '', 
               model: str = "claude-3-7-sonnet-20250219", temperature: float = 0.8,
               system_prompt: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Execute Claude API call with provided query and return results.
        
        Args:
            query: The query/prompt to send to Claude
            context: Additional context to append to the query
            model: Claude model to use
            temperature: Response creativity (0.0-1.0)
            system_prompt: Optional system prompt override
            
        Returns:
            List of dictionaries containing parsed results, or error if parsing fails
        """
        if system_prompt is None:
            system_prompt = "You are an AI assistant that provides helpful and accurate responses."
        
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=5000,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query + context
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
            
            print("CLAUDE RESPONSE")
            print(self._parse_response(response_text))
            return self._parse_response(response_text)
            
        except Exception as e:
            print(f"Error in API call: {e}")
            return [{"error": str(e)}]

    def _parse_response(self, response_text: str) -> List[Dict[str, Any]]:
        try:
            # Try to parse as single JSON object first
            if response_text.strip().startswith('{'):
                results = json.loads(response_text.strip())
                return [results]
            
            # Try to parse as JSON array
            elif response_text.strip().startswith('['):
                results = json.loads(response_text.strip())
                return results
            
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
                
                # If no JSON found, return the raw text
                if not results:
                    return [{"response": response_text}]
                
                return results
                
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response text: {response_text[:500]}...")
            # Return raw text if JSON parsing fails
            return [{"response": response_text, "parse_error": str(e)}]

    def get_raw_response(self, query: str, context: str = '', 
                        model: str = "claude-3-7-sonnet-20250219", temperature: float = 0.8,
                        system_prompt: Optional[str] = None) -> str:
        """
        Execute Claude API call and return raw text response without parsing.
        
        Args:
            query: The query/prompt to send to Claude
            context: Additional context to append to the query
            model: Claude model to use
            temperature: Response creativity (0.0-1.0)
            system_prompt: Optional system prompt override
            
        Returns:
            Raw text response from Claude
        """
        if system_prompt is None:
            system_prompt = "You are an AI assistant that provides helpful and accurate responses."
        
        try:
            message = self.client.messages.create(
                model=model,
                max_tokens=5000,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": query + context
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
            
            return response_text
            
        except Exception as e:
            print(f"Error in API call: {e}")
            return f"Error: {str(e)}"