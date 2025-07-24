import base64
from PIL import Image
import io
from typing import Union, Optional

def convert_screenshot_to_image(screenshot_data: Union[bytes, str], target_size: tuple = (1920, 1080)) -> Optional[Image.Image]:
    """
    Convert screenshot data (bytes or base64 string) to PIL Image with specified size.
    
    Args:
        screenshot_data: Screenshot data as bytes or base64 encoded string
        target_size: Target size as (width, height) tuple, default is (1920, 1080)
    
    Returns:
        PIL Image object resized to target size, or None if conversion fails
    """
    try:
        # Handle different input types
        if isinstance(screenshot_data, str):
            # If it's a string, assume it's base64 encoded
            image_bytes = base64.b64decode(screenshot_data)
        elif isinstance(screenshot_data, bytes):
            # First try to use bytes directly (most common case for VMware)
            image_bytes = screenshot_data
        else:
            raise ValueError(f"Unsupported screenshot data type: {type(screenshot_data)}")
        
        # Try to convert bytes to PIL Image
        try:
            image = Image.open(io.BytesIO(image_bytes))
        except Exception as direct_error:
            # If direct bytes fail, try base64 decoding
            try:
                decoded_bytes = base64.b64decode(image_bytes)
                image = Image.open(io.BytesIO(decoded_bytes))
            except Exception as base64_error:
                print(f"Failed to decode image data: {direct_error}")
                return None
        
        # Resize to target size using high-quality resampling
        resized_image = image.resize(target_size, Image.Resampling.LANCZOS)
        
        return resized_image
        
    except Exception as e:
        print(f"Error converting screenshot: {e}")
        return None

def save_screenshot_as_png(screenshot_data: Union[bytes, str], 
                          filename: str = "screenshot.png", 
                          target_size: tuple = (1920, 1080)) -> bool:
    """
    Convert and save screenshot data as PNG file.
    
    Args:
        screenshot_data: Screenshot data as bytes or base64 encoded string
        filename: Output filename
        target_size: Target size as (width, height) tuple
    
    Returns:
        True if successful, False otherwise
    """
    image = convert_screenshot_to_image(screenshot_data, target_size)
    if image:
        image.save(filename, "PNG")
        print(f"Screenshot saved as {filename} with size {image.size}")
        return True
    return False

def screenshot_to_bytes(screenshot_data: Union[bytes, str], 
                       target_size: tuple = (1920, 1080), 
                       format: str = "PNG") -> Optional[bytes]:
    """
    Convert screenshot data to bytes in specified format and size.
    
    Args:
        screenshot_data: Screenshot data as bytes or base64 encoded string
        target_size: Target size as (width, height) tuple
        format: Output format (PNG, JPEG, etc.)
    
    Returns:
        Image bytes in specified format, or None if conversion fails
    """
    image = convert_screenshot_to_image(screenshot_data, target_size)
    if image:
        output_buffer = io.BytesIO()
        image.save(output_buffer, format=format)
        return output_buffer.getvalue()
    return None

# Example usage function
def process_vmware_screenshot(obs_screenshot):
    """
    Process VMware screenshot from obs["screenshot"] and convert to 1920x1080.
    
    Args:
        obs_screenshot: Screenshot data from obs["screenshot"]
    
    Returns:
        dict with processed image information
    """
    if obs_screenshot is None:
        return {"success": False, "message": "No screenshot data"}
    
    print(f"Original screenshot type: {type(obs_screenshot)}")
    print(f"Original screenshot length: {len(obs_screenshot) if hasattr(obs_screenshot, '__len__') else 'N/A'}")
    
    # Convert to PIL Image
    image = convert_screenshot_to_image(obs_screenshot, (1920, 1080))
    
    if image:
        # Save as file
        image.save("vmware_screenshot_1920x1080.png")
        
        # Convert back to bytes if needed
        image_bytes = screenshot_to_bytes(obs_screenshot, (1920, 1080))
        
        return {
            "success": True,
            "original_size": "Unknown",
            "resized_size": image.size,
            "saved_file": "vmware_screenshot_1920x1080.png",
            "image_bytes_length": len(image_bytes) if image_bytes else 0,
            "image_object": image
        }
    else:
        return {"success": False, "message": "Failed to convert screenshot"}