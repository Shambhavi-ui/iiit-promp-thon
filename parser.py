import cv2
import numpy as np
import math


def crop_to_paper(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    coords = np.column_stack(np.where(gray > 200))
    if coords.size == 0:
        return img, gray, 0, 0

    x, y, w, h = cv2.boundingRect(coords)
    pad = 10
    x = max(0, x - pad)
    y = max(0, y - pad)
    w = min(img.shape[1] - x, w + pad * 2)
    h = min(img.shape[0] - y, h + pad * 2)
    cropped = img[y:y+h, x:x+w]
    return cropped, gray[y:y+h, x:x+w], x, y


def make_edge_mask(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)
    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    edges = cv2.morphologyEx(edges, cv2.MORPH_OPEN, kernel)
    return edges


def normalize_line(x1, y1, x2, y2, x_off, y_off):
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 12:
        x2 = x1
    if abs(dy) < 12:
        y2 = y1

    x1 += x_off
    y1 += y_off
    x2 += x_off
    y2 += y_off

    if (x1, y1) > (x2, y2):
        x1, y1, x2, y2 = x2, y2, x1, y1
    return int(x1), int(y1), int(x2), int(y2)


def merge_intervals(intervals, tolerance=8):
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= merged[-1][1] + tolerance:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def merge_collinear_lines(lines, tolerance=8):
    vertical = {}
    horizontal = {}

    def find_group(key, groups):
        for existing in groups:
            if abs(existing - key) <= tolerance:
                return existing
        return key

    for x1, y1, x2, y2 in lines:
        if abs(x1 - x2) < tolerance:
            x = int(round((x1 + x2) / 2))
            group = find_group(x, vertical)
            start, end = sorted([y1, y2])
            vertical.setdefault(group, []).append((start, end))
        elif abs(y1 - y2) < tolerance:
            y = int(round((y1 + y2) / 2))
            group = find_group(y, horizontal)
            start, end = sorted([x1, x2])
            horizontal.setdefault(group, []).append((start, end))
        else:
            # Keep any non-axis-aligned line as-is.
            pass

    merged = []
    for x, intervals in vertical.items():
        for start, end in merge_intervals(intervals, tolerance):
            merged.append((x, start, x, end))
    for y, intervals in horizontal.items():
        for start, end in merge_intervals(intervals, tolerance):
            merged.append((start, y, end, y))
    return merged


def snap_wall_endpoints_to_grid(wall_lines, tolerance=12):
    if not wall_lines:
        return wall_lines

    def cluster_positions(values):
        sorted_values = sorted(values)
        clusters = []
        for value in sorted_values:
            placed = False
            for cluster in clusters:
                if abs(cluster[0] - value) <= tolerance:
                    cluster.append(value)
                    placed = True
                    break
            if not placed:
                clusters.append([value])
        return [int(round(sum(cluster) / len(cluster))) for cluster in clusters]

    vertical_x = cluster_positions({x for x1, y1, x2, y2 in wall_lines if abs(x1 - x2) < tolerance for x in (x1, x2)})
    horizontal_y = cluster_positions({y for x1, y1, x2, y2 in wall_lines if abs(y1 - y2) < tolerance for y in (y1, y2)})

    def snap_value(value, candidates):
        if not candidates:
            return value
        best = min(candidates, key=lambda c: abs(c - value))
        return best if abs(best - value) <= tolerance else value

    snapped = set()
    for x1, y1, x2, y2 in wall_lines:
        if abs(y1 - y2) < tolerance:
            x1 = snap_value(x1, vertical_x)
            x2 = snap_value(x2, vertical_x)
            y1 = snap_value(y1, horizontal_y)
            y2 = y1
        elif abs(x1 - x2) < tolerance:
            y1 = snap_value(y1, horizontal_y)
            y2 = snap_value(y2, horizontal_y)
            x1 = snap_value(x1, vertical_x)
            x2 = x1
        else:
            x1 = snap_value(x1, vertical_x)
            x2 = snap_value(x2, vertical_x)
            y1 = snap_value(y1, horizontal_y)
            y2 = snap_value(y2, horizontal_y)

        if (x1, y1) > (x2, y2):
            x1, y1, x2, y2 = x2, y2, x1, y1
        snapped.add((x1, y1, x2, y2))

    return snapped


def split_axis_aligned_intersections(wall_lines, tolerance=12):
    vertical = []
    horizontal = []
    others = []

    for x1, y1, x2, y2 in wall_lines:
        if abs(x1 - x2) < tolerance:
            y_start, y_end = sorted([y1, y2])
            vertical.append((x1, y_start, x2, y_end))
        elif abs(y1 - y2) < tolerance:
            x_start, x_end = sorted([x1, x2])
            horizontal.append((x_start, y1, x_end, y2))
        else:
            others.append((x1, y1, x2, y2))

    normalized = []
    for x, y1, x2, y2 in vertical:
        ys = {y1, y2}
        for hx1, hy, hx2, _ in horizontal:
            if hx1 - tolerance <= x <= hx2 + tolerance and y1 - tolerance <= hy <= y2 + tolerance:
                ys.add(hy)
        ys = sorted(ys)
        for a, b in zip(ys, ys[1:]):
            if b - a >= 4:
                normalized.append((x, a, x, b))

    for x1, y, x2, y2 in horizontal:
        xs = {x1, x2}
        for vx, vy1, vx2, vy2 in vertical:
            if vy1 - tolerance <= y <= vy2 + tolerance and x1 - tolerance <= vx <= x2 + tolerance:
                xs.add(vx)
        xs = sorted(xs)
        for a, b in zip(xs, xs[1:]):
            if b - a >= 4:
                normalized.append((a, y, b, y))

    return normalized + others


def normalize_wall_lines(wall_lines, tolerance=12):
    if not wall_lines:
        return wall_lines
    wall_lines = set(merge_collinear_lines(wall_lines, tolerance=tolerance))
    wall_lines = snap_wall_endpoints_to_grid(wall_lines, tolerance=tolerance)
    wall_lines = set(split_axis_aligned_intersections(wall_lines, tolerance=tolerance))
    wall_lines = set(merge_collinear_lines(wall_lines, tolerance=tolerance))
    return wall_lines


def remove_border_contours(mask, padding=4):
    # Remove unwanted contours that touch the image border,
    # such as false bottom strips or paper edges.
    h, w = mask.shape
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cleaned = mask.copy()
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if x <= padding or y <= padding or x + cw >= w - padding or y + ch >= h - padding:
            cv2.drawContours(cleaned, [cnt], -1, 0, thickness=cv2.FILLED)
    return cleaned


def clean_edges(edges, min_area=100):
    # Filter out very small noisy contours after morphological cleanup.
    cleaned = np.zeros_like(edges)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        if cv2.contourArea(cnt) >= min_area:
            cv2.drawContours(cleaned, [cnt], -1, 255)
    return cleaned


def preprocess_floor_plan(image_path):
    # Read the floor plan, crop the page region, and build a cleaned edge mask.
    img = cv2.imread(image_path)
    if img is None:
        return None, None, 0, 0

    cropped, _, x_off, y_off = crop_to_paper(img)
    edges = make_edge_mask(cropped)
    edges = remove_border_contours(edges)
    edges = clean_edges(edges)
    return cropped, edges, x_off, y_off


def parse_floor_plan(image_path):
    cropped, edges, x_off, y_off = preprocess_floor_plan(image_path)
    if edges is None:
        return []

    wall_lines = set()
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80, minLineLength=60, maxLineGap=20)
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            length = math.hypot(x2 - x1, y2 - y1)
            if length < 60:
                continue
            x1, y1, x2, y2 = normalize_line(x1, y1, x2, y2, x_off, y_off)
            bw = abs(x2 - x1) + 1
            bh = abs(y2 - y1) + 1
            if bw <= 40 and bh <= 40:
                continue
            wall_lines.add((x1, y1, x2, y2))

    if wall_lines:
        wall_lines = normalize_wall_lines(set(wall_lines), tolerance=10)

    if not wall_lines:
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 200:
                continue

            x, y, w, h = cv2.boundingRect(cnt)
            if w <= 40 and h <= 40:
                continue

            epsilon = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            for i in range(len(approx)):
                x1, y1 = approx[i][0]
                x2, y2 = approx[(i + 1) % len(approx)][0]
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                length = math.hypot(dx, dy)
                if length < 60:
                    continue
                if not (dx < 12 or dy < 12):
                    continue
                x1, y1, x2, y2 = normalize_line(x1, y1, x2, y2, x_off, y_off)
                bw = abs(x2 - x1) + 1
                bh = abs(y2 - y1) + 1
                if bw <= 40 and bh <= 40:
                    continue
                wall_lines.add((x1, y1, x2, y2))

    if wall_lines:
        wall_lines = normalize_wall_lines(set(wall_lines), tolerance=10)

    walls = [[[x1, y1], [x2, y2]] for x1, y1, x2, y2 in sorted(wall_lines)]
    return walls


