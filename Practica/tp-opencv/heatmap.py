import sys
import time
import argparse
import cv2
import numpy as np


SCALE = 0.5
FLOW_ITERATIONS = 2
FLOW_WINSIZE = 9
FLOW_LEVELS = 3
OVERLAY_EVERY = 3
DILATE_KERNEL_SIZE = 5
DILATE_ITER = 2
GAUSS_KERNEL = 15


def build_parser():
    p = argparse.ArgumentParser(
        description="Detector de jugadores de futbol con Optical Flow y mapa de calor 2D"
    )
    p.add_argument("video", help="Ruta al archivo de video")
    p.add_argument(
        "--threshold",
        type=float,
        default=1.5,
        help="Umbral de magnitud para detectar movimiento (default: 1.5)",
    )
    p.add_argument(
        "--output",
        default="heatmap_output.png",
        help="Nombre del archivo de salida (default: heatmap_output.png)",
    )
    return p


def draw_hud(display, frame_idx, total_frames, analyzed, elapsed):
    h, w = display.shape[:2]
    progress = (frame_idx + 1) / total_frames if total_frames > 0 else 0

    cv2.putText(
        display, "ANALIZANDO...", (30, 45),
        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3, cv2.LINE_AA,
    )
    info = f"F:{frame_idx+1}/{total_frames} | A:{analyzed} | {elapsed:.1f}s"
    cv2.putText(
        display, info, (30, 80),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2, cv2.LINE_AA,
    )

    bar_w, bar_h = 400, 20
    x0 = (w - bar_w) // 2
    y0 = h - 50
    cv2.rectangle(display, (x0, y0), (x0 + bar_w, y0 + bar_h), (50, 50, 50), -1)
    cv2.rectangle(display, (x0, y0), (x0 + int(bar_w * progress), y0 + bar_h), (0, 200, 0), -1)
    cv2.rectangle(display, (x0, y0), (x0 + bar_w, y0 + bar_h), (200, 200, 200), 2)


def main():
    args = build_parser().parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"Error: no se pudo abrir {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    sw, sh = int(width * SCALE), int(height * SCALE)

    print(f"Video: {args.video}")
    print(f"Resolucion: {width}x{height} -> flow en {sw}x{sh} | FPS: {fps:.1f} | Frames: {total_frames}")

    prev_gray = None
    heatmap_acc = np.zeros((height, width), dtype=np.float32)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (DILATE_KERNEL_SIZE, DILATE_KERNEL_SIZE))
    frame_idx = 0
    analyzed = 0
    t0 = time.time()

    window_name = "Analisis - Jugadores de Futbol"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 540)
    display_delay = max(1, int(1000 / (fps * 4)))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray_full = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray_full, (sw, sh))

        if prev_gray is not None:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray, gray_small, None,
                pyr_scale=0.5, levels=FLOW_LEVELS, winsize=FLOW_WINSIZE,
                iterations=FLOW_ITERATIONS, poly_n=5, poly_sigma=1.2, flags=0,
            )

            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

            mask = np.zeros_like(mag)
            mask[mag > args.threshold] = 1.0
            mask = cv2.dilate(mask, kernel, iterations=DILATE_ITER)
            mask = cv2.GaussianBlur(mask, (GAUSS_KERNEL, GAUSS_KERNEL), 0)

            mask_full = cv2.resize(mask, (width, height))
            heatmap_acc += mask_full
            analyzed += 1

        prev_gray = gray_small

        if frame_idx % OVERLAY_EVERY == 0:
            elapsed = time.time() - t0
            display = frame.copy()
            draw_hud(display, frame_idx, total_frames, analyzed, elapsed)

            if analyzed > 0 and np.max(heatmap_acc) > 0:
                norm = heatmap_acc / np.max(heatmap_acc)
                blurred = cv2.GaussianBlur((norm * 255).astype(np.uint8), (15, 15), 0)
                colored = cv2.applyColorMap(blurred, cv2.COLORMAP_JET)
                heat_resized = cv2.resize(colored, (width, height))
                display = cv2.addWeighted(heat_resized, 0.35, display, 0.65, 0)

            cv2.imshow(window_name, display)

        key = cv2.waitKey(display_delay) & 0xFF
        if key == ord("q"):
            print("Analisis cancelado por el usuario.")
            break

        frame_idx += 1

    cap.release()
    elapsed = time.time() - t0

    if analyzed == 0:
        print("No se analizo ningun frame.")
        sys.exit(1)

    print(f"Analizados {analyzed} frames en {elapsed:.1f}s ({analyzed/elapsed:.1f} fps)")

    norm = heatmap_acc / np.max(heatmap_acc)
    blurred = cv2.GaussianBlur((norm * 255).astype(np.uint8), (15, 15), 0)
    final_heatmap = cv2.applyColorMap(blurred, cv2.COLORMAP_JET)

    cv2.imwrite(args.output, final_heatmap)
    print(f"Mapa de calor guardado en: {args.output}")

    cv2.imshow("Mapa de Calor - Final", final_heatmap)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
