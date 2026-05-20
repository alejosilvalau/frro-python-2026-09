import cv2

imagen = cv2.imread('logo.png')

cv2.imshow('Imagen logo', imagen)

cv2.waitKey(0)
cv2.destroyAllWindows()