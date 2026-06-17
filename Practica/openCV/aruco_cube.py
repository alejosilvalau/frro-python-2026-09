"""
ArUco 3D Cube — OpenCV + Open3D
Detecta marcadores ArUco (DICT_6X6_250) con la webcam y proyecta
un cubo 3D rojo sobre cada uno.

Open3D construye el mesh (vértices, triángulos, normales).
OpenCV estima la pose y proyecta el mesh sobre el frame.

Requisitos:
    pip install opencv-contrib-python open3d numpy
"""
import sys
import numpy as np
import cv2
from cv2 import aruco

try:
    import open3d as o3d
except ImportError:
    sys.exit("Falta open3d.  Instalalo con:  pip install open3d")

# ── Configuración ─────────────────────────────────────────────────────────────
MARKER_SIZE = 0.05          # Tamaño físico del marcador impreso en metros (5 cm)
DICT_TYPE   = aruco.DICT_6X6_250
CUBE_ALPHA  = 0.88          # Opacidad del cubo

# Esquinas del marcador en su sistema de coordenadas local
# (misma convención que estimatePoseSingleMarkers)
_h = MARKER_SIZE / 2.0
MARKER_OBJ_PTS = np.float32([
    [-_h,  _h, 0],   # top-left
    [ _h,  _h, 0],   # top-right
    [ _h, -_h, 0],   # bottom-right
    [-_h, -_h, 0],   # bottom-left
])

CUBE_EDGES = [
    (0,1),(1,2),(2,3),(3,0),   # base
    (4,5),(5,6),(6,7),(7,4),   # tapa
    (0,4),(1,5),(2,6),(3,7),   # pilares
]


# ── Mesh del cubo (Open3D) ────────────────────────────────────────────────────
def make_cube_mesh(size: float):
    """
    Usa Open3D para construir el cubo.
    Retorna vértices (8,3), triángulos (12,3) y normales por triángulo (12,3).
    Centrado en XY, base en Z=0, tapa en Z=+size (hacia la cámara).
    """
    half = size / 2.0
    mesh = o3d.geometry.TriangleMesh.create_box(size, size, size)
    mesh.translate([-half, -half, 0.0])
    mesh.compute_triangle_normals()

    verts   = np.asarray(mesh.vertices,         dtype=np.float32)   # (8, 3)
    tris    = np.asarray(mesh.triangles,        dtype=np.int32)     # (12, 3)
    normals = np.asarray(mesh.triangle_normals, dtype=np.float32)   # (12, 3)
    return verts, tris, normals


# ── Proyección y dibujo ───────────────────────────────────────────────────────
def draw_cube(frame, verts, tris, normals, rvec, tvec, K, D):
    rvec = rvec.reshape(3, 1)
    tvec = tvec.reshape(3, 1)
    R, _ = cv2.Rodrigues(rvec)

    # Vértices en espacio de cámara (para ordenar por profundidad)
    verts_cam = (R @ verts.T + tvec).T           # (8, 3)

    # Normales en espacio de cámara (para backface culling)
    norms_cam = (R @ normals.T).T                # (12, 3)

    # Proyección a 2D
    pts2d, _ = cv2.projectPoints(verts, rvec, tvec, K, D)
    pts2d = pts2d.reshape(-1, 2).astype(int)

    # Profundidad media por triángulo
    depths = verts_cam[tris, 2].mean(axis=1)     # (12,)

    # Backface culling: cara visible si normal apunta hacia la cámara (nz < 0)
    visible = np.where(norms_cam[:, 2] < 0)[0]

    # Painter's algorithm: de atrás hacia adelante
    vis_sorted = visible[np.argsort(depths[visible])[::-1]]

    overlay = frame.copy()
    for idx in vis_sorted:
        tri = tris[idx]
        pts = pts2d[tri]
        # Iluminación simple: más rojo cuanto más frontal es la normal
        intensity = int(np.clip((-norms_cam[idx, 2]) * 200 + 55, 55, 255))
        cv2.fillConvexPoly(overlay, pts, (0, 0, intensity))

    cv2.addWeighted(overlay, CUBE_ALPHA, frame, 1.0 - CUBE_ALPHA, 0, frame)

    # Aristas
    for a, b in CUBE_EDGES:
        cv2.line(frame, tuple(pts2d[a]), tuple(pts2d[b]), (0, 0, 255), 2)


# ── Main ──────────────────────────────────────────────────────────────────────
def build_camera_matrix(w: int, h: int) -> np.ndarray:
    f = float(max(w, h))
    return np.array([[f, 0, w / 2.0],
                     [0, f, h / 2.0],
                     [0, 0,     1.0]], dtype=np.float64)


def main():
    # Mesh del cubo — se construye una sola vez con Open3D
    verts, tris, normals = make_cube_mesh(MARKER_SIZE)
    print(f"Mesh Open3D listo: {len(verts)} vértices, {len(tris)} triángulos")

    aruco_dict = aruco.getPredefinedDictionary(DICT_TYPE)
    detector   = aruco.ArucoDetector(aruco_dict, aruco.DetectorParameters())

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        sys.exit("Error: no se puede abrir la webcam.")

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    K = build_camera_matrix(W, H)
    D = np.zeros((4, 1), dtype=np.float64)

    print("ArUco 3D Cube  |  q = salir")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = detector.detectMarkers(gray)

        count = 0
        if ids is not None:
            aruco.drawDetectedMarkers(frame, corners, ids)
            for corner, mid in zip(corners, ids.flatten()):
                img_pts = corner[0].astype(np.float32)
                ok, rvec, tvec = cv2.solvePnP(
                    MARKER_OBJ_PTS, img_pts, K, D,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE,
                )
                if ok:
                    draw_cube(frame, verts, tris, normals, rvec, tvec, K, D)
                    count += 1

        cv2.putText(frame, f"Marcadores: {count}/6",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow("ArUco 3D Cube", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
