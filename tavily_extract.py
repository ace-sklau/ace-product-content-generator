import asyncio
from tavily import AsyncTavilyClient
import requests
import os


class upcExtract:

    def __init__(self):
        # self.tavily_client = AsyncTavilyClient(api_key="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") # old key tied to sklau@aceharde.com personal account
        self.tavily_client = AsyncTavilyClient(api_key=os.environ["TAVILY_API_KEY"]) # Prod key tied to corp account, 1000 rpmin and 19000 rpmonth

    def get_failed_url_content(self, url): # this works well when tavily_client.search(**q) fails to load a given url, but its a higher token cost since it is the entire content of the webpage
        payload = {
            "urls": url,
            "include_images": False,
            "extract_depth": "advanced"
        }
        headers = {
            "Authorization": "Bearer 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",
            "Content-Type": "application/json"
        }

        response = requests.request("POST", url, json=payload, headers=headers)

        return(response.text)


    async def fetch_and_extract(self, upc='', queries=None, include_images=False, item_num=None, manufacturer_name=None, short_description=None):
        # Define the queries with search_depth and max_results inside the query dictionary
        if upc != '' and not include_images:
            queries = [
            {"query": "What product corresponds to the UPC/EAN code " + upc + "?", "search_depth": "advanced", "max_results": 2, "include_images": include_images, "exclude_domains": [("www.acehardware.com")]},
            {"query": "product information UPC EAN " + upc + "", "search_depth": "advanced", "max_results": 2, "include_images": include_images, "exclude_domains": [("www.acehardware.com")]},
            {"query": "UPC EAN lookup " + upc + "", "search_depth": "advanced", "max_results": 2, "include_images": include_images, "exclude_domains": [("www.acehardware.com")]},
            {"query": "UPC " + upc + " product", "search_depth": "advanced", "max_results": 2, "include_images": include_images, "exclude_domains": [("www.acehardware.com")]},
            {"query": "EAN " + upc + " product", "search_depth": "advanced", "max_results": 2, "include_images": include_images, "exclude_domains": [("www.acehardware.com")]}
            ]
        elif upc == '' and not include_images:

            queries = [
            {"query": f'Find product details for {manufacturer_name} item number "{item_num}"', "search_depth": "advanced", "max_results": 5, "exclude_domains": [("www.acehardware.com")]},
            {"query": f'"{manufacturer_name}" "{item_num}"', "search_depth": "advanced", "max_results": 5, "exclude_domains": [("www.acehardware.com")]},
            {"query": f'"{manufacturer_name}" "{item_num}" MPN', "search_depth": "advanced", "max_results": 5, "exclude_domains": [("www.acehardware.com")]}           
            ]
        elif include_images:
            queries = [
                {"query": 'High resolution image of ' + str(queries), "search_depth": "basic", "max_results": 20, "include_images": include_images, "exclude_domains": [("www.acehardware.com")]}
            ]
        # Perform the search queries concurrently, passing the entire query dictionary
        responses = await asyncio.gather(*[self.tavily_client.search(**q) for q in queries])

        relevant_urls = []
        output = ""

        if include_images:
            for response in responses:
                for image in response['images']:
                    relevant_urls.append(image)
            return relevant_urls

        # Filter URLs with a score greater than 0.5. Alternatively, you can use a re-ranking model or an LLM to identify the most relevant sources, or cluster your documents and extract content only from the most relevant cluster
        for response in responses:
            for result in response.get('results', []):
                if result.get('score', 0) > 0.5:
                    output += f"Item title: {result['title']}, Item Information: {result['content']}; "            

        return output
    
    def run(self, upc='', queries=None, include_images=False, item_num=None, manufacturer_name=None, short_description=None):
        output = asyncio.run(self.fetch_and_extract(upc=upc, queries=queries, include_images=include_images, item_num=item_num, manufacturer_name=manufacturer_name, short_description=short_description))
        return output
