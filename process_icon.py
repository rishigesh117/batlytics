import os
from PIL import Image, ImageChops

def process_icon(input_path, output_path):
    print(f"Loading {input_path}")
    img = Image.open(input_path).convert('RGBA')
    
    # The image has a dark blue background (roughly #060e29) but might have black padding.
    # Let's find the bounding box of the non-black pixels.
    # Create a completely black image of the same size to use as a difference baseline
    bg = Image.new('RGBA', img.size, (0, 0, 0, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    
    if bbox:
        print(f"Cropping to non-black bounding box: {bbox}")
        img = img.crop(bbox)
    else:
        print("No bounding box found, using original image.")
        
    # The cropped image is the actual logo with the dark blue background.
    # The background color of the logo itself (e.g. from the top center pixel)
    bg_color = img.getpixel((img.width // 2, 5))
    print(f"Detected background color: {bg_color}")
    
    # We want a 1024x1024 final image
    final_size = 1024
    final_img = Image.new('RGBA', (final_size, final_size), bg_color)
    
    # For Android adaptive icons, the safe zone is the inner 66% (which is a diameter of 682px)
    # The logo should fit comfortably inside 682x682.
    safe_zone = 682
    
    # Calculate scale factor to fit the cropped image into safe_zone x safe_zone
    # But wait, the cropped image ALREADY has some background padding.
    # Let's just scale the cropped image to 1024x1024 and see if it looks right?
    # If the user's image is already perfectly designed, we just want to expand the edges to 1024x1024 without cropping.
    
    # Let's scale the cropped image such that its largest dimension is 1024.
    # No, Android adaptive icon requires the important content to be in the center 682x682.
    # The user's image is a square (or close to it) with the logo taking up most of it.
    # Let's resize the cropped image so it fills 800x800, giving it enough padding to 1024x1024.
    target_content_size = 800
    scale = target_content_size / max(img.width, img.height)
    new_size = (int(img.width * scale), int(img.height * scale))
    
    img_resized = img.resize(new_size, Image.Resampling.LANCZOS)
    
    # Paste into the center
    paste_x = (final_size - new_size[0]) // 2
    paste_y = (final_size - new_size[1]) // 2
    
    # To avoid sharp edges where we pasted (if the background color isn't perfectly uniform),
    # actually the background is uniform dark blue in the corners, so it should blend seamlessly.
    final_img.paste(img_resized, (paste_x, paste_y), img_resized)
    
    final_img.save(output_path, "PNG")
    print(f"Saved adaptive icon to {output_path}")

if __name__ == "__main__":
    input_file = r"C:\Users\sivab\.gemini\antigravity\brain\c7674233-b68f-4bad-b1d2-cee99e1387bf\media__1782907606114.jpg"
    output_file = r"c:\project\cricket score app\logo.png"
    process_icon(input_file, output_file)