def get_edge_preview(image_path):
    cropped, edges, _, _ = preprocess_floor_plan(image_path)
    if edges is None:
        return None
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)


def find_doors(image_path):
    # Detect door footprints as moderate-size horizontal edge blobs.
    cropped, edges, x_off, y_off = preprocess_floor_plan(image_path)
    if edges is None:
        return []

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    doors = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 120 or area > 4000:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if (30 < w < 120 and 10 < h < 40) or (10 < w < 40 and 30 < h < 120):
            doors.append([int(x + x_off), int(y + y_off), int(w), int(h)])
    return doors


def rects_overlap(rect1, rect2):
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2
    return not (x1 + w1 <= x2 or x2 + w2 <= x1 or y1 + h1 <= y2 or y2 + h2 <= y1)


def find_windows(image_path):
    # Detect window candidates from small edge contours.
    cropped, edges, x_off, y_off = preprocess_floor_plan(image_path)
    if edges is None:
        return []

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_windows = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 60 or area > 2000:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if 25 < w < 120 and 5 < h < 35:
            raw_windows.append([int(x + x_off), int(y + y_off), int(w), int(h)])

    # Exclude any candidate that overlaps a detected door.
    doors = find_doors(image_path)
    windows = []
    for win in raw_windows:
        if any(rects_overlap(win, door) for door in doors):
            continue
        windows.append(win)

    return windows


