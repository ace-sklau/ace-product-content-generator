# Import necessary libraries
import threading
import uuid
import re
import concurrent.futures
import ast
import dash
import requests
from PIL import Image, UnidentifiedImageError
import io
import base64
import pandas as pd
import numpy as np
import response_to_delta_table
# Import dash_bootstrap_components first to ensure its CSS loads before potential custom styles
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback # Import directly
from datetime import datetime
# Assuming tavily_extract and claude are in a 'resources' subfolder
# If they are in the same directory, change imports back
try:
    # Use relative import if files are in the same package/directory structure
    from .resources import tavily_extract # Import Tavily client
    from .resources import claude         # Import Claude client
except ImportError:
    print("Could not import from 'resources' using relative path. Trying direct import...")
    try:
        import tavily_extract
        import claude
    except ImportError as e:
         print(f"Failed to import tavily_extract or claude: {e}")
         # Set them to None to handle gracefully in the callback
         tavily_extract = None
         claude = None

# Global dictionary to track progress for each upload (per user session)
progress_dict = {}

dcc_upload = dcc.Upload(
    id='upload-data',
    children=html.Div([
        'Upload CSV...'
    ]),
    style={
        'width': '100%',
        'height': '60px',
        'lineHeight': '60px',
        'borderWidth': '1px',
        'borderStyle': 'dashed',
        'borderRadius': '5px',
        'textAlign': 'center',
        'margin': '10px'
    },
    multiple=False
)
# Initialize the Dash app with a Bootstrap theme and suppress callback exceptions
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    # Define the assets folder if your image is there
    assets_folder='assets'
)

# --- App Layout ---
app.layout = dbc.Container([
    html.Div([
        html.Img(src="assets/images/ace-hardware-logo.png", alt="logo", className="header-img"),
        html.H1("Product Content Generation POC", className="title"),
    ], className="header container-fluid"),
    dbc.Row([
        dbc.Col([
            html.P(
                "Please enter the product details below. Provide a UPC OR both Vendor and Item #.",
                className="text-center text-muted" # Center text, make it muted, add margin bottom
            ),
            html.P(
                "For bulk upload, submit a csv file with the fields; upc, vendor, item_num.",
                className="text-center text-muted mb-4" # Center text, make it muted, add margin bottom
            )
        ])
    ]),
    dbc.Tabs(id="tabs", active_tab='tab-individual', children=[
        dbc.Tab(label='Individual Item Upload', tab_id='tab-individual'),
        dbc.Tab(label='Bulk Item Upload', tab_id='tab-bulk'),
    ]),
    html.Div(id='tabs-content', className='mt-4')
], fluid=True)

