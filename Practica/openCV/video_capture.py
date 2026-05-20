import cv2
import os
from datetime import datetime
import time

def create_output_directory():
    """Create output directory if it doesn't exist"""
    output_dir = "captured_videos"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    return output_dir

def countdown_and_record(cap, output_dir, video_count):
    """Perform countdown and record a video"""
    countdown_start = 3
    countdown_duration = 1000  # milliseconds
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Generate filename with date and time
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
    filename = f"video_{timestamp}_#{video_count}.mp4"
    filepath = os.path.join(output_dir, filename)
    
    # Create video writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filepath, fourcc, fps, (width, height))
    
    if not out.isOpened():
        print("Error: Could not create video writer")
        return False
    
    # Countdown loop
    while countdown_start >= 0:
        start_time = time.time() * 1000  # Convert to milliseconds
        
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Error reading frame")
                out.release()
                return False
            
            # Display countdown on frame
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 3
            font_color = (0, 0, 255)  # Red
            thickness = 3
            
            # Add countdown text
            text = str(countdown_start) if countdown_start > 0 else "REC"
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
            text_x = (frame.shape[1] - text_size[0]) // 2
            text_y = (frame.shape[0] + text_size[1]) // 2
            
            cv2.putText(frame, text, (text_x, text_y), font, font_scale, font_color, thickness)
            
            # Show frame with countdown
            cv2.imshow("Camera - Press SPACE to record, Q to quit", frame)
            cv2.waitKey(33)  # ~30fps
            
            # Check if 1 second has passed
            elapsed = time.time() * 1000 - start_time
            if elapsed >= countdown_duration:
                break
        
        countdown_start -= 1
    
    print(f"Recording video #{video_count}...")
    print("Press SPACE to stop recording")
    
    # Recording loop - records until SPACE is pressed or 5 minutes max
    recording_start = time.time()
    max_duration = 300  # 5 minutes max
    
    while time.time() - recording_start < max_duration:
        ret, frame = cap.read()
        if not ret:
            print("Error reading frame")
            break
        
        # Add recording indicator and timer
        font = cv2.FONT_HERSHEY_SIMPLEX
        elapsed = int(time.time() - recording_start)
        minutes = elapsed // 60
        seconds = elapsed % 60
        
        # Red circle for REC indicator
        cv2.circle(frame, (50, 50), 15, (0, 0, 255), -1)
        
        # Recording time
        time_text = f"REC {minutes:02d}:{seconds:02d}"
        cv2.putText(frame, time_text, (80, 60), font, 1.2, (0, 0, 255), 2)
        
        # Instruction text
        cv2.putText(frame, "Press SPACE to stop", (10, frame.shape[0] - 20), font, 0.7, (0, 255, 0), 2)
        
        # Write frame to video
        out.write(frame)
        
        # Show frame
        cv2.imshow("Camera - Press SPACE to record, Q to quit", frame)
        
        # Check for key press
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):  # SPACE key to stop recording
            print("Recording stopped")
            break
        elif key == ord('q'):
            print("Exiting during recording...")
            out.release()
            return "quit"
    
    # Release video writer
    out.release()
    print(f"Video saved: {filepath}")
    
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
    print("Press SPACE to start recording, Q to quit")
    print("=" * 50)
    
    video_count = 1
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error reading frame")
            break
        
        # Display live camera feed
        cv2.putText(
            frame, 
            f"Video #{video_count} | Press SPACE to record, Q to quit", 
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2
        )
        
        cv2.imshow("Camera - Press SPACE to record, Q to quit", frame)
        
        # Check for key press
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Exiting...")
            break
        elif key == ord(' '):  # SPACE key
            print(f"\nStarting video #{video_count}...")
            result = countdown_and_record(cap, output_dir, video_count)
            if result == "quit":
                break
            video_count += 1
            print(f"Ready for video #{video_count}")
            print("=" * 50)
    
    # Release resources
    cap.release()
    cv2.destroyAllWindows()
    print("Camera closed.")

if __name__ == "__main__":
    main()
