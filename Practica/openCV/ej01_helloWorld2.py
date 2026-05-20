import cv2
# cap = cv2.VideoCapture(0)
cap = cv2.VideoCapture('video.mp4')
# cap = cv2.VideoCapture('rtsp://192.168.1.2:8080/out.h264')

while True:
    ret, frame = cap.read()
    if not ret:
        print("No se puede leer el frame")
        break

    cv2.imshow('mi primer open CV', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()