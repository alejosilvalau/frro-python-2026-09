import cv2
import numpy as np
from collections import OrderedDict

# ──────────────────────────────────────────────
#  Centroid Tracker
#  Asocia detecciones entre frames usando distancia euclidiana
# ──────────────────────────────────────────────
class CentroidTracker:
    def __init__(self, max_disappeared=30, max_distance=80):
        self.next_id = 0
        self.objects = OrderedDict()      # id -> centroid actual
        self.disappeared = OrderedDict()  # id -> frames sin detectar
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance

    def register(self, centroid):
        self.objects[self.next_id] = centroid
        self.disappeared[self.next_id] = 0
        self.next_id += 1

    def deregister(self, object_id):
        del self.objects[object_id]
        del self.disappeared[object_id]

    def update(self, rects):
        # Sin detecciones: incrementar desaparecidos
        if len(rects) == 0:
            for oid in list(self.disappeared.keys()):
                self.disappeared[oid] += 1
                if self.disappeared[oid] > self.max_disappeared:
                    self.deregister(oid)
            return self.objects

        # Calcular centroides de las detecciones actuales
        input_centroids = np.array(
            [(x + w // 2, y + h // 2) for (x, y, w, h) in rects], dtype="int"
        )

        if len(self.objects) == 0:
            for c in input_centroids:
                self.register(tuple(c))
            return self.objects

        object_ids = list(self.objects.keys())
        object_centroids = np.array(list(self.objects.values()), dtype="int")

        # Matriz de distancias: objetos existentes vs detecciones nuevas
        D = np.linalg.norm(
            object_centroids[:, np.newaxis] - input_centroids[np.newaxis, :], axis=2
        )

        rows = D.min(axis=1).argsort()
        cols = D.argmin(axis=1)[rows]

        used_rows, used_cols = set(), set()

        for row, col in zip(rows, cols):
            if row in used_rows or col in used_cols:
                continue
            if D[row, col] > self.max_distance:
                continue
            oid = object_ids[row]
            self.objects[oid] = tuple(input_centroids[col])
            self.disappeared[oid] = 0
            used_rows.add(row)
            used_cols.add(col)

        # Objetos no emparejados → incrementar desaparecidos
        for row in set(range(D.shape[0])) - used_rows:
            oid = object_ids[row]
            self.disappeared[oid] += 1
            if self.disappeared[oid] > self.max_disappeared:
                self.deregister(oid)

        # Detecciones nuevas sin emparejar → registrar
        for col in set(range(D.shape[1])) - used_cols:
            self.register(tuple(input_centroids[col]))

        return self.objects


# ──────────────────────────────────────────────
#  Configuración
# ──────────────────────────────────────────────
ENTRADA_DESDE_ABAJO = True   # True: subir  al bus = venir desde abajo del frame
                              # False: subir al bus = venir desde arriba del frame
LINE_RATIO = 0.5              # Posición vertical de la línea (0.0 = arriba, 1.0 = abajo)

# ──────────────────────────────────────────────
#  HOG People Detector
# ──────────────────────────────────────────────
hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

tracker = CentroidTracker(max_disappeared=30, max_distance=80)

# Estado por ID: qué lado de la línea ocupaba en el frame anterior
previous_side = {}   # id -> 'above' | 'below'
entraron = 0
salieron = 0

frame_count = 0
DETECT_EVERY = 3  # Detectar cada N frames para mejor rendimiento

while True:
    ret, frame = cap.read()
    if not ret:
        break

    height, width = frame.shape[:2]
    line_y = int(height * LINE_RATIO)

    rects = []
    frame_count += 1

    if frame_count % DETECT_EVERY == 0:
        # Reducir resolución para detección → más rápido
        small = cv2.resize(frame, (320, 240))
        scale_x = width / 320
        scale_y = height / 240

        boxes, _ = hog.detectMultiScale(
            small,
            winStride=(8, 8),
            padding=(4, 4),
            scale=1.05,
        )

        for (x, y, w, h) in boxes:
            rects.append((
                int(x * scale_x), int(y * scale_y),
                int(w * scale_x), int(h * scale_y)
            ))

        # Non-maximum suppression para eliminar detecciones duplicadas
        if len(rects) > 0:
            r = np.array([[x, y, x + w, y + h] for (x, y, w, h) in rects])
            pick = []
            x1, y1, x2, y2 = r[:, 0], r[:, 1], r[:, 2], r[:, 3]
            area = (x2 - x1 + 1) * (y2 - y1 + 1)
            idxs = np.argsort(y2)
            while len(idxs) > 0:
                last = idxs[-1]
                pick.append(last)
                xx1 = np.maximum(x1[last], x1[idxs[:-1]])
                yy1 = np.maximum(y1[last], y1[idxs[:-1]])
                xx2 = np.minimum(x2[last], x2[idxs[:-1]])
                yy2 = np.minimum(y2[last], y2[idxs[:-1]])
                w_i = np.maximum(0, xx2 - xx1 + 1)
                h_i = np.maximum(0, yy2 - yy1 + 1)
                overlap = (w_i * h_i) / area[idxs[:-1]]
                idxs = np.delete(idxs, np.concatenate(([len(idxs) - 1], np.where(overlap > 0.65)[0])))
            rects = [(r[i][0], r[i][1], r[i][2] - r[i][0], r[i][3] - r[i][1]) for i in pick]

    objects = tracker.update(rects)

    # ── Detectar cruces de línea ──
    for oid, (cx, cy) in objects.items():
        current_side = 'below' if cy > line_y else 'above'

        if oid in previous_side:
            prev_side = previous_side[oid]
            if prev_side != current_side:
                if ENTRADA_DESDE_ABAJO:
                    if prev_side == 'below' and current_side == 'above':
                        entraron += 1
                    elif prev_side == 'above' and current_side == 'below':
                        salieron += 1
                else:
                    if prev_side == 'above' and current_side == 'below':
                        entraron += 1
                    elif prev_side == 'below' and current_side == 'above':
                        salieron += 1

        previous_side[oid] = current_side

    # Limpiar IDs que ya no están siendo trackeados
    active_ids = set(objects.keys())
    previous_side = {k: v for k, v in previous_side.items() if k in active_ids}

    # ── Dibujar ──
    # Línea de conteo
    cv2.line(frame, (0, line_y), (width, line_y), (0, 255, 255), 2)
    cv2.putText(frame, "LINEA DE CONTEO", (10, line_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # Bounding boxes y centroides
    for (x, y, w, h) in rects:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 200, 0), 2)

    for oid, (cx, cy) in objects.items():
        color = (0, 0, 255) if cy > line_y else (255, 100, 0)
        cv2.circle(frame, (cx, cy), 5, color, -1)
        cv2.putText(frame, f"ID {oid}", (cx - 15, cy - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    # Panel de contadores
    panel_y = 10
    cv2.rectangle(frame, (0, 0), (220, 80), (0, 0, 0), -1)
    cv2.putText(frame, f"Entraron: {entraron}", (10, panel_y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 100), 2)
    cv2.putText(frame, f"Salieron: {salieron}", (10, panel_y + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 100, 255), 2)
    cv2.putText(frame, f"En bus:   {max(0, entraron - salieron)}", (10, panel_y + 78),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

    cv2.imshow("Bus - Contador de Pasajeros  [Q] salir  [R] reset", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('r'):
        entraron = 0
        salieron = 0
        previous_side.clear()
        tracker = CentroidTracker(max_disappeared=30, max_distance=80)
        print("Contadores reseteados")

print(f"\nResumen final → Entraron: {entraron}  |  Salieron: {salieron}  |  En bus: {max(0, entraron - salieron)}")
cap.release()
cv2.destroyAllWindows()
