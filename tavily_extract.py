import asyncio
from tavily import AsyncTavilyClient
import requests
import os

class upcExtract:

    def __init__(self, api_key: str):
        self.tavily_client = AsyncTavilyClient(api_key) # Prod key tied to corp account, 1000 rpmin and 19000 rpmonth

    async def search_by_upc_ean(self, upc):
        queries = [
            {"query": "What product corresponds to the UPC/EAN code " + upc + "?", "search_depth": "advanced", "max_results": 2, "include_images": False, "exclude_domains": [("www.acehardware.com")]},
            {"query": "product information UPC EAN " + upc + "", "search_depth": "advanced", "max_results": 2, "include_images": False, "exclude_domains": [("www.acehardware.com")]},
            {"query": "UPC EAN lookup " + upc + "", "search_depth": "advanced", "max_results": 2, "include_images": False, "exclude_domains": [("www.acehardware.com")]},
            {"query": "UPC " + upc + " product", "search_depth": "advanced", "max_results": 2, "include_images": False, "exclude_domains": [("www.acehardware.com")]},
            {"query": "EAN " + upc + " product", "search_depth": "advanced", "max_results": 2, "include_images": False, "exclude_domains": [("www.acehardware.com")]}
        ]
        
        # Perform the search queries concurrently
        responses = await asyncio.gather(*[self.tavily_client.search(**q) for q in queries])
        
        output = ""
        # Filter URLs with a score greater than 0.5
        for response in responses:
            for result in response.get('results', []):
                if result.get('score', 0) > 0.5:
                    output += f"Item title: {result['title']}, Item Information: {result['content']}; "            

        return output

    async def search_by_vendor_item(self, item_num, manufacturer_name):
        queries = [
            {"query": f'Find product details for {manufacturer_name} item number "{item_num}"', "search_depth": "advanced", "max_results": 5, "exclude_domains": [("www.acehardware.com")]},
            {"query": f'"{manufacturer_name}" "{item_num}"', "search_depth": "advanced", "max_results": 5, "exclude_domains": [("www.acehardware.com")]},
            {"query": f'"{manufacturer_name}" "{item_num}" MPN', "search_depth": "advanced", "max_results": 5, "exclude_domains": [("www.acehardware.com")]}           
        ]
        
        # Perform the search queries concurrently
        responses = await asyncio.gather(*[self.tavily_client.search(**q) for q in queries])
        
        output = ""
        # Filter URLs with a score greater than 0.5
        for response in responses:
            for result in response.get('results', []):
                if result.get('score', 0) > 0.5:
                    output += f"Item title: {result['title']}, Item Information: {result['content']}; "            

        return output

    async def search_images(self, search_query):
        queries = [
            {"query": 'High resolution image of ' + str(search_query), "search_depth": "basic", "max_results": 20, "include_images": True, "exclude_domains": [("www.acehardware.com")]}
        ]
        
        # Perform the search queries concurrently
        responses = await asyncio.gather(*[self.tavily_client.search(**q) for q in queries])

        relevant_urls = []
        for response in responses:
            for image in response['images']:
                relevant_urls.append(image)
                
        return relevant_urls

    # Convenience wrapper methods that can be called synchronously
    def run_upc_search(self, upc):
        return asyncio.run(self.search_by_upc_ean(upc))

    def run_vendor_item_search(self, item_num, manufacturer_name):
        return asyncio.run(self.search_by_vendor_item(item_num, manufacturer_name))

    def run_image_search(self, search_query):
        return asyncio.run(self.search_images(search_query))