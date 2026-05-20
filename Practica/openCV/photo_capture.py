import cv2
import os
from datetime import datetime
import time

def create_output_directory():
    """Create output directory if it doesn't exist"""
    output_dir = "captured_photos"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def countdown_and_capture(cap, output_dir, photo_count):
    """Perform countdown and capture a photo"""
    countdown_start = 3
    countdown_duration = 1000  # milliseconds
    frame_count = 0
    frames_per_second = 30
    
    # Countdown loop
    while countdown_start >= 0:
        start_time = time.time() * 1000  # Convert to milliseconds
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error reading frame")
                return False
            
            # Display countdown on frame
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 3
            font_color = (0, 0, 255)  # Red
            thickness = 3
            
            # Add countdown text
            text = str(countdown_start) if countdown_start > 0 else "SMILE!"
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = (frame.shape[0] + text_size[1]) // 2
            
            cv2.putText(frame, text, (text_x, text_y), font, font_scale, font_color, thickness)
            
            # Show frame with countdown
            cv2.imshow("Camera - Press SPACE to capture, Q to quit", frame)
            cv2.waitKey(33)  # ~30fps
            
            # Check if 1 second has passed
            elapsed = time.time() * 1000 - start_time
            if elapsed >= countdown_duration:
                break
        
        countdown_start -= 1
    
    # Capture the photo
    ret, frame = cap.read()
    if not ret:
        print("Error capturing frame")
        return False
    
    # Generate filename with date and time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    filename = f"photo_{timestamp}_#{photo_count}.jpg"
    filepath = os.path.join(output_dir, filename)
    
    # Save the photo
    cv2.imwrite(filepath, frame)
    print(f"Photo saved: {filepath}")
    
    return True

def main():
    """Main program"""
    output_dir = create_output_directory()
    
    # Open camera
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Cannot open camera")
        return
    
    print("Camera opened successfully!")
    print("Press SPACE to capture photo, Q to quit")
    print("=" * 50)
    
    photo_count = 1
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error reading frame")
            break
        
        # Display live camera feed
        cv2.putText(
            frame, 
            f"Photo #{photo_count} | Press SPACE to capture, Q to quit", 
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        cv2.imshow("Camera - Press SPACE to capture, Q to quit", frame)
        
        # Check for key press
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Exiting...")
            break
        elif key == ord(' '):  # SPACE key
            print(f"\nCapturing photo #{photo_count}...")
            countdown_and_capture(cap, output_dir, photo_count)
            photo_count += 1
            print(f"Ready for photo #{photo_count}")
            print("=" * 50)
    
    # Release resources
    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed.")

if __name__ == "__main__":
    main()
