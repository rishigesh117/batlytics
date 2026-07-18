import os
from PIL import Image, ImageDraw

def process_icon(input_path, output_path):
    print(f"Loading {input_path}")
    img = Image.open(input_path).convert('RGB')
    
    width, height = img.size
    
    # Get true background color
    bg_color_rgb = img.getpixel((width // 2, height // 10))
    print(f"Detected background color: {bg_color_rgb}")
    
    # Find bounding box (ignore black pixels where R+G+B < 15)
    min_x = width
    min_y = height
    max_x = 0
    max_y = 0
    
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if r + g + b > 15:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
                
    if min_x >= max_x or min_y >= max_y:
        print("Image is entirely black?")
        return
        
    print(f"Cropping to bbox: x={min_x}-{max_x}, y={min_y}-{max_y}")
    cropped = img.crop((min_x, min_y, max_x, max_y))
    
    # Floodfill the 4 corners to remove black rounded borders
    ImageDraw.floodfill(cropped, (0, 0), bg_color_rgb, thresh=20)
    ImageDraw.floodfill(cropped, (cropped.width-1, 0), bg_color_rgb, thresh=20)
    ImageDraw.floodfill(cropped, (0, cropped.height-1), bg_color_rgb, thresh=20)
    ImageDraw.floodfill(cropped, (cropped.width-1, cropped.height-1), bg_color_rgb, thresh=20)
    
    final_size = 1024
    final_img = Image.new('RGB', (final_size, final_size), bg_color_rgb)
    
    target_size = 750
    scale = target_size / max(cropped.width, cropped.height)
    new_w, new_h = int(cropped.width * scale), int(cropped.height * scale)
    
    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    px = (final_size - new_w) // 2
    py = (final_size - new_h) // 2
    final_img.paste(resized, (px, py))
    
    final_img.save(output_path, "PNG")
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    input_file = r"C:\Users\sivab\.gemini\antigravity\brain\c7674233-b68f-4bad-b1d2-cee99e1387bf\media__1782907606114.jpg"
    output_file = r"c:\project\cricket score app\logo.png"
    process_icon(input_file, output_file)