# --- Tab Layout ---
individual_tab_layout = dbc.Container([
    # Input Form Section
    html.Div([
        # Input Row 1: Vendor
        dbc.Row([
            dbc.Col(dbc.Label("Vendor:", html_for='vendor-input', className="fw-bold"), width=2, className="text-end"), # Right-align label
            dbc.Col(
                dbc.Input(id='vendor-input', type='text', placeholder='Enter vendor name...'),
                width=9 # Adjust width
            ),
        ], className="mb-3 align-items-center"), # Vertically align items, add margin bottom

        # Input Row 2: Item Number
        dbc.Row([
            dbc.Col(dbc.Label("Manuf. Item #:", html_for='item-num-input', className="fw-bold"), width=2, className="text-end"),
            dbc.Col(
                dbc.Input(id='item-num-input', type='text', placeholder='Enter item number...'),
                 width=9
            ),
        ], className="mb-3 align-items-center"),

        # Input Row 3: UPC
        dbc.Row([
            dbc.Col(dbc.Label("UPC:", html_for='upc-input', className="fw-bold"), width=2, className="text-end"),
            dbc.Col(
                dbc.Input(id='upc-input', type='text', placeholder='Enter UPC number...'),
                 width=9
            ),
        ], className="mb-3 align-items-center"),

        # Row for Buttons
        dbc.Row([
            dbc.Col([ # Wrap buttons in a Col for centering
                dbc.Button(
                    'Generate Content',
                    id='submit-button-state',
                    n_clicks=0,
                    color="primary",
                    style={'backgroundColor': '#d40029', 'borderColor': '#d40029'},
                    className="ms-1 shadow-sm" # Add margin right and shadow
                ),
                dbc.Button(
                    'Clear Input',
                    id='clear-button-state',
                    n_clicks=0,
                    color="secondary",
                    outline=True, # Make clear button less prominent
                    style={'borderColor': '#d40029'},
                    className="ms-1 shadow-sm" # Add margin left and shadow
                ),
            ], width={"size": 10, "offset": 1}, className="text-center") # Center buttons within the column
        ], className="mb-4"), # Add margin bottom

        # Output Area with Loading Spinner
        dbc.Row([
            dbc.Col(
                # Wrap the Markdown output with dcc.Loading
                dcc.Loading(
                    id="loading-output",
                    type="default", # Options: "graph", "cube", "circle", "dot", "default"
                    children=[
                         # Use dcc.Markdown to display the output text
                         # *** Added dangerously_allow_html=True to render images ***
                         dcc.Markdown(
                             id='output-paragraph',
                             className="mt-4 p-3 border rounded bg-light shadow-sm", # Add padding, border, background, rounding, shadow
                             dangerously_allow_html=True, # NEEDED TO RENDER HTML IMG TAGS
                             style={'overflowWrap': 'break-word', 'whiteSpace': 'pre-wrap', 'minHeight': '100px'} # Ensure minimum height
                         )
                    ]
                ),
                 width={"size": 10, "offset": 1} # Center output area
            )
        ])
    ], className="mid container-fluid px-4"), # Add horizontal padding
], fluid=True, className="bg-light") # Set a light background for the whole container
bulk_tab_layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            # New inner Row to arrange Button and Upload component horizontally
            dbc.Row([
                # Column for the Button
                dbc.Col([
                    dcc.Upload(
                        id='upload-data', # This ID will be the primary trigger via the "button"
                        children=html.Div('Select CSV File'),
                        style={
                            'width': '100%',
                            'height': '100%', # Aims to match the height of the dropzone via align="stretch"
                            'backgroundColor': '#d40029',
                            'borderColor': '#d40029',
                            'color': 'white', # Text color for visibility against the red background
                            'borderRadius': '5px', # Consistent with other elements
                            'display': 'flex',
                            'alignItems': 'center',
                            'justifyContent': 'center',
                            'textAlign': 'center',
                            'cursor': 'pointer',
                            'padding': '0.375rem 0.75rem', # Standard Bootstrap button padding
                            # 'lineHeight': '1.5', # Standard Bootstrap button line height, flex handles alignment
                        },
                        multiple=False # Allow only a single file upload
                    )
                ], width=4, className="pe-2"), # Use pe-2 (padding-end) for spacing on right
                
                # Column for the Upload component
                dbc.Col([
                    dcc.Upload(
                        id='upload-data-dropzone',
                        children=html.Div('Drag and Drop CSV file here'),
                        style={
                            'width': '100%', # Upload component takes full width of this column
                            'height': '100%', # Attempt to match button height (may need adjustment)
                            'lineHeight': '35px', # Keep for vertical centering of text if button is taller
                            'borderWidth': '1px', 
                            'borderStyle': 'dashed', 
                            'borderRadius': '5px',
                            'textAlign': 'center',
                            'display': 'flex', # Use flex to help center content
                            'alignItems': 'center',
                            'justifyContent': 'center'
                        },
                        multiple=False
                    )
                ], width=8, className="ps-2") # Use ps-2 (padding-start) for spacing on left
            ], align="stretch") # align="stretch" helps make both columns same height, or use "center"
        ], width={"size": 10, "offset": 1}) # Outer column for centering the whole block
    ], className='mb-4'),
    dbc.Row([
        dbc.Col([
            dbc.Progress(id='progress-bar', value=0, max=100, animated=True, striped=True, style={'height': '30px', 'marginBottom': '15px'}),
            dcc.Interval(id='progress-interval', interval=800, n_intervals=0),  # poll every 0.8s
            dcc.Store(id='progress-key', data=None),
            html.Div(id='upload-status', className='mt-2'),
            dbc.Button('Process CSV', id='process-csv-btn', n_clicks=0, style={'backgroundColor': '#d40029', 'borderColor': '#d40029'}, className="ms-1 shadow-sm"),
            dcc.Download(id='download-results'),
            dcc.Store(id='downloaded', data=False),
        ], width={"size": 10, "offset": 1}, className="text-center")
    ])
    
])

