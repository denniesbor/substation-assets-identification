# ------------------------------------------------------------------
# Description: This file contains the training code for a computer vision model
# Using YOLOv8 architecture.
# A sample google earth imagery of substations is used to train the model.
# Author: Dennies Bor
# Date: 21-08-2024
# ------------------------------------------------------------------
# %%
from pathlib import Path
import os
from ultralytics import YOLO

parent_dir = Path(__file__).resolve().parent.parent

# Load model yolov8
model = YOLO("yolov8n.yaml")  # build a new model from YAML
model = YOLO("yolov8n.pt")  # or load a pretrained model

# Train the model
# results = model.train(data="./data.yml", epochs=100, imgsz=640, device="cuda", save=True)

# %%

import cv2
import numpy as np

# Run inference on a single image
# Load the best saved checkpoint
best_weights_path = parent_dir / "runs/detect/train5/weights/best.pt"

model = YOLO(best_weights_path)

# Load a single image
image_path = "screenshot_669594105.png"
image = cv2.imread(str(image_path))

# Perform inference
results = model(image)

# Visualize the results on the image
for result in results:
    boxes = result.boxes.xyxy.cpu().numpy()
    classes = result.boxes.cls.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()

    for box, cls, conf in zip(boxes, classes, confidences):
        x1, y1, x2, y2 = box.astype(int)
        label = f"{model.names[int(cls)]}: {conf:.2f}"
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2
        )

# Display the image
cv2.imshow("YOLOv8 Detection", image)
cv2.waitKey(0)
cv2.destroyAllWindows()

# Save the output image
output_path = "output_detection.jpg"
cv2.imwrite(output_path, image)
print(f"Output image saved to {output_path}")

# %%