def classify_room_area(area):
    if area > 140000:
        return 'Living Room'
    if area > 90000:
        return 'Master Bedroom'
    if area > 55000:
        return 'Bedroom'
    if area > 30000:
        return 'Kitchen'
    if area > 18000:
        return 'Dining Room'
    if area > 10000:
        return 'Bathroom'
    return 'Storage'


def find_rooms(image_path):
    # Estimate room regions by inverting the wall edge mask and
    # finding large interior contours that are not border regions.
    cropped, edges, x_off, y_off = preprocess_floor_plan(image_path)
    if edges is None:
        return []

    inverted = cv2.bitwise_not(edges)
    flood = inverted.copy()
    h, w = flood.shape
    mask = np.zeros((h + 2, w + 2), np.uint8)
    cv2.floodFill(flood, mask, (0, 0), 0)
    room_mask = cv2.bitwise_and(inverted, cv2.bitwise_not(flood))

    kernel = np.ones((5, 5), np.uint8)
    room_mask = cv2.morphologyEx(room_mask, cv2.MORPH_OPEN, kernel)
    room_mask = cv2.morphologyEx(room_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(room_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rooms = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 5000:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        if x <= 5 or y <= 5 or x + w >= cropped.shape[1] - 5 or y + h >= cropped.shape[0] - 5:
            continue

        rooms.append({
            'bounds': [
                [int(x + x_off), int(y + y_off)],
                [int(x + w + x_off), int(y + h + y_off)]
            ],
            'label': classify_room_area(area),
            'area': int(area)
        })

    rooms.sort(key=lambda r: r['area'], reverse=True)
    return rooms