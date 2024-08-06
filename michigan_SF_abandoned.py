'''
-----Warning, this code is an abandoned file, it was intended to showcase how it could have intergrate the email script
        to further expand the automation process. It will not execute. ---

---This code takes text from Salesforce, extract information, capture screenshots and run the classification model to
    determine the status of the images (Hit/Miss)
---Make sure the correct drawing order was turned on!!!
---Make sure to clear the Definition Query(if needed) before running.

-Created by Mike Huang
-This code was built on July 18, 2024, based on code from June 2024. With some style and logic updates on July 30, 2024.
-When running this code in ArcGIS pro, please make sure all the necessary libray was installed, see pip install below.

-Warning: This is a legacy that could not run!
-Warning: I tried to fix the performance issues of the code:
    The issue: After running the process, if the user close/terminate the process, and try to run again. There is a
    possibility that it could cause the program to crash. Since the program will keep running until the user closes the
    input prompt, user can keep using it as long it is running in the same process.
-Warning: This code only works on Michigan missdig ticket, for the input, simply ctrl-a and ctrl-c the entire webpage,
            and ctrl-v into the input prompt.

-Transfer code to ArcGIS Pro instruction:
-ArcGIS pro -> View ---> Catalog Pane ---> Toolboxes ---> (right-click) New Toolbox(.atbx) ---> (right-click) New --->
--->(right-click) Script --> Paste the code into Execution
'''

'''pip install if needed'''
import arcpy
import os
import re
import csv
from datetime import datetime
from PyQt5.QtWidgets import QApplication, QInputDialog              #pip install pyqt5
from PIL import Image, ImageDraw, ImageFont                         #pip install pillow
from fpdf import FPDF                                               #pip install fpdf
import matplotlib.pyplot as plt                                     #pip install matplotlib
from tensorflow.keras.preprocessing import image                    #pip install tensorflow
from tensorflow.keras.models import load_model
import numpy as np                                                  #pip install np
import tensorflow as tf
import webbrowser                                                   #install other package as prompted
import urllib.parse
import pandas as pd

model = load_model(r"...\CompVision_Cable\model\CV_Cable_v3.keras")

def get_output_directory(app):
    dir = QFileDialog.getExistingDirectory(None, "Select Output Directory")
    return dir

def add_text_to_image(image_path, text, font_size=12):
    try:
        with Image.open(image_path) as img:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype("arial.ttf", font_size)
            text_position = (10, 10)
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


def regex_process(content):
    try:
        ticket_number_pattern = r"TICKET NO= (\d+)"
        latitude_pattern = r"LATITUDE= (\d+\.\d+)"
        longitude_pattern = r"LONGITUDE= (-?\d+\.\d+)"
        location_details_pattern = r"\[LOCATION DETAILS\](.*?)\n\n"
        caller_details_pattern = r"\[CALLER DETAILS\](.*?)\n\n"

        location_details_match = re.search(location_details_pattern, content, re.DOTALL)
        location_details = location_details_match.group(1) if location_details_match else ""

        caller_details_match = re.search(caller_details_pattern, content, re.DOTALL)
        caller_details = caller_details_match.group(1) if caller_details_match else ""

        address_pattern = r"ADDRESS= ([^\n]+)"
        city_pattern = r"CITY/TOWN= ([^\n]+)"
        state_pattern = r"STATE= ([^\n]+)"
        email_pattern = r"EMAIL ADDRESS= ([^\n]+)"
        name_pattern = r"CONTACT NAME= ([^\n]+)"
        req_name_pattern = r"Request Name\s+(\S+)"
        ticket_pattern = r"Subject\s+TICKET: ([^\n]+)"

        latitude_match = re.search(latitude_pattern, location_details)
        longitude_match = re.search(longitude_pattern, location_details)
        address_match = re.search(address_pattern, location_details)
        city_match = re.search(city_pattern, location_details)
        state_match = re.search(state_pattern, location_details)
        email_match = re.search(email_pattern, caller_details)
        name_match = re.search(name_pattern, caller_details)
        req_name_match = re.search(req_name_pattern, content)
        ticket_match = re.search(ticket_pattern, content)

        return (latitude_match, longitude_match, address_match, city_match, state_match, email_match, name_match,
                req_name_match, ticket_match)
    except Exception as e:
        print(f"Error in regex processing: {e}")
        return None, None, None, None, None, None, None, None, None


