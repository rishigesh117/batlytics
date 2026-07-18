import os
from PIL import Image, ImageChops, ImageDraw
import numpy as np

def process_icon(input_path, output_path):
    print(f"Loading {input_path}")
    img = Image.open(input_path).convert('RGB')
    
    # Convert to numpy array for easier processing
    arr = np.array(img)
    
    # The image has black padding/rounded corners. We want to find the true dark blue background color.
    # Let's sample a few pixels that are likely in the background (top center, slightly down)
    h, w, _ = arr.shape
    bg_color_rgb = tuple(arr[h//10, w//2])
    print(f"Detected background color: {bg_color_rgb}")
    
    # We want to identify the bounding box of the actual logo + blue background, ignoring the pure black (0,0,0) or (1,0,2) borders
    # Let's threshold the image to find non-black pixels.
    # Sum of RGB channels > 10 to ignore near-black
    mask = np.sum(arr, axis=2) > 10
    
    # Find bounding box
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    if not np.any(rows) or not np.any(cols):
        print("Image is entirely black?")
        return
        
    ymin, ymax = np.where(rows)[0][[0, -1]]
    xmin, xmax = np.where(cols)[0][[0, -1]]
    
    print(f"Cropping to bbox: x={xmin}-{xmax}, y={ymin}-{ymax}")
    cropped = img.crop((xmin, ymin, xmax, ymax))
    
    # Now, the cropped image still has rounded corners (black pixels in the corners).
    # Since Android adaptive icons require the background to be full bleed (no rounded corners baked in),
    # we need to fill the corners with the dark blue background color.
    # To do this, we can just create a mask of the near-black pixels and fill them.
    # But wait, there might be black inside the logo (like the cricket ball seams)?
    # Better yet, since we know it's a rounded rectangle, we can just paste the cropped image onto a full dark-blue background,
    # and then manually fill the 4 corners with dark blue.
    # Or, simpler: any pixel near the edge that is near-black gets replaced with bg_color.
    
    cropped_arr = np.array(cropped)
    ch, cw, _ = cropped_arr.shape
    
    # Flood fill the 4 corners
    from skimage.morphology import flood_fill
    # skimage might not be available, let's do a simple BFS or just use PIL ImageDraw for the corners
    # A simpler way: we know the background color. We can create a 1024x1024 image filled with bg_color.
    final_size = 1024
    final_img = Image.new('RGB', (final_size, final_size), bg_color_rgb)
    
    # Android adaptive icon safe zone is 682x682.
    # The logo (text + graph + ball) is inside the cropped area.
    # Let's resize the cropped area so it fits nicely inside the safe zone, say 680x680.
    # BUT wait! If the user wants the blue background to just extend, and the logo to remain its relative size...
    # The user said: "Make sure the icon fills the safe area correctly so it displays properly in the launcher without being cut off".
    
    # Let's make the background transparent where appropriate?
    # "Ensure the icon has transparent edges where appropriate"
    # Actually, Android adaptive icons shouldn't have transparent edges, they must have a solid background layer and a foreground layer.
    # But Buildozer uses a single PNG and Android scales it. If we use a solid background, it works perfectly.
    
    # Since we can't easily distinguish the black corners from black in the logo without flood fill,
    # let's just use a distance-from-center mask.
    
    # Let's just create a completely transparent image, and extract ONLY the non-background pixels? No, the user wants the dark blue background!
    # "Keep the same Batlytics logo design exactly as it is. Do not redesign or change the colors..."
    
    # Let's use PIL's floodfill to replace the black corners with bg_color!
    try:
        from PIL import ImageDraw
        ImageDraw.floodfill(cropped, (0, 0), bg_color_rgb, thresh=20)
        ImageDraw.floodfill(cropped, (cw-1, 0), bg_color_rgb, thresh=20)
        ImageDraw.floodfill(cropped, (0, ch-1), bg_color_rgb, thresh=20)
        ImageDraw.floodfill(cropped, (cw-1, ch-1), bg_color_rgb, thresh=20)
    except Exception as e:
        print("Floodfill failed:", e)

    # Now resize the cropped (and corner-filled) image so the content fits well.
    # Let's make the cropped image size around 750x750 so it's large but safe.
    target_size = 750
    scale = target_size / max(cw, ch)
    new_w, new_h = int(cw * scale), int(ch * scale)
    
    resized = cropped.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Paste into center
    px = (final_size - new_w) // 2
    py = (final_size - new_h) // 2
    final_img.paste(resized, (px, py))
    
    # Save as PNG
    final_img.save(output_path, "PNG")
    print(f"Saved to {output_path}")

if __name__ == "__main__":
    input_file = r"C:\Users\sivab\.gemini\antigravity\brain\c7674233-b68f-4bad-b1d2-cee99e1387bf\media__1782907606114.jpg"
    output_file = r"c:\project\cricket score app\logo.png"
    process_icon(input_file, output_file)
