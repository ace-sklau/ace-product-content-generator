"""
Key Features:

Single Product Flow: All steps work on one product through the entire pipeline
Mock Processing Functions: Each step has its own processing function that you can replace with your actual logic:

process_taxonomy() - for taxonomy classification
process_attributes() - for attribute extraction/population
process_content() - for title, romance text, and features generation


Step-by-Step Modification: Users can review and edit results at each stage
Progress Tracking: Sidebar shows current progress and allows quick navigation
Data Persistence: All modifications are saved in st.session_state.product_data

Customization Points:

Replace the mock functions with your actual API calls or processing logic
Modify the form fields in each step to match your specific data requirements
Adjust the categories, options, and validation rules as needed
Customize the final results display format

The app maintains all user modifications throughout the workflow and provides a comprehensive final summary with export capabilities. Each step builds upon the previous one, creating a complete product processing pipeline.
"""

import streamlit as st
import time
import tavily_extract
import claude
import taxonomy

product_content = None

initial_claude_query = """
You create product data about new products that will be put onto the AceHardware website for sale. 
When generating the product data, please use concise description for each product, highlighting the products features and benefits of use.
Also include a list of features of the product (in bullet format) and do not list the price for the product. 
Finally include the UPC and the manufacturer name (and manufacturer code). 

Structure the response as valid JSON with the following fields:
- UPC: item upc/ean code
- Vendor: vendor/manufacturer name
- Item_Number: manufacturer item/model number
- Product_Title: concise product title
- Product_Description: detailed product description
- Product_Features: array of all features

Return only valid JSON without any formatting indicators or additional text.

Use the following product information to produce this content:
"""

final_claude_query = """
You create product data about new products that will be put onto the AceHardware website for sale. 
When generating the product data, please use concise description for each product, highlighting the products features and benefits of use.
Also include a list of features of the product (in bullet format) and do not list the price for the product. 
Finally include the UPC and the manufacturer name (and manufacturer code). 

Structure the response as valid JSON with the following fields:
- Product_Description: detailed product description
- Product_Features: array of all features, including references to provided attributes if possible

Return only valid JSON without any formatting indicators or additional text.

Use the following product information to produce this content:
"""

tavily_client = tavily_extract.upcExtract(api_key=st.secrets["TAVILY_API_KEY"])
claude_client = claude.ClaudeQuery(api_key=st.secrets["ANTHROPIC_API_KEY"])
taxonomy_classifier = taxonomy.ProductTaxonomyClassifier(api_key=st.secrets["ANTHROPIC_API_KEY"])

# Configure page
st.set_page_config(page_title="Product Processing App", layout="wide")
    

# Initialize session state
if 'page' not in st.session_state:
    st.session_state.page = 'input'
if 'current_step' not in st.session_state:
    st.session_state.current_step = 1
if 'product_data' not in st.session_state:
    st.session_state.product_data = {}

# Mock functions to simulate processing steps
def initial_product_lookup(upc_ean=None, manufacturer=None, item_number=None):
  
    if upc_ean:
        tavily_search = tavily_client.run_upc_search(upc=upc_ean)
        if tavily_search == "":
            return ""
        else:
            return claude_client.search(initial_claude_query, tavily_search)
    else:
        tavily_search = tavily_client.run_vendor_item_search(item_num=item_number, manufacturer_name=manufacturer)
        if tavily_search == "":
            return ""
        else:
            return claude_client.search(initial_claude_query, tavily_search)

def process_taxonomy(product_data):
    return taxonomy_classifier.classify_product(str(product_data))

def process_attributes(product_data, taxonomy_data):
    return taxonomy_classifier.get_attributes(taxonomy_data, product_data)


def validate_inputs(upc_ean, manufacturer, item_number):
    """Validate that user entered either UPC/EAN OR both manufacturer and item number"""
    upc_filled = bool(upc_ean and upc_ean.strip())
    manufacturer_filled = bool(manufacturer and manufacturer.strip())
    item_filled = bool(item_number and item_number.strip())
    
    if upc_filled and (manufacturer_filled or item_filled):
        return False, "Please enter either UPC/EAN OR Manufacturer + Item Number, not both."
    
    if upc_filled:
        return True, "Valid UPC/EAN input"
    
    if manufacturer_filled and item_filled:
        return True, "Valid Manufacturer + Item Number input"
    
    return False, "Please enter either UPC/EAN OR both Manufacturer and Item Number."

