# Import necessary libraries
import uuid
import streamlit as st
import requests
from PIL import Image, UnidentifiedImageError
import io
import pandas as pd
import numpy as np
# import response_to_delta_table  # Uncomment if needed

# Helper functions (keep the same as original)
def process_single_row(vendor, item_num, upc):
    """Process a single row for bulk upload"""
    try:
        results_dict = tavily_claude_search(vendor, item_num, upc, bulk=True)[0]
        if results_dict is None:
            return upc, vendor, item_num, "", "", "", "", "", ""
        elif results_dict == "":
            st.error(f"Error querying Claude of Tavily")
            return upc, vendor, item_num, "", "", "", "", "", ""
        else:
            return (
                results_dict["UPC"], 
                results_dict["Vendor"], 
                results_dict["Item_Number"], 
                results_dict["Product_Category"], 
                results_dict["Product_Title"], 
                results_dict["Product_Description"], 
                results_dict["Product_Features"], 
                results_dict["Wholesale_Case_Weight"], 
                results_dict["Wholesale_Case_Dimensions"]
            )
    except Exception as e:
        st.error(f"Error processing item: {str(e)}")
        return upc, vendor, item_num, "", "", "", "", "", ""

def tavily_claude_search(vendor, item_num, upc, bulk=False):
    """
    Uses Tavily to search for product info based on inputs (UPC or Vendor/Item#),
    then uses Claude to generate a description based on Tavily's findings.
    """
    vendor = "" if vendor is None else str(vendor)
    item_num = "" if item_num is None else str(item_num)
    upc = "" if upc is None else str(upc)
    
    # Check if imports worked
    if tavily_extract is None or claude is None:
        st.error("Error: tavily_extract or claude modules not imported successfully.")
        return None, "Error: Required search/generation modules could not be loaded."

    # Initialize clients
    try:
        tavily_client = tavily_extract.upcExtract()
        claude_client = claude.ClaudeQuery()
    except Exception as e:
        st.error(f"Error initializing API clients: {e}")
        return None, f"Error initializing API clients: {e}. Check API keys and dependencies."

    # Input validation
    vendor = vendor.strip() if vendor else None
    item_num = item_num.strip() if item_num else None
    upc = upc.strip() if upc else None

    if not any([vendor, item_num, upc]):
        return None, "Please provide a UPC, or both Vendor and Manufacturer Item Number."

    # Tavily text search
    tavily_output = ""
    try:
        if upc:
            tavily_output = tavily_client.run(upc=upc)
        elif all([vendor, item_num]):
            tavily_output = tavily_client.run(item_num=item_num, manufacturer_name=vendor)
        else:
            return None, "Please provide a UPC, OR provide both Vendor and Manufacturer Item Number."
    except Exception as e:
        st.error(f"Error during Tavily text search: {e}")
        return None, f"An error occurred during the web search. Error: {e}"

    # Process Tavily results & query Claude
    if not tavily_output or tavily_output.strip() == '':
        return None, "No relevant information found via web search for the provided details."
    else:
        try:
            # Pass Tavily results to Claude
            claude_content_blocks, taxonomy = claude_client.search(context=tavily_output)
            claude_text = claude_content_blocks[0]
            
            if isinstance(claude_content_blocks, list):
                for block in claude_content_blocks:
                    if type(block) is Exception:
                        st.error(f"Claude error: {block}")
                        return None
                    if hasattr(block, 'text'):
                        claude_text += block.text + "\n"

            if not claude_text:
                return None, "Web search found information, but could not generate a refined description."
            elif not bulk:
                # For individual items, handle images (simplified for Streamlit)
                product_search_term = f'{claude_text["Product_Title"]}; {claude_text["Vendor"]}, {claude_text["Item_Number"]}'
                
                # Image search (simplified - would need adaptation for Streamlit image display)
                image_html = ""
                try:
                    image_urls = tavily_client.run(queries=product_search_term, include_images=True)
                    if image_urls and isinstance(image_urls, list):
                        # In Streamlit, you'd display images differently
                        # This is a placeholder for the image handling logic
                        image_html = f"Found {len(image_urls)} images"
                except Exception as img_e:
                    image_html = "Error retrieving images"

                final_output = claude_content_blocks[0], image_html, taxonomy
                return final_output
            else:
                return claude_text, None
        except Exception as e:
            st.error(f"Error during Claude query or processing: {e}")
            return None, f"An error occurred while generating the description. Error: {e}"

