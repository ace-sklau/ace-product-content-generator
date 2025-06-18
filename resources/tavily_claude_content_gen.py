# Assume claude.py, csv_data.py, tavily_extract.py are in a 'resources' subfolder
# or adjust the import paths accordingly.
from resources import csv_data
from resources import tavily_extract
from resources import claude
from tkinter import Tk
from tkinter.filedialog import askopenfilename, askdirectory
import sys # For exiting gracefully

class TavilyClaudeContentGen:
    def __init__(self):
        """Initializes the Tavily and Claude clients."""
        self.tavily_e = tavily_extract.upcExtract()
        self.claude_client = claude.ClaudeQuery()

    def get_data(self):
        """Prompts the user to select an input CSV file and loads it."""
        Tk().withdraw() # Keep the root Tkinter window from appearing
        filename = askopenfilename(title="Select Input Pipe-Delimited File")
        if not filename:
            print("No file selected. Exiting.")
            return None # Return None if user cancels
        print(f"Loading data from: {filename}")
        upc_data = csv_data.CsvData(filename)
        if not upc_data.loaded_successfully:
            print(f"Failed to load data from {filename}. Exiting.")
            return None
        if not upc_data.header:
            print("Could not find header row in the file. Exiting.")
            return None
        return upc_data

    def get_column_indices(self, header):
        """
        Asks the user to specify which columns to use for searching.

        Args:
            header (list): The list of column names from the CSV header.

        Returns:
            dict: A dictionary containing the selected column indices,
                  or None if input is invalid or aborted.
                  Keys: 'search_type', 'upc', 'item_num', 'manuf', 'desc'
        """
        print("\n--- Column Selection ---")
        print("Available columns:")
        for i, col_name in enumerate(header):
            print(f"  {i}: {col_name}")

        indices = {'search_type': None, 'upc': None, 'item_num': None, 'manuf': None, 'desc': None}
        max_index = len(header) - 1

        # --- Get Search Type ---
        while True:
            search_choice = input("Select search type:\n  1: Use Item Number, Manufacturer, Description\n  2: Use UPC/EAN\nEnter choice (1 or 2): ").strip()
            if search_choice == '1':
                indices['search_type'] = 1
                break
            elif search_choice == '2':
                indices['search_type'] = 2
                break
            else:
                print("Invalid choice. Please enter 1 or 2.")

        # --- Get Specific Column Indices ---
        def prompt_for_index(prompt_text):
            while True:
                try:
                    idx_str = input(f"{prompt_text} (Enter column number 0-{max_index}): ").strip()
                    if not idx_str.isdigit():
                        print("Invalid input. Please enter a number.")
                        continue
                    idx = int(idx_str)
                    if 0 <= idx <= max_index:
                        return idx
                    else:
                        print(f"Index out of range. Please enter a number between 0 and {max_index}.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
                except KeyboardInterrupt:
                    print("\nOperation cancelled by user.")
                    return None

        if indices['search_type'] == 1: # Item/Manuf/Desc Search
            indices['item_num'] = prompt_for_index("Enter index for Item Number column")
            if indices['item_num'] is None: return None
            indices['manuf'] = prompt_for_index("Enter index for Manufacturer Name column")
            if indices['manuf'] is None: return None
            indices['desc'] = prompt_for_index("Enter index for Short Description column")
            if indices['desc'] is None: return None
        else: # UPC Search
            indices['upc'] = prompt_for_index("Enter index for UPC/EAN column")
            if indices['upc'] is None: return None

        print("--- Column Selection Complete ---")
        return indices

    def claude_tavily_extract(self, upc_data, column_indices):
        """
        Processes each row using Tavily and Claude based on selected columns.

        Args:
            upc_data (CsvData): The loaded CSV data object.
            column_indices (dict): Dictionary containing the indices for relevant columns.

        Returns:
            str: A combined string containing the results for all rows.
        """
        combined_output = ''
        search_type = column_indices['search_type']
        upc_idx = column_indices['upc']
        item_num_idx = column_indices['item_num']
        manuf_idx = column_indices['manuf']
        desc_idx = column_indices['desc']

        # Use a counter for the processing limit
        processed_count = 0
        processing_limit = 20 # Keep the original limit for now

        for i, row in enumerate(upc_data.get_data_rows()):
            if processed_count >= processing_limit:
                print(f"\nReached processing limit of {processing_limit} rows.")
                break

            print(f"\nProcessing row {i+1}...")
            # Use pipe delimiter for output consistency with input
            output_row_str = "|".join(map(str, row))
            tavily_output = ''
            tavily_image_search = []

            try:
                # --- Perform Tavily Search ---
                if search_type == 1: # Item/Manuf/Desc
                    # Safely get data using indices
                    item_num = row[item_num_idx] if item_num_idx < len(row) else None
                    manuf_name = row[manuf_idx] if manuf_idx < len(row) else None
                    short_desc = row[desc_idx] if desc_idx < len(row) else None

                    if not all([item_num, manuf_name, short_desc]):
                         print(f"  Warning: Missing required data in row {i+1} for Item/Manuf/Desc search. Skipping Tavily search.")
                         combined_output += f"{output_row_str}\n\nNo results found (missing input data)\n\n___\n\n"
                         continue # Skip to next row

                    print(f"  Searching Tavily with: Item='{item_num}', Manuf='{manuf_name}', Desc='{short_desc}'")
                    tavily_output = self.tavily_e.run(item_num=item_num, manufacturer_name=manuf_name, short_description=short_desc)

                else: # UPC Search
                    upc = row[upc_idx] if upc_idx < len(row) else None
                    if not upc:
                        print(f"  Warning: Missing UPC data in row {i+1}. Skipping Tavily search.")
                        combined_output += f"{output_row_str}\n\nNo results found (missing UPC)\n\n___\n\n"
                        continue # Skip to next row

                    print(f"  Searching Tavily with UPC: '{upc}'")
                    tavily_output = self.tavily_e.run(upc=upc)

                # --- Process Tavily Results ---
                if not tavily_output or tavily_output.strip() == '':
                    print("  Tavily returned no results.")
                    combined_output += f"{output_row_str}\n\nNo results found via Tavily\n\n___\n\n"
                else:
                    print("  Tavily search successful. Querying Claude...")
                    # --- Query Claude ---
                    claude_output_obj = self.claude_client.search(tavily_output) # Assuming search returns the message object
                    claude_text = ''.join(str(content_block.text) for content_block in claude_output_obj if hasattr(content_block, 'text')) # Extract text safely

                    if not claude_text.strip():
                         print("  Claude returned no description.")
                         combined_output += f"{output_row_str}\n\n{tavily_output}\n\nClaude returned no description.\n\n___\n\n" # Include Tavily output for context
                    else:
                        print("  Claude description generated. Searching for images...")
                        # --- Get Images from Tavily ---
                        # Use the generated Claude text to find relevant images
                        tavily_image_search = self.tavily_e.run(queries=claude_text, include_images=True)
                        print(f"  Found {len(tavily_image_search)} images.")

                        # --- Combine Output ---
                        combined_output += f"{output_row_str}\n\n" # Original row data
                        combined_output += f"{claude_text}\n\n" # Claude's description
                        # Add image HTML tags
                        if tavily_image_search:
                            combined_output += ''.join(f'<img src="{image_url}" alt="Product Image" style="width:200px; height:auto; margin: 5px;" onerror="this.style.display=\'none\'"/> ' + "\n" for image_url in tavily_image_search)
                        combined_output += "\n___\n\n" # Separator

            except IndexError as e:
                 print(f"  Error accessing data in row {i+1}: {e}. Check column indices and file structure. Skipping row.")
                 combined_output += f"{output_row_str}\n\nError processing row: Invalid column index used.\n\n___\n\n"
            except Exception as e:
                print(f"  An unexpected error occurred processing row {i+1}: {e}")
                combined_output += f"{output_row_str}\n\nError processing row: {e}\n\n___\n\n"

            processed_count += 1 # Increment the counter only after attempting to process a row

        return combined_output

    def search(self):
        """Main workflow: get data, get columns, process, save."""
        # 1. Get Input Data
        upc_data = self.get_data()
        if upc_data is None:
            return # Exit if file loading failed or was cancelled

        # 2. Get Column Mappings from User
        column_indices = self.get_column_indices(upc_data.header)
        if column_indices is None:
            print("Column selection aborted or failed. Exiting.")
            return # Exit if column selection failed or was cancelled

        # 3. Process Data
        print("\nStarting data processing...")
        output_data = self.claude_tavily_extract(upc_data, column_indices)

        # 4. Get Output Path
        print("\nSelect the folder where the output file should be saved.")
        outpath = askdirectory(title="Select Output Folder")
        if not outpath:
            print("No output folder selected. Exiting.")
            return

        # 5. Save Output
        print(f"\nSaving output to directory: {outpath}")
        # The save class handles creating the timestamped filename
        csv_data.save(outpath, output_data)
        print("Processing complete.")

# --- Main Execution ---
if __name__ == "__main__":
    generator = TavilyClaudeContentGen()
    generator.search()
