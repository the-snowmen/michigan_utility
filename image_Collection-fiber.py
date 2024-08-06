'''

---This code collect Fiber Cable features images. It is designed to collect data for machine learning.
---Make sure the correct drawing order was turned on!!!
---Make sure to clear the Definition Query(if needed) before running.

-Created by Mike Huang
-This code was built on July 2024, based on code from June 2024. With some style and logic updates on July 30, 2024.
-When running this code in ArcGIS pro, please make sure all the necessary library was installed, see pip install below.

-Warning: Please make sure the layer's attribute table contains the field 'Serving Area'
-Warning: Based on previous experience, the range of start and end index tend to be within 700-800 images per session,
            try to keep the range within that. Going beyond that could cause the program to crash :(
-Warning: When selecting the output directory, make sure to create a new folder for each session, as it will overwrite
any previous files that has the same name.

-Transfer code to ArcGIS Pro instruction:

-ArcGIS pro -> View ---> Catalog Pane ---> Toolboxes ---> (right-click) New Toolbox(.atbx) ---> (right-click) New --->
--->(right-click) Script --> Paste the code into Execution
'''

'''pip install if needed'''
import arcpy
import os
import random
from PyQt5.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox                      #pip install pyqt5


def get_output_directory(app):
    dir = QFileDialog.getExistingDirectory(None, "Select Output Directory")
    return dir


def get_serving_area_code(app):
    serving_area_code, ok = QInputDialog.getInt(None, "Input Dialog", "Enter the serving area code:", 1, 1, 11)
    if not ok:
        return None
    return serving_area_code


def show_max_features(app, max_features):
    QMessageBox.information(None, "Max Features", f"The maximum number of features is {max_features}. Make sure to save"
                                                  f" it in a new folder, it will overwrite similar name file.")


def get_feature_count(layer):
    count = 0
    try:
        count = int(arcpy.management.GetCount(layer)[0])
    except Exception as e:
        print(f"An error occurred while counting features: {e}")
    return count


def apply_filter(layer_name, query):
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps()

    if not maps:
        print("No maps found in the current ArcGIS Project.")
        return None

    map_view = maps[0]  # Assuming you're using the first map; adjust as needed. Whatever map is currently active
    layers = map_view.listLayers(layer_name)

    if not layers:
        print(f"Layer '{layer_name}' not found in the map.")
        return None

    layer = layers[0]

    if layer is None:
        print(f"Layer '{layer_name}' not found.")
        return None

    # Apply the query
    try:
        layer.definitionQuery = query
        print(f"Applied filter to layer '{layer_name}'.")
        return layer
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def get_features(layer, start_index, end_index):
    features = []
    try:
        with arcpy.da.SearchCursor(layer, ["SHAPE@"]) as cursor:
            for i, row in enumerate(cursor):
                if i >= start_index and i < end_index:
                    features.append(row[0])
                elif i >= end_index:
                    break
    except Exception as e:
        print(f"An error occurred while retrieving features: {e}")
    return features


'''
Change the scale if needed, current range is 1000-21000 meters, interval of 1000
'''
def get_random_scale():
    return random.choice(range(4000, 21000, 1000))


def capture_screenshots(map_name, features, layer, output_base_directory):
    aprx = arcpy.mp.ArcGISProject("CURRENT")
    maps = aprx.listMaps()

    map_view = [m for m in maps if m.name == map_name]
    if not map_view:
        print(f"Map '{map_name}' not found.")
        return
    map_view = map_view[0]

    map_frame = aprx.activeView

    if map_frame is None:
        print(f"No active view found for map '{map_name}'")
        return

    if not os.path.exists(output_base_directory):
        os.makedirs(output_base_directory)
        print(f"Created folder: {output_base_directory}")

    for i, feature in enumerate(features):
        try:
            # Ensure the feature has a valid extent
            extent = feature.extent
            if extent.XMin is None or extent.YMin is None or extent.XMax is None or extent.YMax is None:
                print(f"Feature {i + 1} has an invalid extent.")
                continue

            print(f"Feature {i + 1} extent: {extent}")
            map_frame.camera.setExtent(extent)
            scale = get_random_scale()
            map_frame.camera.scale = scale
            print(f"Zoomed to feature {i + 1} at scale {scale}")

            # Deselect all features
            arcpy.management.SelectLayerByAttribute(layer, "CLEAR_SELECTION")
            print("Features deselected.")

            output_image_path = os.path.join(output_base_directory, f"snapshot_{i + 1}.png")
            width = 1080                #currently saved in 1080x1080, change if needed
            height = 1080
            map_frame.exportToPNG(output_image_path, width=width, height=height)
            print(f"Snapshot saved to {output_image_path}")

        except Exception as e:
            print(f"An error occurred while processing feature {i + 1}: {e}")

'''
Ask the user to pick a range, try to keep it within 800. ex. 1-801, 801-1601, etc.
Oh yeah, the actual 'end index' is 'end_index - 1', so if 'end_index=800', it will capture till features_799.
'''
def get_start_end_indices(app):
    start_index, ok1 = QInputDialog.getInt(None, "Input Dialog", "Enter the start index:", 1, 1)
    if not ok1:
        return None, None

    end_index, ok2 = QInputDialog.getInt(None, "Input Dialog", "Enter the end index:", 100, 1)
    if not ok2:
        return None, None

    return start_index, end_index


def main():
    map_name = "Map"
    layer_name = "fibercable_20240611"              #Change this if needed, most likely, and check the attribut table

    app = QApplication([])

    serving_area_code = get_serving_area_code(app)
    if serving_area_code is None:
        print("Input was cancelled. Exiting the program.")
        return

    '''
    Change below if needed, '=' --> is, '<>' --> is not
    '''
    query = f"placementtype = 'Underground' And serving_area = {serving_area_code}"

    # Apply filter
    try:
        layer = apply_filter(layer_name, query)
        if not layer:
            print("Failed to apply filter.")
            return
    except Exception as e:
        print(f"An error occurred while filtering the layer: {e}")
        return

    # Get feature count after applying filter
    max_features = get_feature_count(layer)

    # Inform the user of the maximum number of features
    show_max_features(app, max_features)

    output_base_directory = get_output_directory(app)
    if not output_base_directory:
        print("No output directory selected. Exiting the program.")
        return

    start_index, end_index = get_start_end_indices(app)
    if start_index is None or end_index is None:
        print("Start or end index input was cancelled. Exiting the program.")
        return

    try:
        features = get_features(layer, start_index, end_index)
        if not features:
            print("No features found or an error occurred.")
            return
    except Exception as e:
        print(f"An error occurred while retrieving features: {e}")
        return

    try:
        capture_screenshots(map_name, features, layer, output_base_directory)
    except Exception as e:
        print(f"An error occurred while capturing screenshots: {e}")


if __name__ == '__main__':
    main()
