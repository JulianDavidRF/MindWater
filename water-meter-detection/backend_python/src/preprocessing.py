import cv2
from pathlib import Path

def process_image(image_path:Path,per_width:int=45, per_height:int=45):
    image = cv2.imread(str(image_path))
    image = _crop_image(image=image,per_width=per_width, per_height=per_height)
    image = _convert_grayscale(image=image)
    return image

def _crop_image(image, per_width, per_height):
    img_height, img_width = image.shape[:2]

    crop_width = int(img_width*(per_width/100))
    crop_height = int(img_height*(per_height/100))

    center_x = img_width // 2
    center_y = img_height // 2

    x1 = center_x - crop_width // 2
    y1 = center_y - crop_height // 2
    x2 = center_x + crop_width // 2
    y2 = center_y + crop_height // 2

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(img_width, x2)
    y2 = min(img_height, y2)
    return image[y1:y2, x1:x2]

def _convert_grayscale(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)