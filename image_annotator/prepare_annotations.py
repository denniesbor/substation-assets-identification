# %%
from PIL import Image
from pathlib import Path
import os
import json

labelme_path = Path('Annotations')
output_dir = Path('yolo_annotations')

labels = []
# Some labels are not properly labeled
# We will use this dictionary to correct the labels
existing_labels = {'Transformer': 'Transformer', 
 'Circuit Breaker': 'Circuit Breaker',
 'Transformers': 'Transformer', 
 'transformers': 'Transformer', 
 'Reactors': 'Reactors', 
 'Rectangle': 'Transformer'
 }

classes = list(set(existing_labels.values()))
print(classes)

def convert_labelme_to_yolo(labelme_dir, output_dir, classes):
    
    global labels
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    for file in os.listdir(labelme_dir):
        if file.endswith('.json'):
            with open(os.path.join(labelme_dir, file), 'r') as f:
                data = json.load(f)
                img_path = os.path.join(labelme_dir, data['imagePath'])
                image_base_path = os.path.basename(img_path)
                
                # The images are in labelme_dir
                img_path = os.path.join(labelme_dir, image_base_path)
        
                img = Image.open(img_path)
                img_w, img_h = img.size
                
                yolo_file = os.path.join(output_dir, file.replace('.json', '.txt'))
                with open(yolo_file, 'w') as f:
                    for shape in data['shapes']:
                        label = shape['label']
                        label = existing_labels.get(label, label)
                        
                        if label not in classes:
                            print(f'Unknown label: {label}')
                            continue

                        class_id = classes.index(label)
                        shape_type = shape['shape_type']
                        points = shape['points']

                        if shape_type == 'rectangle':
                            x1, y1 = points[0]
                            x2, y2 = points[1]
                        elif shape_type == 'polygon':
                            x_coords = [p[0] for p in points]
                            y_coords = [p[1] for p in points]
                            x1, y1 = min(x_coords), min(y_coords)
                            x2, y2 = max(x_coords), max(y_coords)
                        else:
                            print(f'Unsupported shape type: {shape_type}')
                            continue

                        # Convert to YOLO format
                        x_center = (x1 + x2) / 2 / img_w
                        y_center = (y1 + y2) / 2 / img_h
                        width = abs(x2 - x1) / img_w
                        height = abs(y2 - y1) / img_h
                        
                        yololabel = f'{class_id} {x_center} {y_center} {width} {height}\n'

                        f.write(yololabel)


convert_labelme_to_yolo(labelme_path, output_dir, classes)


print(set(labels))

# %%

# Train test split the data
import os
import random
import shutil

def split_dataset(image_dir, labels_dir, destination_dir, split_ratio=0.8):
    # Create destination directories
    os.makedirs(os.path.join(destination_dir, 'images', 'train'), exist_ok=True)
    os.makedirs(os.path.join(destination_dir, 'images', 'val'), exist_ok=True)
    os.makedirs(os.path.join(destination_dir, 'labels', 'train'), exist_ok=True)
    os.makedirs(os.path.join(destination_dir, 'labels', 'val'), exist_ok=True)

    # Get all image files
    image_files = [f for f in os.listdir(image_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    
    # Shuffle the list of image files
    random.shuffle(image_files)

    # Calculate split index
    split_index = int(len(image_files) * split_ratio)

    # Split and copy files
    for i, image_file in enumerate(image_files):
        source_image = os.path.join(image_dir, image_file)
        source_label = os.path.join(
            labels_dir, os.path.splitext(image_file)[0] + ".txt"
        )

        if i < split_index:  # Train set
            dest_image = os.path.join(destination_dir, 'images', 'train', image_file)
            dest_label = os.path.join(destination_dir, 'labels', 'train', os.path.splitext(image_file)[0] + '.txt')
        else:  # Validation set
            dest_image = os.path.join(destination_dir, 'images', 'val', image_file)
            dest_label = os.path.join(destination_dir, 'labels', 'val', os.path.splitext(image_file)[0] + '.txt')

        shutil.copy(source_image, dest_image)
        if os.path.exists(source_label):
            shutil.copy(source_label, dest_label)         


image_dir = labelme_path
labels_dir = output_dir
destination_dir = Path('dataset')

split_dataset(image_dir, labels_dir, destination_dir)
# %%
