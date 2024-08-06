'''
--version 1 of the tracker, it take input from user from QtWidgets --- June 13, 2024
--It takes the coordinate and return 4 images from different altitude.

---Make sure the correct drawing order was turned on!!!
---Make sure to clear the Definition Query(if needed) before running.

-Created by Mike Huang
-This code was built on July 13, 2024. With some style and logic updates on July 30, 2024.
-I added textbox that included coordinate and scale 
-When running this code in ArcGIS pro, please make sure all the necessary libray was installed, see pip install below.

-Warning: I tried to fix the performance issues of the code:
    The issue: After running the process, if the user close/terminate the process, and try to run again. There is a
    possibility that it could cause the program to crash. Since the program will keep running until the user closes the
    input prompt, user can keep using it as long it is running in the same process.

-Transfer code to ArcGIS Pro instruction:

-ArcGIS pro -> View ---> Catalog Pane ---> Toolboxes ---> (right-click) New Toolbox(.atbx) ---> (right-click) New --->
--->(right-click) Script --> Paste the code into Execution
'''

'''pip install if needed'''
import arcpy
import os
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QInputDialog, QFileDialog, QMessageBox                      #pip install pyqt5
from PIL import Image, ImageDraw, ImageFont

def get_output_directory():
    app = QApplication([])
    dir = QFileDialog.getExistingDirectory(None, "Select Output Directory")
    return dir

'''
Change the scales if needed
'''
def go_to_coordinate_and_capture_screenshots(map_name, longitude, latitude, spatial_reference=4326,
                                             scales=[2500, 5000, 10000, 25000], output_base_directory=None,
                                             save_screenshots=True):
    """
    Navigate to a specific coordinate in an ArcGIS Pro local map and save multiple snapshots at different scales.
    """
    if output_base_directory is None:
        print("Output base directory not specified")
        return

    point = arcpy.PointGeometry(arcpy.Point(longitude, latitude), arcpy.SpatialReference(spatial_reference))
    aprx = arcpy.mp.ArcGISProject("CURRENT")

    maps = aprx.listMaps()
    map_view = next((m for m in maps if m.name == map_name), None)
    if not map_view:
        print(f"Map '{map_name}' not found.")
        return

    map_frame = aprx.activeView
    if map_frame is None:
        print(f"No active view found for map '{map_name}'")
        return

    if save_screenshots:
        now = datetime.now()
        folder_name = now.strftime("%Y%m%d_%H%M%S")
        output_directory = os.path.join(output_base_directory, folder_name)
        os.makedirs(output_directory)
        print(f"Created folder: {output_directory}")

    for scale in scales:
        map_frame.camera.setExtent(point.extent)
        map_frame.camera.scale = scale
        print(f"Zoomed to coordinate ({longitude}, {latitude}) with spatial reference {spatial_reference} "
              f"on map '{map_name}' at scale {scale}")

        if save_screenshots:
            output_image_path = os.path.join(output_directory, f"snapshot_scale_{scale}.png")
            width = 1080
            height = 1080
            map_frame.exportToPNG(output_image_path, width, height)
            print(f"Snapshot saved to {output_image_path}")

            text = f"Coordinate: ({longitude}, {latitude})\nScale: 1:{scale} meter"
            add_text_to_image(output_image_path, text)


def get_coordinate():
    app = QApplication([])
    text, ok = QInputDialog.getText(None, "Coordinate Input",
                                    "Enter the coordinates "
                                    "(format: LATITUDE= 42.523131 LONGITUDE= -83.180006 or 43.218644, -86.241839):")
    if ok:
        text = text.replace('LATITUDE=', '').replace('LONGITUDE=', '').replace(',', ' ').strip()
        parts = text.split()
        if len(parts) >= 2:
            try:
                latitude = float(parts[0])
                longitude = float(parts[1])
                return longitude, latitude, True
            except ValueError:
                print("Invalid coordinate format. Please enter valid numbers for latitude and longitude.")
    return None, None, False

def filtered(layer_name, placement_col_name, owner_col_name):
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    map_view = aprx.listMaps()[0]  # Assuming you're using the first map; adjust as needed
    layer = next((lyr for lyr in map_view.listLayers(layer_name)), None)
    if not layer:
        print(f"Layer '{layer_name}' not found in the map.")
        return

    aerial_query = f"{arcpy.AddFieldDelimiters(layer, placement_col_name)} <> 'Aerial'"
    iru_query = f"{arcpy.AddFieldDelimiters(layer, owner_col_name)} <> 'IRU'"
    combined_query = f"{aerial_query} AND {iru_query}"

    try:
        layer.definitionQuery = combined_query
        print(f"Applied combined filter to layer '{layer_name}'.")
    except Exception as e:
        print(f"An error occurred: {e}")

'''
This function add the text box (coordinate, ticket number, and scale information)
'''
def add_text_to_image(image_path, text, font_size=12):
    try:
        with Image.open(image_path) as img:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype("arial.ttf", font_size)
            text_position = (10, 10) #adjust this for box location (now is top left)
            text_bbox = draw.textbbox(text_position, text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            padding = 5
            rectangle_position = [
                text_position[0] - padding,
                text_position[1] - padding,
                text_position[0] + text_width + padding,
                text_position[1] + text_height + padding
            ]
            draw.rectangle(rectangle_position, fill="white")
            draw.text(text_position, text, fill="black", font=font)
            img.save(image_path)
    except Exception as e:
        print(f"Error adding text to image: {e}")

def main():

    '''
        Update below if needed
    '''
    map_name = "Map"
    layer_name = "fibercable_20240611"
    placement_col_name = "placementtype"
    owner_col_name = "owner_type"

    try:
        filtered(layer_name, placement_col_name, owner_col_name)
    except Exception as e:
        print(f"An error occurred while filtering the layer: {e}")
        return

    while True:
        longitude, latitude, save_screenshots = get_coordinate()
        if longitude is None and latitude is None:
            print("Exiting the program.")
            break

        output_base_directory = get_output_directory()  # Prompt users to select an output destination
        if not output_base_directory:
            print("No output directory selected. Exiting the program.")
            return

        try:
            go_to_coordinate_and_capture_screenshots(map_name, longitude, latitude,
                                                     output_base_directory=output_base_directory,
                                                     save_screenshots=save_screenshots)
        except Exception as e:
            print(f"An error occurred while capturing screenshots: {e}")

if __name__ == '__main__':
    main()
