import cv2
import numpy as np
import sys
from pathlib import Path


MAX_DIST = 80
MIN_AREA = 800
HIST_LEN = 10


def select_line(frame, win="Click start & end of counting line. Press any key when done."):
    pts = []

    def click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            pts.append((x, y))
            cv2.circle(param, (x, y), 5, (0, 255, 255), -1)
            if len(pts) == 2:
                cv2.line(param, pts[0], pts[1], (0, 255, 255), 2)
            cv2.imshow(win, param)

    disp = frame.copy()
    cv2.namedWindow(win)
    cv2.setMouseCallback(win, click, disp)

    while len(pts) < 2:
        cv2.imshow(win, disp)
        key = cv2.waitKey(30) & 0xFF
        if key == 27:
            cv2.destroyWindow(win)
            return None

    cv2.destroyWindow(win)
    return pts[0], pts[1]


def point_side(p, line):
    (x1, y1), (x2, y2) = line
    return (p[0] - x1) * (y2 - y1) - (p[1] - y1) * (x2 - x1)


def crossed_line(prev, curr, line):
    return point_side(prev, line) * point_side(curr, line) < 0


def closest_track(centroid, tracks):
    best_id, best_dist = None, MAX_DIST
    for tid, t in tracks.items():
        last = t["centroids"][-1]
        d = np.hypot(centroid[0] - last[0], centroid[1] - last[1])
        if d < best_dist:
            best_dist = d
            best_id = tid
    return best_id


def main():
    if len(sys.argv) < 2:
        print("Usage: python car_counter.py <video>")
        sys.exit(1)

    video_path = sys.argv[1]
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open {video_path}")
        sys.exit(1)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Video: {w}x{h}, {fps:.2f} fps")

    ret, first_frame = cap.read()
    if not ret:
        print("Cannot read first frame")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    line = select_line(first_frame)
    if line is None:
        print("No line selected")
        sys.exit(1)

    pt_a, pt_b = line
    print(f"Line: ({pt_a[0]},{pt_a[1]}) -> ({pt_b[0]},{pt_b[1]})")

    bg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=36, detectShadows=True)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    tracks = {}
    next_id = 0
    count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        fg = bg.apply(frame)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        centroids = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < MIN_AREA:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            cx, cy = x + bw // 2, y + bh // 2
            centroids.append((cx, cy, x, y, bw, bh))

        matched = set()
        for cx, cy, x, y, bw, bh in centroids:
            tid = closest_track((cx, cy), tracks)
            if tid is not None:
                t = tracks[tid]
                t["centroids"].append((cx, cy))
                if len(t["centroids"]) > HIST_LEN:
                    t["centroids"].pop(0)
                if not t["crossed"] and len(t["centroids"]) >= 2:
                    if crossed_line(t["centroids"][-2], t["centroids"][-1], line):
                        t["crossed"] = True
                        count += 1
                        print(f"Car #{count} crossed")
                matched.add(tid)
            else:
                tracks[next_id] = {"centroids": [(cx, cy)], "crossed": False}
                next_id += 1

        # Mark unmatched tracks as stale (optional cleanup)
        stale = [tid for tid in tracks if tid not in matched]
        # Remove stale tracks after some time - keep them briefly
        # We'll just mark by not updating
        for tid in stale:
            t = tracks[tid]
            t["centroids"].append(t["centroids"][-1])  # hold position
            if len(t["centroids"]) > HIST_LEN:
                t["centroids"].pop(0)

        # Draw
        cv2.line(frame, pt_a, pt_b, (0, 255, 255), 2)
        for cx, cy, x, y, bw, bh in centroids:
            cv2.rectangle(frame, (x, y), (x + bw, y + bh), (0, 255, 0), 2)
            cv2.circle(frame, (cx, cy), 3, (0, 0, 255), -1)

        for tid, t in tracks.items():
            if len(t["centroids"]) > 1:
                pts = np.array(t["centroids"], np.int32)
                cv2.polylines(frame, [pts], False, (255, 0, 0), 1)

        cv2.putText(frame, f"Count: {count}", (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 2)

        cv2.imshow("Car Counter - drag line, then press ENTER", frame)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nTotal cars counted: {count}")


if __name__ == "__main__":
    main()