# --- Callbacks ---

# Callback to handle tab changes
@callback(
    Output('tabs-content', 'children'),
    Input('tabs', 'active_tab')
)
def render_content(tab):
    if tab == 'tab-individual':
        return individual_tab_layout
    elif tab == 'tab-bulk':
        return bulk_tab_layout

# Callback to handle content generation using Tavily and Claude
@callback(
    Output('output-paragraph', 'children'), # Target the Markdown component's children
    Input('submit-button-state', 'n_clicks'),
    State('vendor-input', 'value'),
    State('item-num-input', 'value'),
    State('upc-input', 'value'),
    prevent_initial_call=True # Prevent callback firing on page load
)
def single_item_search(submit_clicks, vendor, item_num, upc, bulk=False):
    search_results = tavily_claude_search(vendor, item_num, upc)
    results_dict = search_results[0]
    taxonomy_results = search_results[2]
    markdown_list = []
    for key, value in taxonomy_results["attributes"].items():
        markdown_list.append(f"- **{key}**: {value}")
        formated_attribute_list = "\n".join(markdown_list)
    formated_features_list = [f"* {s}\n" for s in results_dict["Product_Features"]]
    results_images = search_results[1]
    output_string = f"""
# {results_dict["Product_Title"]}

**Product Taxonomy**
Level 1: {taxonomy_results["level_1_category"]}
Level 2: {taxonomy_results["level_2_category"]}
Level 3: {taxonomy_results["level_3_category"]}

**Product Atrributes**
{formated_attribute_list}

{results_dict["Product_Description"]}

**Features:**
{"".join(formated_features_list)}

**Product Weight:** {results_dict["Wholesale_Case_Weight"]}
**Product Size:** {results_dict["Wholesale_Case_Dimensions"]}
**UPC:** {results_dict["UPC"]}  
**Manufacturer:** {results_dict["Vendor"]}   
**Manufacturer Code:** {results_dict["Item_Number"]} 
"""
    return output_string, results_images

# Callback to handle csv processing
@callback(
    Output('progress-key', 'data'),
    Input('process-csv-btn', 'n_clicks'),
    State('upload-data', 'contents'),
    State('upload-data', 'filename'),
    State('upload-data-dropzone', 'contents'),
    State('upload-data-dropzone', 'filename'),
    prevent_initial_call=True
)
def start_bulk_processing(n_clicks, contents_button, filename_button, contents_dropzone, filename_dropzone):
    if contents_button is None and contents_dropzone is None:
        raise dash.exceptions.PreventUpdate
    if contents_dropzone is None:
        content_type, content_string = contents_button.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), dtype=str)
        df = df.replace({np.nan: None})
    else:
        content_type, content_string = contents_dropzone.split(',')
        decoded = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')), dtype=str)
        df = df.replace({np.nan: None})
    
    args = [(row[1], row[2], row[0]) for _, row in df.iterrows()]
    total = len(args)
    
    # Create a unique key for this upload
    progress_key = str(uuid.uuid4())
    progress_dict[progress_key] = {
        'current': 0, 'total': total, 'results': [None]*total, 'finished': False, 'csv': None
    }
    
    def worker(idx, arg):
        result = process_single_row(*arg)
        progress_dict[progress_key]['results'][idx] = result
        progress_dict[progress_key]['current'] += 1
        return result
    
    def thread_target():
        try:
            # Use ThreadPoolExecutor to limit concurrent threads
            max_workers = 5  # Adjust this number based on your needs
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_idx = {executor.submit(worker, idx, arg): idx for idx, arg in enumerate(args)}
                
                # Wait for completion
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        print(f'Row {idx} generated an exception: {exc}')
            
            # All rows done: prepare CSV for download
            results = progress_dict[progress_key]['results']
            print(results)
            results_df = pd.DataFrame(results, columns=[
                "upc_cd", "vendor_nm", "manufacturer_item_num", "taxonomy_cd", "product_nm", 
                "product_description_txt", "product_features_txt", "product_weight", "product_dimensions"
            ])
            csv = results_df.to_csv(index=False)
            progress_dict[progress_key]['csv'] = csv
            progress_dict[progress_key]['finished'] = True
            results_df['timestamp'] = pd.Timestamp.now()
            # response_to_delta_table.write_dataframe_to_delta_table("ai_squad_np.pcg.generated_product_information", results_df)
            
        except Exception as e:
            print(f"Error in thread_target: {e}")
            progress_dict[progress_key]['finished'] = True
    
    threading.Thread(target=thread_target, daemon=True).start()
    return progress_key

