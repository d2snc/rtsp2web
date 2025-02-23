import cv2

url = "rtsp://admin:CRPFDC@192.168.0.20:554/cam/realmonitor?channel=1&subtype=0"
cap = cv2.VideoCapture(url)

if not cap.isOpened():
    print("Falha ao abrir o stream.")
else:
    print("Stream aberto com sucesso!")
    ret, frame = cap.read()
    if ret:
        cv2.imshow("Frame", frame)
        cv2.waitKey(0)
    cap.release()
cv2.destroyAllWindows()
