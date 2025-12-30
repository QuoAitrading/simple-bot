"""
Resize rainbow gif to be wider (extend it).
"""
from PIL import Image, ImageSequence
import os

# Use absolute paths
params_dir = os.path.dirname(__file__)
source = os.path.join(params_dir, 'line-rainbow.gif')
target = os.path.join(params_dir, 'line-rainbow-wide.gif')
target_width = 620  # Covers most of Discord chat width

if not os.path.exists(source):
    print(f"Error: {source} not found")
    exit(1)

try:
    im = Image.open(source)
    w, h = im.size
    print(f"Original size: {w}x{h}")
    
    frames = []
    
    # Handle duration/loop
    duration = im.info.get('duration', 40)
    loop = im.info.get('loop', 0)
    
    for frame in ImageSequence.Iterator(im):
        # Stretch width, keep height
        # Use LANCZOS if available, else ANTIALIAS
        resample = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.ANTIALIAS
        new_frame = frame.copy().resize((target_width, h), resample).convert("RGBA")
        frames.append(new_frame)
        
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        loop=loop,
        duration=duration,
        optimize=True,
        disposal=2
    )
    print(f"Saved wide version to {target}")

except Exception as e:
    print(f"Error resizing: {e}")