# --- Callback to poll progress and update progress bar ---
@callback(
    Output('progress-bar', 'value'),
    Output('progress-bar', 'label'),
    Output('progress-bar', 'color'),
    Input('progress-interval', 'n_intervals'),
    State('progress-key', 'data'),
    prevent_initial_call=True
)
def update_progress_bar(n_intervals, progress_key):
    if not progress_key or progress_key not in progress_dict:
        raise dash.exceptions.PreventUpdate
    prog = progress_dict[progress_key]
    total, current = prog['total'], prog['current']
    percent = int((current / total) * 100) if total else 0
    color = 'success' if prog['finished'] else 'info'
    return percent, f"{percent}% Complete", color

# --- Callback to auto-download when finished ---
@callback(
    Output('download-results', 'data'),
    Output('downloaded', 'data'),
    Input('progress-bar', 'value'),
    State('progress-key', 'data'),
    State('downloaded', 'data'),
    prevent_initial_call=True
)
def auto_download_csv(progress_value, progress_key, downloaded):
    if not progress_key or progress_key not in progress_dict or downloaded:
        raise dash.exceptions.PreventUpdate
    prog = progress_dict[progress_key]
    if not prog['finished'] or not prog['csv']:
        raise dash.exceptions.PreventUpdate
    # Only trigger download once!
    #print(prog['csv'])
    return dict(content=prog['csv'], filename='results.csv'), True

# Callback to update screen after CSV upload
@callback( # Using dash.callback for a more self-contained example if app isn't in this snippet
    Output('upload-status', 'children'),
    [Input('upload-data', 'contents'),
     Input('upload-data-dropzone', 'contents')],
    [State('upload-data', 'filename'),
     State('upload-data-dropzone', 'filename')],
    prevent_initial_call=True
)
def update_upload_status(contents_button, contents_dropzone, filename_button, filename_dropzone):

    ctx = dash.callback_context # Requires 'import dash' or 'from dash import callback_context'
    
    contents = None
    filename = None
    message = "Please select a CSV file using either method."

    if not ctx.triggered:
        # Should not happen with prevent_initial_call=True, but good for robustness
        return message
    
    # Get the ID of the component that triggered the callback
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == 'upload-data':
        contents = contents_button
        filename = filename_button
    elif triggered_id == 'upload-data-dropzone':
        contents = contents_dropzone
        filename = filename_dropzone
    # Fallback if triggered_id isn't clear or for older Dash versions (less precise)
    elif contents_button is not None:
        contents = contents_button
        filename = filename_button
    elif contents_dropzone is not None:
        contents = contents_dropzone
        filename = filename_dropzone

    if contents is not None:
        # You would typically parse the contents here (e.g., base64 decode, read into pandas)
        # For this example, we're just confirming the file selection.
        message = dbc.Alert(f"Uploaded file: {filename}", color="success")
    
    return message

# Callback to handle clearing inputs (Clear button)
@callback(
    Output('vendor-input', 'value'),
    Output('item-num-input', 'value'),
    Output('upc-input', 'value'),
    Input('clear-button-state', 'n_clicks'),
    prevent_initial_call=True
)
def clear_inputs(clear_clicks):
    """
    Clears the text in all input fields when the Clear button is clicked.
    """
    return "", "", ""