def validate_taxonomy_selection(level_1, level_2, level_3):
    """External validation function like input_page has"""
    if not level_1 or not level_2 or not level_3:
        return False, "Please select all taxonomy levels before continuing."
    return True, "Valid taxonomy selection"

def input_page():
    """Initial input page"""
    st.title("Product Content Generation - Initial Lookup")
    st.write("Enter product information to begin generating content:")
    
    with st.form("product_form"):
        st.subheader("Method 1: UPC/EAN")
        upc_ean = st.text_input("UPC/EAN Code", placeholder="Enter UPC or EAN code")
        
        st.subheader("Method 2: Manufacturer + Item Number") 
        manufacturer = st.text_input("Manufacturer", placeholder="Enter manufacturer name")
        item_number = st.text_input("Item Number", placeholder="Enter item number")
        
        st.info("💡 Fill out either the UPC/EAN field OR both Manufacturer and Item Number fields")
        
        submitted = st.form_submit_button("Start Processing", type="primary")
        
        if submitted:
            is_valid, message = validate_inputs(upc_ean, manufacturer, item_number)
            
            if is_valid:
                with st.spinner("Looking up product..."):
                    if upc_ean and upc_ean.strip():
                        result = initial_product_lookup(upc_ean=upc_ean.strip())
                    else:
                        result = initial_product_lookup(manufacturer=manufacturer.strip(), 
                                                      item_number=item_number.strip())
                
                # Check if product lookup failed
                print("RESULT")
                print(result)
                if result == "":
                    st.error("❌ No product was found with the provided information. Please verify your input and try again.")
                else:
                    # print(result)
                    st.session_state.product_data['initial'] = result
                    st.session_state.page = 'taxonomy'
                    st.session_state.current_step = 2
                    st.rerun()
            else:
                st.error(message)