def get_image_resolution_from_url(image_url):
    """
    Downloads an image from a URL and attempts to extract its resolution (width and height).
    """
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get('content-type')
        if not content_type or not content_type.lower().startswith('image/'):
            return f"Content-Type is '{content_type}', not recognized as an image."

        try:
            img = Image.open(io.BytesIO(response.content))
        except UnidentifiedImageError:
            return f"Could not identify or open image from URL: {image_url}"

        width, height = img.size
        return (width, height) if width and height else "Could not determine image resolution."

    except requests.exceptions.Timeout:
        return f"Error downloading image: Request timed out for URL {image_url}"
    except requests.exceptions.RequestException as e:
        return f"Error downloading image: {e}"
    except IOError:
        return f"Error processing image data from URL: {image_url}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# Assuming tavily_extract and claude are in a 'resources' subfolder
try:
    from resources import tavily_extract
    from resources import claude
except ImportError:
    # st.error("Could not import from 'resources' using relative path. Trying direct import...")
    try:
        import tavily_extract
        import claude
    except ImportError as e:
        st.error(f"Failed to import tavily_extract or claude: {e}")
        tavily_extract = None
        claude = None

# Initialize session state
if 'progress_dict' not in st.session_state:
    st.session_state.progress_dict = {}

# Page configuration
st.set_page_config(
    page_title="Product Content Generation POC",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS for styling
st.markdown("""
<style>
    .header-img {
        max-height: 60px;
        width: auto;
    }
    .title {
        color: #d40029;
        text-align: center;
        margin-bottom: 30px;
    }
    .stButton > button {
        background-color: #d40029;
        color: white;
        border: none;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #b8002a;
    }
    .upload-section {
        border: 2px dashed #ccc;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    # st.image("assets/images/ace-hardware-logo.png", width=200)  # Uncomment if you have the logo
    st.markdown('<h1 class="title">Product Content Generation POC</h1>', unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; color: #666; margin-bottom: 30px;">
    <p>Please enter the product details below. Provide a UPC OR both Vendor and Item #.</p>
    <p>For bulk upload, submit a csv file with the fields: upc, vendor, item_num.</p>
</div>
""", unsafe_allow_html=True)

# Tab selection
tab1, tab2 = st.tabs(["Individual Item Upload", "Bulk Item Upload"])

# Individual Item Tab
with tab1:
    st.markdown("### Enter Product Information")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.markdown("**Vendor:**")
        st.markdown("**Manuf. Item #:**")
        st.markdown("**UPC:**")
    
    with col2:
        vendor = st.text_input("Vendor", placeholder="Enter vendor name...", label_visibility="collapsed")
        item_num = st.text_input("Item Number", placeholder="Enter item number...", label_visibility="collapsed")
        upc = st.text_input("UPC", placeholder="Enter UPC number...", label_visibility="collapsed")
    
    # Buttons
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        generate_btn = st.button("Generate Content", type="primary")
    with col3:
        clear_btn = st.button("Clear Input")
    
    # Clear inputs
    if clear_btn:
        st.rerun()
    
    # Generate content
    if generate_btn:
        if not any([vendor, item_num, upc]):
            st.error("Please provide a UPC, or both Vendor and Manufacturer Item Number.")
        else:
            with st.spinner("Generating content..."):
                try:
                    search_results = tavily_claude_search(vendor, item_num, upc)
                    if search_results and search_results[0]:
                        results_dict = search_results[0]
                        taxonomy_results = search_results[2]
                        
                        # Format attributes
                        markdown_list = []
                        for key, value in taxonomy_results["attributes"].items():
                            markdown_list.append(f"- **{key}**: {value}")
                        formatted_attribute_list = "\n".join(markdown_list)
                        
                        # Format features
                        formatted_features_list = [f"* {s}\n" for s in results_dict["Product_Features"]]
                        
                        # Display results
                        st.markdown(f"# {results_dict['Product_Title']}")
                        
                        st.markdown("**Product Taxonomy**")
                        st.markdown(f"Level 1: {taxonomy_results['level_1_category']}")
                        st.markdown(f"Level 2: {taxonomy_results['level_2_category']}")
                        st.markdown(f"Level 3: {taxonomy_results['level_3_category']}")
                        
                        st.markdown("**Product Attributes**")
                        st.markdown(formatted_attribute_list)
                        
                        st.markdown(results_dict["Product_Description"])
                        
                        st.markdown("**Features:**")
                        st.markdown("".join(formatted_features_list))
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown(f"**Product Weight:** {results_dict['Wholesale_Case_Weight']}")
                            st.markdown(f"**UPC:** {results_dict['UPC']}")
                            st.markdown(f"**Manufacturer Code:** {results_dict['Item_Number']}")
                        with col2:
                            st.markdown(f"**Product Size:** {results_dict['Wholesale_Case_Dimensions']}")
                            st.markdown(f"**Manufacturer:** {results_dict['Vendor']}")
                        
                        # Display images if available
                        if len(search_results) > 1 and search_results[1]:
                            st.markdown("**Images:**")
                            # Note: Images would need to be processed differently in Streamlit
                            st.info("Image display functionality needs to be adapted for Streamlit")
                    else:
                        st.error("No results found or an error occurred during search.")
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")

# Bulk Upload Tab
with tab2:
    st.markdown("### Bulk CSV Upload")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a CSV file with columns: upc, vendor, item_num"
    )
    
    if uploaded_file is not None:
        try:
            # Read and display preview of CSV
            df = pd.read_csv(uploaded_file, dtype=str)
            df = df.replace({np.nan: None})
            
            st.success(f"File uploaded successfully! Found {len(df)} rows.")
            
            # Show preview
            with st.expander("Preview uploaded data", expanded=True):
                st.dataframe(df.head())
            
            # Process button
            if st.button("Process CSV", type="primary"):
                progress_key = str(uuid.uuid4())
                st.session_state.progress_dict[progress_key] = {
                    'current': 0,
                    'total': len(df),
                    'results': [None] * len(df),
                    'finished': False,
                    'csv': None
                }
                
                # Create progress tracking
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Process rows
                args = [(row[1], row[2], row[0]) for _, row in df.iterrows()]
                total = len(args)
                
                def update_progress():
                    current = st.session_state.progress_dict[progress_key]['current']
                    progress = current / total if total > 0 else 0
                    progress_bar.progress(progress)
                    status_text.text(f"Processing: {current}/{total} items completed ({int(progress*100)}%)")
                
                results = []
                for idx, (vendor, item_num, upc) in enumerate(args):
                    try:
                        result = process_single_row(vendor, item_num, upc)
                        results.append(result)
                        st.session_state.progress_dict[progress_key]['current'] = idx + 1
                        update_progress()
                    except Exception as e:
                        st.error(f"Error processing row {idx + 1}: {str(e)}")
                        results.append((upc, vendor, item_num, "", "", "", "", "", ""))
                        st.session_state.progress_dict[progress_key]['current'] = idx + 1
                        update_progress()
                
                # Create results DataFrame
                results_df = pd.DataFrame(results, columns=[
                    "upc_cd", "vendor_nm", "manufacturer_item_num", "taxonomy_cd", 
                    "product_nm", "product_description_txt", "product_features_txt", 
                    "product_weight", "product_dimensions"
                ])
                
                # Add timestamp
                results_df['timestamp'] = pd.Timestamp.now()
                
                # Show completion
                progress_bar.progress(1.0)
                status_text.text("Processing complete!")
                
                # Download button
                csv_data = results_df.to_csv(index=False)
                st.download_button(
                    label="Download Results CSV",
                    data=csv_data,
                    file_name=f"product_results_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                
                # Show results preview
                with st.expander("Preview results", expanded=True):
                    st.dataframe(results_df)
                
                # Uncomment to write to delta table
                # response_to_delta_table.write_dataframe_to_delta_table(
                #     "ai_squad_np.pcg.generated_product_information", results_df
                # )
                
        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")