# Miscellaneous functions
def process_single_row(vendor, item_num, upc):
    # return None
    results_dict = tavily_claude_search(vendor, item_num, upc, bulk=True)[0]
    if results_dict is None:
        return upc, vendor, item_num,  "", "", "", "", "", ""
    else:
        return results_dict["UPC"], results_dict["Vendor"], results_dict["Item_Number"], results_dict["Product_Category"], results_dict["Product_Title"], results_dict["Product_Description"], results_dict["Product_Features"], results_dict["Wholesale_Case_Weight"], results_dict["Wholesale_Case_Dimensions"]

def tavily_claude_search(vendor, item_num, upc, bulk=False):
    vendor = "" if vendor is None else str(vendor)
    item_num = "" if item_num is None else str(item_num)
    upc = "" if upc is None else str(upc)
    """
    Uses Tavily to search for product info based on inputs (UPC or Vendor/Item#),
    then uses Claude to generate a description based on Tavily's findings.
    Finally, uses the start of the Claude description to search for images via Tavily
    and displays the description followed by the images.
    """
    # Check if imports worked
    if tavily_extract is None or claude is None:
        print("Error: tavily_extract or claude modules not imported successfully.")
        return None, "Error: Required search/generation modules could not be loaded. Check server logs."

    # Initialize clients within the callback
    try:
        tavily_client = tavily_extract.upcExtract()
        claude_client = claude.ClaudeQuery()
    except Exception as e:
        print(f"Error initializing API clients: {e}")
        return None, f"Error initializing API clients: {e}. Check API keys and dependencies."

    # --- Input Validation ---
    vendor = vendor.strip() if vendor else None
    item_num = item_num.strip() if item_num else None
    upc = upc.strip() if upc else None

    if not any([vendor, item_num, upc]):
        return None, "Please provide a UPC, or both Vendor and Manufacturer Item Number."

    # --- Tavily Text Search ---
    tavily_output = ""
    print("Starting Tavily text search...")
    try:
        if upc:
            print(f"  Searching Tavily with UPC: '{upc}'")
            tavily_output = tavily_client.run(upc=upc)
        elif all([vendor, item_num]):
            print(f"  Searching Tavily with: Item='{item_num}', Manuf='{vendor}'")
            tavily_output = tavily_client.run(item_num=item_num, manufacturer_name=vendor)
        else:
             print("  Insufficient data provided. Need UPC or both Vendor and Item #.")
             return None, "Please provide a UPC, OR provide both Vendor and Manufacturer Item Number."
        print("Tavily text search complete.")
    except Exception as e:
        print(f"Error during Tavily text search: {e}")
        return None, f"An error occurred during the web search. Please check the console for details. Error: {e}"

    # --- Process Tavily Results & Query Claude ---
    if not tavily_output or tavily_output.strip() == '':
        print("  Tavily returned no results.")
        return None, "No relevant information found via web search for the provided details."
    else:
        print("  Tavily search successful. Querying Claude...")
        try:
            # Pass Tavily results to Claude 
            claude_content_blocks, taxonomy = claude_client.search(context=tavily_output)
            # Extract text content from the list of blocks returned by claude.py
            claude_text = claude_content_blocks[0]
            if isinstance(claude_content_blocks, list):
                 for block in claude_content_blocks:
                     if type(block) is Exception:
                         print(block)
                         return None
                     if hasattr(block, 'text'):
                         claude_text += block.text + "\n"
            else:
                print(f"Warning: Unexpected response format from Claude: {type(claude_content_blocks)}")
            print("  Claude query complete.")

            if not claude_text:
                print("  Claude returned no description (or text extraction failed).")
                return None, "Web search found information, but could not generate a refined description."
            elif not bulk:
                # --- Get succint item name for tavily image search ---
                product_search_term = f'{claude_text["Product_Title"]}; {claude_text["Vendor"]}, {claude_text["Item_Number"]}'
                # --- Tavily Image Search (using Claude's output) ---
                image_html = "" # Initialize empty string for image HTML
                print("  Starting Tavily image search based on Claude description...")
                try:
                    image_query = product_search_term
                    print(f"    Image search query for: '{image_query}'")

                    # Call Tavily run method requesting images
                    image_urls = tavily_client.run(queries=image_query, include_images=True)
                    print(image_urls)
                    for url in image_urls:
                        print(get_image_resolution_from_url(url))
                    if image_urls and isinstance(image_urls, list):
                        print(f"    Found {len(image_urls)} images.")
                        # Generate HTML for the image container and images
                        image_html = "<hr/><p><strong>Images:</strong></p>"
                        # Add a container div with flex properties for horizontal layout
                        image_html += "<div style='display: flex; flex-direction: row; flex-wrap: wrap; justify-content: flex-start; align-items: center;'>" # Flex container
                        image_html += ''.join(
                            f'<img src="{url}" alt="Product Image" '
                            # Individual image styling (display:inline-block removed as flex handles it)
                            f'style="max-width:150px; height:auto; margin: 5px; border-radius: 8px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);" '
                            f'onerror="this.style.display=\'none\'"/>'
                            for url in image_urls
                        )
                        image_html += "</div>" # Close flex container
                    else:
                        print("    No images found or invalid response from Tavily image search.")

                except Exception as img_e:
                    print(f"    Error during Tavily image search: {img_e}")
                    # Don't fail the whole request, just skip images
                    image_html = "\n\n(Error retrieving images)"


                # Combine Claude's text and the image HTML
                # Use Markdown line breaks (\n\n) before appending HTML if needed. Commented out the images since they are not needed at the moment
                # final_output = f"{claude_text}\n\n{image_html}"
                final_output = claude_content_blocks[0], image_html, taxonomy
                processed_data = [(upc,vendor,item_num,claude_text,image_html)]  
                
                # response_to_delta_table.write_to_delta_table("ai_squad_np.pcg.product_content_response_history", processed_data)
                return final_output
            else:
                return claude_text, None
        except Exception as e:
            print(f"Error during Claude query or processing: {e}")
            return None, f"An error occurred while generating the description. Please check the console for details. Error: {e}"

