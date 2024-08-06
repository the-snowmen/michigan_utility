import os
from PyQt5.QtWidgets import QApplication, QInputDialog, QFileDialog, QMessageBox                      #pip install pyqt5

# def get_output_directory():
#     app = QApplication([])
#     dir = QFileDialog.getExistingDirectory(None, "Select Output Directory")
#     return dir

# Replace 'your_folder_path' with the path to your folder
folder_path = r"...\CompVision_Cable\basedata\T104\Miss"
# List all files in the folder
files = os.listdir(folder_path)

# Filter out only PNG files
png_files = [file for file in files if file.endswith('.png')]

# Sort the PNG files to ensure they are renamed in a specific order
png_files.sort()

# Rename each PNG file
for i, file in enumerate(png_files):
    new_name = f"A{i + 1}.png"
    os.rename(os.path.join(folder_path, file), os.path.join(folder_path, new_name))

print("Renaming complete.")