def filtered(layer_name, placement_col_name, owner_col_name):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        maps = aprx.listMaps()
        map_view = maps[0]
        layer = map_view.listLayers(layer_name)[0]

        if layer is None:
            print(f"Layer '{layer_name}' not found")
            return

        aerial_query = f"{arcpy.AddFieldDelimiters(layer, placement_col_name)} <> 'Aerial'"
        iru_query = f"{arcpy.AddFieldDelimiters(layer, owner_col_name)} <> 'IRU'"
        combined_query = f"{aerial_query} AND {iru_query}"

        layer.definitionQuery = combined_query
        print(f"Applied combined filter to layer '{layer_name}'.")
    except Exception as e:
        print(f"An error occurred in filtered function: {e}")


'''
1. This function takes the coordinate information and go to the coordinate, then proceed to take screenshots from 
five different scales. (1:2500 meters, 1:5000 meters, 1:10000 meters, 1:20000 meters, and 1:30000 meters), the scale can
be changed if needed.
2. The default spatial reference is 4326, it can be changed as needed as well.
3. For the screenshot saving process, it uses the 'request name' + 'current time (to the seconds)' to created a folder:
        ex. req-12345 + 073024_111633 = req-12345_073024_111633
   The screenshot itself follow a similar format, 'request name' + scale{x}
        ex. req-12345 + scale_30000 = req-12345_scale_30000 
'''
def go_to_coordinate_and_capture_screenshots(map_name, longitude, latitude, req_name, ticket, spatial_reference=4326,
                                             scales=[2500, 5000, 10000, 20000, 30000], output_base_directory=None,
                                             save_screenshots=True):
    try:
        global output_directory
        if output_base_directory is None:
            print("Output base directory not specified")
            return

        point = arcpy.PointGeometry(arcpy.Point(longitude, latitude), arcpy.SpatialReference(spatial_reference))
        aprx = arcpy.mp.ArcGISProject("CURRENT")

        maps = aprx.listMaps()
        print("Available maps:")
        for m in maps:
            print(m.name)

        map_view = [m for m in maps if m.name == map_name]
        if not map_view:
            print(f"Map '{map_name}' not found.")
            return
        map_view = map_view[0]

        map_frame = aprx.activeView
        if map_frame is None:
            print(f"No active view found for map '{map_name}'")
            return

        if save_screenshots:
            now = datetime.now()
            curr_time = now.strftime("%m%d%Y_%H%M%S")
            folder_name = f"{req_name}_{curr_time}"
            output_directory = os.path.join(output_base_directory, folder_name)
            os.makedirs(output_directory)
            print(f"Created folder: {output_directory}")

        for scale in scales:
            map_frame.camera.setExtent(point.extent)
            map_frame.camera.scale = scale
            print(
                f"Zoomed to coordinate ({longitude}, {latitude}) with spatial reference {spatial_reference} on map"
                f" '{map_name}' at scale {scale}")
            if save_screenshots:
                output_image_path = os.path.join(output_directory, f"{req_name}_scale_{scale}.png")
                width = 1080
                height = 1080
                map_frame.exportToPNG(output_image_path, width, height)
                print(f"Snapshot saved to {output_image_path}")

                text = f"Ticket: {ticket}\nCoordinate: ({longitude}, {latitude})\nScale: 1:{scale} meter"
                add_text_to_image(output_image_path, text)

        classify_images_in_directory(output_directory)                          #Activate the classify model function
    except Exception as e:
        print(f"Error in go_to_coordinate_and_capture_screenshots: {e}")