def get_image_resolution_from_url(image_url):
    """
    Downloads an image from a URL and attempts to extract its resolution (width and height).

    Args:
        image_url (str): The URL of the image.

    Returns:
        tuple: A tuple (width, height) in pixels if resolution is found.
               Returns a string with an error message if the download or processing fails.
               Returns None if the content type is not recognized as an image and processing is skipped.
    """
    try:
        # Send a GET request to the image URL
        # Use a timeout to prevent hanging indefinitely
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Check if the content type is an image
        content_type = response.headers.get('content-type')
        if not content_type or not content_type.lower().startswith('image/'):
            # If not an image, return an informative message or None
            return f"Content-Type is '{content_type}', not recognized as an image. Cannot get resolution."

        # Open the image from the response content
        try:
            img = Image.open(io.BytesIO(response.content))
        except UnidentifiedImageError:
            # Handle cases where Pillow cannot identify the image format
            return f"Could not identify or open image from URL: {image_url}. The file may be corrupted or not a supported image format."

        # Get the image resolution (width, height)
        # The 'size' attribute of a Pillow Image object returns a (width, height) tuple
        width, height = img.size

        if width is not None and height is not None:
            return (width, height)
        else:
            # This case should ideally not be reached if img.size is always populated
            # for a successfully opened image, but kept for robustness.
            return "Could not determine image resolution, though image was opened."

    except requests.exceptions.Timeout:
        return f"Error downloading image: Request timed out for URL {image_url}"
    except requests.exceptions.RequestException as e:
        return f"Error downloading image: {e}"
    except IOError: # Catch general Pillow I/O errors during open or processing
        return f"Error processing image data from URL: {image_url}. Could not read image."
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# --- Run the App ---
if __name__ == '__main__':
    # Run the app server
    app.run(debug=True, host='127.0.0.1', port=8050)
