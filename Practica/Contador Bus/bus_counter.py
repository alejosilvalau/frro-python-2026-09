import cv2
import numpy as np
import sys
from math import atan2, cos, sin, pi
from pathlib import Path


HIST_LEN = 15
HOG_INTERVAL = 5
MOG_WARMUP = 30
MIN_TRACK_FRAMES = 10
SEARCH_RADIUS = 100
MAX_STALE_WITHOUT_HOG = 15


def closest_point_on_segment(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    abx = bx - ax
    aby = by - ay
    t = ((px - ax) * abx + (py - ay) * aby) / (abx * abx + aby * aby + 1e-8)
    t = max(0, min(1, t))
    return (int(ax + t * abx), int(ay + t * aby))


def draw_arrow_from_line(img, click_pt, line_a, line_b, color, label):
    start = closest_point_on_segment(click_pt, line_a, line_b)
    cv2.arrowedLine(img, start, click_pt, color, 3, tipLength=0.25)
    lx = int(start[0] + (click_pt[0] - start[0]) * 0.5) + 5
    ly = int(start[1] + (click_pt[1] - start[1]) * 0.5) - 5
    put_text(img, label, (lx, ly), 0.7, color, 2)


def put_text(img, text, pos, scale, color, thickness=2):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    x, y = pos
    pad = 4
    cv2.rectangle(img, (x - pad, y - th - pad), (x + tw + pad, y + pad), (0, 0, 0), -1)
    cv2.putText(img, text, (x, y), font, scale, color, thickness)


def select_line_and_arrows(frame):
    line_pts = []
    in_pt = None
    out_pt = None
    track_pt = None
    stage = "line"
    win = "Setup"

    def redraw():
        disp = frame.copy()
        if len(line_pts) == 2:
            cv2.line(disp, line_pts[0], line_pts[1], (0, 255, 255), 2)
            if in_pt:
                draw_arrow_from_line(disp, in_pt, line_pts[0], line_pts[1], (0, 255, 0), "IN")
            if out_pt:
                draw_arrow_from_line(disp, out_pt, line_pts[0], line_pts[1], (0, 0, 255), "OUT")
            if track_pt:
                cv2.drawMarker(disp, track_pt, (255, 0, 255), cv2.MARKER_CROSS, 20, 2)
        elif len(line_pts) == 1:
            cv2.circle(disp, line_pts[0], 5, (0, 255, 255), -1)
        if stage == "line":
            put_text(disp, "1. Click 2 pts for line  ENTER=done ESC=reset", (10, 25), 0.5, (255, 255, 255), 2)
        elif stage == "in":
            put_text(disp, "2. Click where IN arrow goes (away from line)", (10, 25), 0.5, (0, 255, 0), 2)
        elif stage == "out":
            put_text(disp, "3. Click where OUT arrow goes (away from line)", (10, 25), 0.5, (0, 0, 255), 2)
        elif stage == "track":
            put_text(disp, "4. Click a point ON THE BUS to track its movement", (10, 25), 0.5, (255, 0, 255), 2)
            put_text(disp, "(choose a distinctive area: logo, window edge, stripe)", (10, 45), 0.4, (200, 200, 200), 1)
        cv2.imshow(win, disp)

    def click(event, x, y, flags, param):
        nonlocal stage, in_pt, out_pt, line_pts, track_pt
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if stage == "line":
            line_pts.append((x, y))
            redraw()
        elif stage == "in":
            in_pt = (x, y)
            stage = "out"
            redraw()
        elif stage == "out":
            out_pt = (x, y)
            stage = "track"
            redraw()
        elif stage == "track":
            track_pt = (x, y)
            stage = "done"
            redraw()

    cv2.namedWindow(win)
    cv2.setMouseCallback(win, click, None)

    while True:
        if stage == "done":
            break
        redraw()
        key = cv2.waitKey(30) & 0xFF
        if stage == "line":
            if key == 27:
                line_pts.clear()
            if key in [13, 32] and len(line_pts) == 2:
                stage = "in"

    cv2.destroyWindow(win)
    return line_pts[0], line_pts[1], in_pt, out_pt, track_pt


def point_side(p, line):
    (x1, y1), (x2, y2) = line
    return float((p[0] - x1) * (y2 - y1) - (p[1] - y1) * (x2 - x1))


def crossed_line(prev, curr, line):
    return point_side(prev, line) * point_side(curr, line) < 0


def person_aspect_ok(bw, bh):
    if bh < bw:
        return False
    aspect = bh / max(bw, 1)
    return 1.5 < aspect < 4.5


def main():
    if len(sys.argv) < 2:
        print("Usage: python bus_counter.py <video>")
        sys.exit(1)

    video_path = sys.argv[1]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Cannot open {video_path}")
        sys.exit(1)

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    scale = (w * h) / (640 * 360)
    print(f"Video: {w}x{h}, {fps:.2f} fps, {total} frames")

    ret, frame = cap.read()
    if not ret:
        print("Cannot read first frame")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    pt_a, pt_b, in_pt, out_pt, track_pt = select_line_and_arrows(frame)
    if None in (pt_a, pt_b, in_pt, out_pt):
        print("Missing line or arrow positions")
        sys.exit(1)

    print(f"Line: ({pt_a[0]},{pt_a[1]}) -> ({pt_b[0]},{pt_b[1]})")
    print(f"Track point: {track_pt}")
    orig_in_side = point_side(in_pt, (pt_a, pt_b))
    print(f"In side: {'positive' if orig_in_side > 0 else 'negative'}")

    TEMPLATE_SIZE = 25
    use_tracking = track_pt is not None
    template_gray = None
    prev_track_center = None
    track_fail_count = 0
    if use_tracking:
        hs = TEMPLATE_SIZE // 2
        x1 = max(0, track_pt[0] - hs)
        y1 = max(0, track_pt[1] - hs)
        x2 = min(w, track_pt[0] + hs)
        y2 = min(h, track_pt[1] + hs)
        templ = frame[y1:y2, x1:x2]
        if templ.size > 0:
            template_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
            prev_track_center = track_pt
            print(f"Template: {templ.shape[1]}x{templ.shape[0]}")
        else:
            use_tracking = False

    orig_line_a, orig_line_b = pt_a, pt_b
    orig_in, orig_out = in_pt, out_pt

    min_area = int(300 * scale)
    max_dist = int(80 * np.sqrt(scale))

    bg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=36, detectShadows=True)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    tracks = {}
    next_id = 0
    count_in = 0
    count_out = 0
    frame_idx = 0

    for _ in range(MOG_WARMUP):
        ret, _ = cap.read()
        if not ret:
            break
        bg.apply(_)
    cap.set(cv2.CAP_PROP_POS_FRAMES, MOG_WARMUP)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1

        # Track bus position
        dx, dy = 0, 0
        if use_tracking and template_gray is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sx1 = max(0, prev_track_center[0] - SEARCH_RADIUS)
            sy1 = max(0, prev_track_center[1] - SEARCH_RADIUS)
            sx2 = min(w, prev_track_center[0] + SEARCH_RADIUS)
            sy2 = min(h, prev_track_center[1] + SEARCH_RADIUS)
            roi = gray[sy1:sy2, sx1:sx2]
            th, tw = template_gray.shape
            if roi.shape[0] > th and roi.shape[1] > tw:
                res = cv2.matchTemplate(roi, template_gray, cv2.TM_CCOEFF_NORMED)
                _, mv, _, ml = cv2.minMaxLoc(res)
                if mv > 0.4:
                    found = (sx1 + ml[0] + tw // 2, sy1 + ml[1] + th // 2)
                    dx = found[0] - prev_track_center[0]
                    dy = found[1] - prev_track_center[1]
                    prev_track_center = found
                    track_fail_count = 0
                else:
                    track_fail_count += 1
                    if track_fail_count > 45:
                        use_tracking = False

        cur_a = (orig_line_a[0] + dx, orig_line_a[1] + dy)
        cur_b = (orig_line_b[0] + dx, orig_line_b[1] + dy)
        cur_in = (orig_in[0] + dx, orig_in[1] + dy)
        cur_out = (orig_out[0] + dx, orig_out[1] + dy)

        # --- Person detection (HOG-primary) ---
        run_hog = (frame_idx % HOG_INTERVAL == 0)
        fg = bg.apply(frame)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        mog_centroids = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            if not person_aspect_ok(bw, bh):
                continue
            cx, cy = x + bw // 2, y + bh // 2
            mog_centroids.append((cx, cy, x, y, bw, bh))

        hog_detections = []
        if run_hog:
            rects, _ = hog.detectMultiScale(frame, winStride=(8, 8),
                                            padding=(8, 8), scale=1.05)
            for hx, hy, hbw, hbh in rects:
                if person_aspect_ok(hbw, hbh):
                    hcx, hcy = hx + hbw // 2, hy + hbh // 2
                    hog_detections.append((hcx, hcy, hx, hy, hbw, hbh))

        matched = set()
        if run_hog:
            used = set()
            for tid in list(tracks.keys()):
                t = tracks[tid]
                last = t["centroids"][-1]
                best_id, best_d = None, max_dist
                for i, (hcx, hcy, _, _, _, _) in enumerate(hog_detections):
                    if i in used:
                        continue
                    d = np.hypot(last[0] - hcx, last[1] - hcy)
                    if d < best_d:
                        best_d = d
                        best_id = i
                if best_id is not None:
                    hcx, hcy, _, _, _, _ = hog_detections[best_id]
                    used.add(best_id)
                    t["centroids"].append((hcx, hcy))
                    if len(t["centroids"]) > HIST_LEN:
                        t["centroids"].pop(0)
                    t["since_hog"] = 0
                    matched.add(tid)

            for i, (hcx, hcy, _, _, _, _) in enumerate(hog_detections):
                if i in used:
                    continue
                tracks[next_id] = {
                    "centroids": [(hcx, hcy)],
                    "crossed": False,
                    "since_hog": 0,
                }
                next_id += 1

            for tid in tracks:
                if tid in matched:
                    continue
                t = tracks[tid]
                last = t["centroids"][-1]
                best_mog, best_d = None, max_dist
                for cx, cy, _, _, _, _ in mog_centroids:
                    d = np.hypot(last[0] - cx, last[1] - cy)
                    if d < best_d:
                        best_d = d
                        best_mog = (cx, cy)
                if best_mog is not None:
                    t["centroids"].append(best_mog)
                    if len(t["centroids"]) > HIST_LEN:
                        t["centroids"].pop(0)
                    matched.add(tid)
        else:
            used = set()
            for tid in list(tracks.keys()):
                t = tracks[tid]
                last = t["centroids"][-1]
                best_id, best_d = None, max_dist
                for i, (cx, cy, _, _, _, _) in enumerate(mog_centroids):
                    if i in used:
                        continue
                    d = np.hypot(last[0] - cx, last[1] - cy)
                    if d < best_d:
                        best_d = d
                        best_id = i
                if best_id is not None:
                    cx, cy, _, _, _, _ = mog_centroids[best_id]
                    used.add(best_id)
                    t["centroids"].append((cx, cy))
                    if len(t["centroids"]) > HIST_LEN:
                        t["centroids"].pop(0)
                    matched.add(tid)

        for tid in list(tracks.keys()):
            if tid in matched:
                continue
            t = tracks[tid]
            t["since_hog"] = t.get("since_hog", 0) + 1
            t["centroids"].append(t["centroids"][-1])
            if len(t["centroids"]) > HIST_LEN:
                t["centroids"].pop(0)
            if t["since_hog"] > MAX_STALE_WITHOUT_HOG:
                del tracks[tid]

        # Crossing detection
        for tid, t in tracks.items():
            if t["crossed"] or len(t["centroids"]) < 2:
                continue
            prev_pos = t["centroids"][-2]
            curr_pos = t["centroids"][-1]
            line_now = (cur_a, cur_b)
            moved = np.hypot(curr_pos[0] - prev_pos[0], curr_pos[1] - prev_pos[1]) > 3

            if crossed_line(prev_pos, curr_pos, line_now) and moved:
                t["crossed"] = True
                side_before = point_side(prev_pos, line_now)
            elif len(t["centroids"]) >= MIN_TRACK_FRAMES:
                half = len(t["centroids"]) // 2
                fh = [point_side(c, line_now) > 0 for c in t["centroids"][:half]]
                sh = [point_side(c, line_now) > 0 for c in t["centroids"][half:]]
                fr = sum(fh) / max(len(fh), 1)
                sr = sum(sh) / max(len(sh), 1)
                if (fr > 0.5) != (sr > 0.5) and max(fr, 1-fr) > 0.6 and max(sr, 1-sr) > 0.6:
                    t["crossed"] = True
                    side_before = 1 if fr > 0.5 else -1

            if t["crossed"]:
                if (side_before > 0) == (orig_in_side > 0):
                    count_out += 1
                    label = "OUT"
                else:
                    count_in += 1
                    label = "IN"
                print(f"Person #{tid} {label} (in={count_in} out={count_out})")

        # --- Draw ---
        cv2.line(frame, cur_a, cur_b, (0, 255, 255), 2)
        draw_arrow_from_line(frame, cur_in, cur_a, cur_b, (0, 255, 0), "IN")
        draw_arrow_from_line(frame, cur_out, cur_a, cur_b, (0, 0, 255), "OUT")

        if use_tracking:
            cv2.drawMarker(frame, prev_track_center, (255, 0, 255), cv2.MARKER_CROSS, 14, 1)

        for tid, t in tracks.items():
            cx, cy = t["centroids"][-1]
            color = (0, 255, 0) if t.get("since_hog", 0) < 5 else (100, 200, 100)
            cv2.circle(frame, (cx, cy), 4, color, -1)
            if len(t["centroids"]) > 1:
                pts = np.array(t["centroids"], np.int32)
                cv2.polylines(frame, [pts], False, color, 2)

        put_text(frame, f"In:  {count_in}", (10, 40), 1.2, (0, 255, 0), 2)
        put_text(frame, f"Out: {count_out}", (10, 80), 1.2, (0, 0, 255), 2)
        put_text(frame, "q to quit", (10, h - 10), 0.5, (200, 200, 200), 1)

        cv2.imshow("Bus Counter (q to quit)", frame)
        if cv2.waitKey(30) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    print(f"\nFinal count - In: {count_in}  Out: {count_out}  Net: {count_in - count_out}")


if __name__ == "__main__":
    main()
