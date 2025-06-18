import csv
import os # Import the os module for file path operations
import datetime # Import the datetime module for timestamping

class save:
   """
   Saves data to a new file within a specified directory.

   Creates a new file named 'output(YYYY-MM-DD_HH-MM-SS).txt'
   in the given directory_path, where the timestamp indicates
   the creation time.
   """
   def __init__(self, directory_path, data):
      """
      Initializes the save object and writes data to a new timestamped file.

      Args:
         directory_path (str): The path to the directory where the file should be saved.
                                If the directory doesn't exist, it will attempt to create it.
         data (any): The data to write. If it's a list or tuple,
                     each item is written on a new line. Otherwise,
                     the string representation of the data is written.
      """
      try:
          # Ensure the directory exists, create it if it doesn't
          # exist_ok=True prevents an error if the directory already exists
          os.makedirs(directory_path, exist_ok=True)

          # Get the current timestamp
          now = datetime.datetime.now()
          # Format the timestamp as YYYY-MM-DD_HH-MM-SS
          timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
          # Create the new filename
          new_filename = f"output({timestamp}).txt"
          # Combine the directory path with the new filename
          file_path = os.path.join(directory_path, new_filename)

          print(f"Creating new file: '{file_path}'")

          # Open the new file in write mode
          # 'w' mode creates the file
          with open(file_path, mode='w', encoding='utf-8') as f:
              if isinstance(data, (list, tuple)):
                  # Write each item of the list/tuple on a new line
                  f.writelines(str(item) + '\n' for item in data)
              else:
                  # Write the string representation of the data
                  f.write(str(data))
          print(f"Data successfully saved to '{file_path}'")

      except OSError as e:
          # Handle errors related to directory creation (e.g., permission denied)
          print(f"Error creating directory '{directory_path}': {e}")
      except Exception as e:
          # Handle other potential errors during file writing
          print(f"Error saving data to '{file_path}': {e}")


class CsvData:
  """
  Represents data read from a pipe-delimited ('|') file.

  Reads a pipe-delimited file upon instantiation and stores the data.
  Provides methods to access the data like a list (e.g., len(), indexing).

  Attributes:
    file_path (str): The path to the CSV file provided during instantiation.
    data (list): A list of lists representing the CSV data. Empty if loading failed.
    header (list): The first row of the CSV, assumed to be the header. Empty if no data.
    loaded_successfully (bool): True if the file was read without errors, False otherwise.
  """
  def __init__(self, file_path):
    """
    Initializes the CsvData object by reading the specified pipe-delimited file.

    Args:
      file_path (str): The path to the pipe-delimited file.
    """
    self.file_path = file_path
    self.data = []
    self.header = []
    self.loaded_successfully = False

    try:
      # Check if the file exists before trying to open it
      if not os.path.exists(self.file_path):
          print(f"Error: File not found at '{self.file_path}'")
          return # Exit __init__ early

      # Open the CSV file for reading
      # 'newline=''' prevents extra blank rows from being read on some systems
      with open(self.file_path, mode='r', newline='', encoding='utf-8') as csvfile:
        # Create a CSV reader object, specifying the pipe delimiter
        csv_reader = csv.reader(csvfile, delimiter='|')

        # Read all rows into the data attribute
        self.data = list(csv_reader) # More concise way to read all rows

      # Check if any data was actually read
      if not self.data:
          print(f"Warning: The file '{self.file_path}' is empty or could not be read properly.")
      else:
          # Assume the first row is the header
          self.header = self.data[0]
          self.loaded_successfully = True # Mark as successfully loaded

    except FileNotFoundError:
      # This case is less likely now due to the os.path.exists check, but good practice
      print(f"Error: File not found at '{self.file_path}'")
    except Exception as e:
      # Handle other potential errors during file reading or processing
      print(f"An error occurred while reading '{self.file_path}': {e}")

  def __len__(self):
    """Returns the number of data rows (excluding the header)."""
    # Return 0 if no data or only a header row exists
    return max(0, len(self.data) - 1) if self.header else len(self.data)

  def __getitem__(self, index):
    """
    Allows accessing data rows by index (e.g., csv_object[0]).
    Index 0 corresponds to the first data row (after the header).
    Raises IndexError if the index is out of bounds.
    """
    if not self.loaded_successfully:
        raise IndexError("CSV data not loaded successfully.")

    if self.header:
        # Adjust index to skip the header row
        actual_index = index + 1
        if 0 <= index < len(self.data) - 1:
             return self.data[actual_index]
        else:
            raise IndexError(f"Row index {index} out of range for data rows.")
    else:
        # No header, access directly
        if 0 <= index < len(self.data):
            return self.data[index]
        else:
            raise IndexError(f"Row index {index} out of range.")

  def __str__(self):
    """Returns a string representation showing file path and number of data rows."""
    status = "loaded successfully" if self.loaded_successfully else "failed to load"
    num_data_rows = len(self)
    return f"<CsvData object for '{self.file_path}' - {status}, {num_data_rows} data rows>"

  def __repr__(self):
    """Detailed representation, often the same as __str__ for simple classes."""
    return self.__str__()

  def get_data_rows(self):
      """Returns a list containing only the data rows (excluding the header)."""
      if self.header and self.data:
          return self.data[1:]
      elif self.data:
          return self.data # No header, return all data
      else:
          return [] # No data loaded