def add_red_border(image_path, border_size=5):
    try:
        with Image.open(image_path) as img:
            img_with_border = Image.new("RGB", (img.width + 2 * border_size, img.height + 2 * border_size), "red")
            img_with_border.paste(img, (border_size, border_size))
            img_with_border.save(image_path)
    except Exception as e:
        print(f"Error adding red border to image: {e}")


'''
This function use the classify model to determine Hit/Miss for each images (red box means hit) then generate a PDF 
report combined with extracted information and classified images. 
'''
def classify_images_in_directory(output_directory, extracted_info):
    try:
        hit_count = 0
        miss_count = 0
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        results = []

        for filename in os.listdir(output_directory):
            if filename.endswith(".png"):
                img_path = os.path.join(output_directory, filename)
                img = image.load_img(img_path, target_size=(480, 480))

                X = image.img_to_array(img)
                X = np.expand_dims(X, axis=0)
                images = np.vstack([X])

                val = model.predict(images)
                print(f"Prediction for {filename}: {val}")

                result = "Hit" if val == 0 else "Miss"
                if result == "Hit":
                    hit_count += 1
                    add_red_border(img_path)
                else:
                    miss_count += 1

                results.append({
                    "Image": filename,
                    "Result": result
                })

                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt=f"Image: {filename}", ln=True, align='C')
                pdf.cell(200, 10, txt=f"Result: {result}", ln=True, align='C')
                pdf.image(img_path, x=10, y=30, w=190)

        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Hit: {hit_count}", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Miss: {miss_count}", ln=True, align='C')

        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Extracted Information:", ln=True, align='C')
        for key, value in extracted_info.items():
            pdf.cell(200, 10, txt=f"{key}: {value}", ln=True, align='C')

        timestamp = datetime.now().strftime("%m%d%y_%H_%M")
        pdf_filename = f"Result_{timestamp}.pdf"
        pdf_file_path = os.path.join(output_directory, pdf_filename)
        pdf.output(pdf_file_path)

        csv_path = os.path.join(output_directory, 'analysis_results.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            fieldnames = ['Image', 'Result']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for result in results:
                writer.writerow(result)

        print(f"PDF saved as {pdf_filename}")
        print(f"Analysis results exported to CSV at {csv_path}")
    except Exception as e:
        print(f"Error in classify_images_in_directory: {e}")


def create_email_script(directory, filter_result, extracted_info):
    script_path = os.path.join(directory, f"email_{filter_result.lower()}.py")
    with open(script_path, 'w') as f:
        f.write(f"""
import subprocess
subprocess.run(["python", "-c", \"""
import sys
import os
import webbrowser
import urllib.parse
import pandas as pd
from datetime import datetime

def find_csv_file(directory):
    for file_name in os.listdir(directory):
        if file_name.endswith('.csv'):
            return os.path.join(directory, file_name)
    return None

def read_data(directory, filter_result):
    csv_file_path = find_csv_file(directory)
    if not csv_file_path:
        raise FileNotFoundError("No CSV file found in the specified directory.")

    data = pd.read_csv(csv_file_path)
    data = data[data['Result'] == filter_result]
    data_dict = data.to_dict(orient='records')
    emails = ", ".join([record['Email'] for record in data_dict])
    ticket = ", ".join([record['Ticket'] for record in data_dict])

    return emails, ticket

def what_time():
    noon = "12:00"
    now = datetime.now().strftime('%H:%M')
    greeting = 'morning' if now < noon else 'afternoon'
    return greeting

def send_email(emails, ticket, greeting):
    cc_addresses = "ehogg@everstream.net"
    body = f"Good {greeting},\\n\\nEverstream have underground facilities in the area."

    # Encode the subject and body for URL
    subject_encoded = urllib.parse.quote(ticket)
    body_encoded = urllib.parse.quote(body)

    # Create the mailto link
    mailto_url = f"mailto:{emails}?cc={cc_addresses}&subject={subject_encoded}&body={body_encoded}"

    # Debug print to verify mailto link
    print(f"mailto_url: {{mailto_url}}")

    # Open the default email client
    webbrowser.open_new(mailto_url)

def main():
    directory = "{directory}"
    filter_result = "{filter_result}"

    try:
        emails, ticket = read_data(directory, filter_result)
    except FileNotFoundError as e:
        print(f"Error: {{str(e)}}")
        sys.exit(1)

    ticket = "Ticket: " + ticket
    greeting = what_time()
    send_email(emails, ticket, greeting)

if __name__ == '__main__':
    main()
\"""])
""")
    print(f"Email script created: {script_path}")


def main():
    app = QApplication([])
    while True:
        content, ok = QInputDialog.getText(None, "Coordinate Input", "Enter here:")
        if not ok:
            break

        (latitude_match, longitude_match, address_match, city_match, state_match, email_match, name_match,
         req_name_match, ticket_match) = regex_process(content)

        extracted_info = {}
        if latitude_match and longitude_match:
            latitude = float(latitude_match.group(1))
            longitude = float(longitude_match.group(1))
            coordinate = str(f"{latitude} {longitude}")
            extracted_info['Coordinate'] = coordinate
            print(f"Latitude/Longitude: {coordinate}")
        else:
            print("Coordinates not found")

        if address_match and city_match and state_match:
            address = address_match.group(1).strip()
            city = city_match.group(1).strip()
            state = state_match.group(1).strip()
            full_address = f"{address}, {city}, {state}"
            extracted_info['Address'] = full_address
            print(f"Address: {full_address}")
        else:
            print("Full address not found")

        if email_match:
            email = email_match.group(1).strip()
            extracted_info['Email'] = email
            print(f"Email: {email}")
        else:
            print("Email not found")

        if name_match:
            name = name_match.group(1).strip()
            extracted_info['Caller Name'] = name
            print(f"Caller Name: {name}")
        else:
            print("Caller Name not found")

        if req_name_match:
            req_name = req_name_match.group(1).strip()
            extracted_info['Request Name'] = req_name
            print(f"Request Name: {req_name}")
        else:
            print("Request Name not found")

        if ticket_match:
            ticket = ticket_match.group(1).strip()
            extracted_info['Ticket'] = ticket
            print(f"Ticket: {ticket}")
        else:
            print("Ticket not found")

        map_name = "Map"                                                #Active MapFrame name, updated if needed
        layer_name = "fibercable_current"                               #Layer name, update this if needed
        placement_col_name = "placementtype"                            #Attribute table field name update if needed
        owner_col_name = "owner_type"                                   #Attribute table field name update if needed
        filtered(layer_name, placement_col_name, owner_col_name)

        output_base_directory = get_output_directory(app)  # Prompt users to select an output destination
        if not output_base_directory:
            print("No output directory selected. Exiting the program.")
            return

        go_to_coordinate_and_capture_screenshots(map_name, longitude, latitude, req_name, ticket,
                                                 output_base_directory=output_base_directory,
                                                 save_screenshots=True)

        if 'output_directory' in globals():
            csv_path = os.path.join(output_directory, f'{req_name}.csv')
            with open(csv_path, 'w', newline='') as csvfile:
                fieldnames = ['Request Name', 'Ticket', 'Coordinate', 'Address', 'Email', 'Contact Name']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow({
                    'Request Name': req_name,
                    'Ticket': ticket,
                    'Coordinate': coordinate,
                    'Address': full_address,
                    'Email': email,
                    'Contact Name': name
                })
            print(f"Data exported to CSV at {csv_path}")
            classify_images_in_directory(output_directory, extracted_info)
        else:
            print("Error: Output directory not set, cannot save CSV.")


if __name__ == '__main__':
    main()