def taxonomy_page():
    """Step 2: Review/modify taxonomy selection"""
    st.title("Step 2: Review/Modify Taxonomy Selection")

    df = taxonomy_classifier.taxonomy_df
    
    # Check if we need to process taxonomy (only if not submitting a form)
    if 'taxonomy' not in st.session_state.product_data:
        if 'processing_taxonomy' not in st.session_state:
            st.session_state.processing_taxonomy = True
            with st.spinner(f"Processing taxonomy for {st.session_state.product_data['initial'][0]['Product_Title']}..."):
                print(st.session_state.product_data['initial'][0]['Product_Title'])
                taxonomy_result = process_taxonomy(st.session_state.product_data['initial'])
                st.session_state.product_data['taxonomy'] = taxonomy_result
            del st.session_state.processing_taxonomy
            st.rerun()
            return  # Exit early to prevent form rendering during processing
    
    current_taxonomy = st.session_state.product_data['taxonomy']
    
    st.write(f"Product found: {st.session_state.product_data['initial'][0]['Product_Title']}")
    st.write("Review or modify the taxonomy classification below:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Category Classification")
        
        # Get unique primary categories from dataframe
        primary_options = sorted(df['level 1 category'].unique().tolist())
        primary_options_with_empty = ["-- Select Level 1 Taxonomy --"] + primary_options
        
        # Find current Level 1 Taxonomy index
        primary_index = 0
        if current_taxonomy.get('level_1_category') and current_taxonomy['level_1_category'] in primary_options:
            primary_index = primary_options_with_empty.index(current_taxonomy['level_1_category'])
        
        primary_selection = st.selectbox("Level 1 Taxonomy", 
                                       options=primary_options_with_empty,
                                       index=primary_index,
                                       key="primary_cat_select")
        
        # Use selected value or fall back to current taxonomy
        if primary_selection == "-- Select Level 1 Taxonomy --":
            level_1_category = None
        else:
            level_1_category = primary_selection
        
        # Get secondary categories for selected Level 1 Taxonomy
        secondary_options = sorted(df[df['level 1 category'] == level_1_category]['level 2 category'].unique().tolist())
        secondary_options_with_empty = ["-- Select Level 2 Taxonomy --"] + secondary_options
        
        # Find current Level 2 Taxonomy index
        secondary_index = 0
        if current_taxonomy.get('level_2_category') and current_taxonomy['level_2_category'] in secondary_options:
            secondary_index = secondary_options_with_empty.index(current_taxonomy['level_2_category'])
        
        secondary_selection = st.selectbox("Level 2 Taxonomy",
                                         options=secondary_options_with_empty,
                                         index=secondary_index,
                                         key="secondary_cat_select")
        
        # Use selected value or fall back to current taxonomy
        if secondary_selection == "-- Select Level 2 Taxonomy --":
            level_2_category = None
        else:
            level_2_category = secondary_selection
                
        # Get Level 3 Taxonomys for selected primary and secondary categories
        product_type_options = sorted(df[(df['level 1 category'] == level_1_category) & 
                                    (df['level 2 category'] == level_2_category)]['level 3 category'].unique().tolist())
        product_type_options_with_empty = ["-- Select Level 3 Taxonomy --"] + product_type_options
        
        # Find current Level 3 Taxonomy index
        product_type_index = 0
        if current_taxonomy.get('level_3_category') and current_taxonomy['level_3_category'] in product_type_options:
            product_type_index = product_type_options_with_empty.index(current_taxonomy['level_3_category'])
        
        product_type_selection = st.selectbox("Level 3 Taxonomy",
                                            options=product_type_options_with_empty,
                                            index=product_type_index,
                                            key="product_type_select")
        
        # Use selected value or fall back to current taxonomy
        if product_type_selection == "-- Select Level 3 Taxonomy --":
            level_3_category = None
        else:
            level_3_category = product_type_selection
    
    # Form for navigation buttons only
    with st.form("taxonomy_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            back_submitted = st.form_submit_button("← Back to Home")
            if back_submitted:
                st.session_state.product_data.pop('taxonomy', None)
                st.session_state.page = 'input'
                st.session_state.current_step = 1
                st.rerun()
            
        with col2:
            if st.form_submit_button("Next: Attributes →", type="primary"):
                print("CATS")
                print(level_2_category)
                if level_1_category and level_2_category and level_3_category:
                    # Save modified taxonomy
                    modified_taxonomy = {
                        'level_1_category': level_1_category,
                        'level_2_category': level_2_category,
                        'level_3_category': level_3_category,
                    }
                    st.session_state.product_data['taxonomy'] = modified_taxonomy
                    st.session_state.product_data.pop('attributes', None)
                    st.session_state.page = 'attributes'
                    st.session_state.current_step = 3
                    st.rerun()
                else:
                    st.error("Please select all taxonomy levels before continuing.")

def attributes_page():
    """Step 3: Review/modify attribute population"""
    st.title("Step 3: Review/Modify Attribute Population")
    
    # Check if we need to process attributes (only if not submitting a form)
    if 'attributes' not in st.session_state.product_data:
        if 'processing_attributes' not in st.session_state:
            st.session_state.processing_attributes = True
            with st.spinner("Processing attributes..."):
                st.session_state.product_data['attributes'] = process_attributes(
                    st.session_state.product_data['initial'], 
                    st.session_state.product_data['taxonomy']['level_3_category']
                )
            del st.session_state.processing_attributes
            st.rerun()
            return  # Exit early to prevent form rendering during processing
    
    current_attributes = st.session_state.product_data['attributes']
    
    # Get the selected level 3 category for display
    current_taxonomy = st.session_state.product_data['taxonomy']
    selected_level_3 = current_taxonomy.get('level_3_category')
    
    if not selected_level_3:
        st.error("No Level 3 Taxonomy selected. Please go back to taxonomy page.")
        return
    
    # Get the taxonomy dataframe to check for valid attribute values
    df = taxonomy_classifier.taxonomy_df
    
    # Filter dataframe for the selected level 3 category (will get multiple rows)
    level_3_rows = df[df['level 3 category'] == selected_level_3]
    
    # Create a mapping of attribute names to their valid values
    attribute_valid_values = {}
    for _, row in level_3_rows.iterrows():
        if 'attribute' in row and 'valid attribute values' in row:
            attr_name = row['attribute']
            valid_values_str = row['valid attribute values']
            
            # Debug print
            print(f"Processing attribute: {attr_name}, valid values: '{valid_values_str}'")
            
            # Check if valid_values_str is not empty (anything other than empty string means dropdown)
            if valid_values_str and str(valid_values_str).strip() != "" and str(valid_values_str) != 'nan':
                # Split by semicolon and clean up values
                valid_values = [val.strip() for val in str(valid_values_str).split(';') if val.strip()]
                attribute_valid_values[attr_name] = valid_values
                print(f"  -> Created dropdown with options: {valid_values}")
            else:
                print(f"  -> Will be text input (empty valid values)")
    
    print(f"Final attribute_valid_values mapping: {attribute_valid_values}")

    st.write(f"Product found: {st.session_state.product_data['initial'][0]['Product_Title']}")
    st.write(f"Review and modify the product attributes for **{selected_level_3}**:")
    
    with st.form("attributes_form"):
        # Dictionary to store the input values
        attribute_inputs = {}
        
        # Get all attributes from the current_attributes dictionary
        attribute_items = list(current_attributes.items())
        
        st.subheader("Product Attributes")
        
        # Create all attributes in a single column
        for attr_name, attr_value in attribute_items:
            # Create a two-column layout for each attribute
            attr_col1, attr_col2 = st.columns([1, 2])
            
            with attr_col1:
                # Display attribute name (non-editable)
                st.write(f"**{attr_name}:**")
            
            with attr_col2:
                # Check if this attribute has valid values (dropdown) or is free-fill (text input)
                if attr_name in attribute_valid_values:
                    valid_values = attribute_valid_values[attr_name].copy()
                    
                    print(f"Creating dropdown for {attr_name} with options: {valid_values}")
                    print(f"Current value to select: '{attr_value}'")
                    
                    # Add current value to options if it's not already there and not empty
                    if attr_value and str(attr_value).strip() and attr_value not in valid_values:
                        valid_values.insert(0, attr_value)
                        print(f"  -> Added current value to options: {valid_values}")
                    
                    # Find the index of current value
                    try:
                        if attr_value and attr_value in valid_values:
                            current_index = valid_values.index(attr_value)
                        else:
                            current_index = 0
                        print(f"  -> Selected index: {current_index}")
                    except ValueError:
                        current_index = 0
                    
                    # Create selectbox for attributes with valid values
                    attribute_inputs[attr_name] = st.selectbox(
                        label=attr_name,
                        options=valid_values,
                        index=current_index,
                        key=f"attr_{attr_name}",
                        label_visibility="collapsed"
                    )
                    print(f"  -> Created selectbox for {attr_name}")
                else:
                    # Create text input for attributes without valid values (free-fill)
                    print(f"Creating text input for {attr_name} (free-fill)")
                    attribute_inputs[attr_name] = st.text_input(
                        label=attr_name,
                        value=attr_value if attr_value else "",
                        key=f"attr_{attr_name}",
                        label_visibility="collapsed"
                    )
        
        # Navigation buttons
        col1, col2 = st.columns(2)
        
        with col1:
            back_submitted = st.form_submit_button("← Back to Taxonomy")
            if back_submitted:
                st.session_state.product_data.pop('attributes', None)
                st.session_state.page = 'taxonomy'
                st.session_state.current_step = 2
                st.rerun()
        
        with col2:
            attributes_submitted = st.form_submit_button("Next: Content →", type="primary")
            if attributes_submitted:
                # Save modified attributes
                st.session_state.pop('temp_features', None)
                st.session_state.product_data['attributes'] = attribute_inputs
                st.session_state.page = 'content'
                st.session_state.current_step = 4
                st.rerun()


def description_and_features_page():
    """Step 4: Review/modify product title, romance text, and features"""
    st.title("Step 4: Review/Modify Product Title, Romance Text, and Features")

    # Get data from existing session state
    if 'final' not in st.session_state.product_data:
        with st.spinner("Generating romance text and features..."):
            st.session_state.product_data['final'] = claude_client.search(initial_claude_query, str(st.session_state.product_data['initial']) + str(st.session_state.product_data['attributes']))

    # Get data from existing session state
    initial_data = st.session_state.product_data['initial']
    taxonomy_data = st.session_state.product_data['taxonomy']
    attributes_data = st.session_state.product_data['attributes']
    final_data = st.session_state.product_data['final']
    
    # Extract product title from initial data
    product_title = initial_data[0]['Product_Title']
    
    # Extract romance text and features from final data
    romance_text = final_data[0]['Product_Description']
    key_features = final_data[0]['Product_Features']
    
    st.write("Review and modify the product content below:")
    
    # Initialize session state for dynamic features if not exists
    if 'temp_features' not in st.session_state:
        st.session_state.temp_features = key_features.copy() if key_features else []
    
    # Form 1: Product Title and Romance Text (full width)
    with st.form("title_romance_form"):
        st.subheader("Product Title")
        edited_title = st.text_input("Title", value=product_title)
        
        st.subheader("Romance Text")
        edited_romance = st.text_area("Romance Text", value=romance_text, height=150)
        
        # Button to save title and romance changes
        save_title_romance = st.form_submit_button("Save Title & Romance Text")
    
    st.divider()
    
    # Create layout with two columns for features
    col1, col2 = st.columns([4, 1])
    
    # Form 2: Key Features (left column)
    with col1:
        with st.form("features_form"):
            st.subheader("Key Features")
            
            # Display existing features with ability to edit
            edited_features = []
            for i, feature in enumerate(st.session_state.temp_features):
                feature_text = st.text_input("", value=feature, key=f"feature_{i}", label_visibility="collapsed")
                if feature_text.strip():  # Only add non-empty features
                    edited_features.append(feature_text.strip())
            
            # Add new feature input
            st.write("**Add New Feature:**")
            new_feature = st.text_input("New Feature", key="new_feature_input")
            
            # Feature management and navigation buttons
            col_a, col_b, col_c = st.columns([1, 1, 1])
            
            with col_a:
                back_clicked = st.form_submit_button("← Back to Attributes")
            
            with col_b:
                add_feature = st.form_submit_button("Add Feature")
            
            with col_c:
                next_clicked = st.form_submit_button("View Final Results →", type="primary")
    
    # Remove buttons column - outside any form (right column)
    with col2:
        # Add spacing to align with features form content
        st.write("")  # Align with Key Features header
        st.write("")
        
        st.write("**Remove**")
        for i, feature in enumerate(st.session_state.temp_features):
            if st.button("✕", key=f"remove_btn_{i}", help="Remove this feature"):
                st.session_state.temp_features.pop(i)
                st.rerun()
        
        # Add spacing to align with new feature input
        st.write("")
        st.write("")
    
    # Handle form submissions
    if save_title_romance:
        # Update the data with title and romance changes
        updated_final = final_data.copy()
        updated_final[0]['Product_Description'] = edited_romance
        
        updated_initial = initial_data.copy()
        updated_initial[0]['Product_Title'] = edited_title
        
        # Save to session state
        st.session_state.product_data['final'] = updated_final
        st.session_state.product_data['initial'] = updated_initial
        
        st.success("Title and romance text saved!")
        st.rerun()
    
    if back_clicked:
        st.session_state.page = 'attributes'
        st.session_state.current_step = 3
        st.rerun()

    if add_feature and new_feature.strip():
        st.session_state.temp_features.append(new_feature.strip())
        st.rerun()
    
    if next_clicked:
        # Save the edited features
        final_features = edited_features.copy()
        
        # Update the final data with modifications
        updated_final = final_data.copy()
        updated_final[0]['Product_Features'] = final_features
        
        # Save to session state
        st.session_state.product_data['final'] = updated_final
        st.session_state.pop('temp_features', None) # Clear temp features
        st.session_state.product_data['content'] = 'completed' # Necessary so generation progress knows this step is completed
        
        st.session_state.page = 'final'
        st.rerun()




def final_page():
    """Final page displaying all processing results"""
    st.title("Final Results - Complete Product Processing")
    st.write("Here are the complete results from all processing steps:")
    
    if st.session_state.product_data:
        # Content Results - Use final data structure only
        with st.expander("📝 Product Content", expanded=True):
            final_data = st.session_state.product_data.get('final', [{}])
            
            if final_data:
                st.subheader("Product Title")
                st.write(final_data[0].get('Product_Title', 'N/A'))

                st.subheader("Product Details")
                st.write(f"**UPC:** {final_data[0].get('UPC', 'N/A')}")
                st.write(f"**Vendor:** {final_data[0].get('Vendor', 'N/A')}")
                st.write(f"**Item Number:** {final_data[0].get('Item_Number', 'N/A')}")
                
                st.subheader("Product Description")
                st.write(final_data[0].get('Product_Description', 'N/A'))
                
                st.subheader("Key Features")
                features = final_data[0].get('Product_Features', [])
                if features:
                    for i, feature in enumerate(features, 1):
                        st.write(f"{i}. {feature}")
                else:
                    st.write("No features available.")
        # Taxonomy Results
        with st.expander("🏷️ Taxonomy Classification", expanded=True):
            taxonomy_data = st.session_state.product_data.get('taxonomy', {})
            
            st.write(f"**Level 1 Taxonomy:** {taxonomy_data.get('level_1_category', 'N/A')}")
            st.write(f"**Level 2 Taxonomy:** {taxonomy_data.get('level_2_category', 'N/A')}")
            st.write(f"**Level 3 Taxonomy:** {taxonomy_data.get('level_3_category', 'N/A')}")
        
        # Attributes Results - Show actual attributes dynamically
        with st.expander("⚙️ Product Attributes", expanded=True):
            attributes_data = st.session_state.product_data.get('attributes', {})
            
            if attributes_data:
                # Display attributes in two columns
                col1, col2 = st.columns(2)
                attributes_list = list(attributes_data.items())
                
                for i, (attr_name, attr_value) in enumerate(attributes_list):
                    with col1 if i % 2 == 0 else col2:
                        st.write(f"**{attr_name}:** {attr_value if attr_value else 'N/A'}")
            else:
                st.write("No attributes available.")
        
        
        st.success("✅ Product processing completed successfully!")
        
        # Action buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Process New Product", type="secondary"):
                # Reset all session state
                st.session_state.page = 'input'
                st.session_state.current_step = 1
                st.session_state.product_data = {}
                # Clear temp features
                if 'temp_features' in st.session_state:
                    del st.session_state.temp_features
                st.rerun()
        
        with col2:
            if st.button("📥 Export Results"):
                import json
                results_json = json.dumps(st.session_state.product_data, indent=2)
                st.download_button(
                    label="Download JSON",
                    data=results_json,
                    file_name=f"{st.session_state.product_data['final'][0]['Vendor']}_{st.session_state.product_data['final'][0]['Item_Number']}.json",
                    mime="application/json"
                )
        
        with col3:
            if st.button("🔧 Edit Previous Step"):
                st.write("Navigate using the sidebar to edit previous steps")
    
    else:
        st.warning("No processing results to display.")
        if st.button("Start Processing"):
            st.session_state.page = 'input'
            st.rerun()


# Main app logic
def main():
    # Sidebar for navigation and status
    with st.sidebar:
        st.image("assets/images/ace-hardware-logo.png", width=150)
        st.header("Generation Progress")
        # Progress indicator
        steps = {
            'input': '1. Initial Product Lookup',
            'taxonomy': '2. Review/modify taxonomy selection',
            'attributes': '3. Review/modify attribute population', 
            'content': '4. Review/modify product title, romance text, and features',
            'final': '5. Final Results'
        }
        
        current_page = st.session_state.page
        
        for page_key, step_name in steps.items():
            if page_key == current_page:
                st.write(f"🔄 **{step_name}**")
            elif page_key in ['input'] or page_key in st.session_state.product_data or (page_key == 'final' and len(st.session_state.product_data) >= 5):
                st.write(f"✅ {step_name}")
            else:
                st.write(f"⏳ {step_name}")
        
        st.divider()
        
        # Navigation buttons (if not on input page)
        if current_page != 'input' and st.session_state.product_data:
            st.subheader("Quick Navigation")
            if 'initial' in st.session_state.product_data and st.button("📋 Taxonomy"):
                st.session_state.page = 'taxonomy'
                st.session_state.current_step = 2
                st.rerun()
            
            if 'taxonomy' in st.session_state.product_data and st.button("⚙️ Attributes"):
                st.session_state.page = 'attributes'
                st.session_state.current_step = 3
                st.rerun()
            
            if 'attributes' in st.session_state.product_data and st.button("📝 Content"):
                st.session_state.page = 'content'
                st.session_state.current_step = 4
                st.rerun()
            
            if 'content' in st.session_state.product_data and st.button("🎯 Final Results"):
                st.session_state.page = 'final'
                st.rerun()
    
    # Route to appropriate page
    if st.session_state.page == 'input':
        input_page()
    elif st.session_state.page == 'taxonomy':
        taxonomy_page()
    elif st.session_state.page == 'attributes':
        attributes_page()
    elif st.session_state.page == 'content':
        description_and_features_page()
    elif st.session_state.page == 'final':
        final_page()

if __name__ == "__main__":
    main()