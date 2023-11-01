import numpy as np
import cv2 as cv
from cv2.typing import MatLike
import math
from pathlib import Path
import os
import time

# map from gimp to opencv
def hsv_map(hsv: list[int]) -> np.ndarray:
    return np.array([hsv[0] * 180/256, hsv[1] * 256/256, hsv[2] * 256/256])

# HSV range of white paint
WHITE_LOW = hsv_map([0, 0, 200])
WHITE_HIGH = hsv_map([255, 30, 255])

WHITE_BUTTON_LOW = hsv_map([10, 20, 130])
WHITE_BUTTON_HIGH = hsv_map([50, 130, 255])
GREEN_BUTTON_LOW = hsv_map([70,25,60])
GREEN_BUTTON_HIGH = hsv_map([120,210,255])

# Number of paint lines
NUMBER_WHITE_LINES =        24

# GB_KERNEL = (7,7)
# CANNY_LOW = 50
# CANNY_HIGH = 150
DIL_KERNEL_MULT =           1/300
ERO_KERNEL_MULT =           1/400
HL_RHO =                    1               # Distance resolution of the accumulator in pixels.
HL_THETA =                  np.pi / 180     # Angle resolution of the accumulator in radians. 
HL_THRESHOLD =              50              # Accumulator threshold parameter. Only those lines are returned that get enough votes
HL_MIN_LINE_LENGTH_MULT =   1/8             # Minimum line length. Line segments shorter than that are rejected. 
HL_MAX_LINE_GAP_MULT =      1/1000          # Maximum allowed gap between points on the same line to link them.

MAX_SLOPE =                 1/3             # maximum slope for lines
MAX_SLOPE_DIF =             1/10            # maximum slope to approx distance between
MAX_LINE_DIST_MULT =        1/100           # lines within this distance are grouped

SCALE_WIDTH =               1000
SCALE_HEIGHT =              1500

NUMBER_BUTTONS =            NUMBER_WHITE_LINES-1
ROW_HEIGHT =                SCALE_HEIGHT/NUMBER_BUTTONS
BUTTON_RECT_HEIGHT =        2/3 * ROW_HEIGHT
BUTTON_RECT_WIDTH_LEFT =    1/20 * SCALE_WIDTH
BUTTON_RECT_WIDTH_RIGHT =   1/10 * SCALE_WIDTH
BUTTON_RECT_OFFSET_Y =      1/6 * ROW_HEIGHT
LEFT_COLOR_CUTOFF =         1/5 * BUTTON_RECT_HEIGHT * BUTTON_RECT_WIDTH_LEFT
RIGHT_COLOR_CUTOFF =        1/10 * BUTTON_RECT_HEIGHT * BUTTON_RECT_WIDTH_RIGHT

PHOTO_LOG_DIR = str((Path(__file__).parent / "../data/pics").resolve())

class ChoreBoardNotFound(Exception):
    pass

def slope(line: MatLike) -> float:
    x1: int = line[0]
    y1: int = line[1]
    x2: int = line[2]
    y2: int = line[3]
    return (y2-y1) / (x2-x1)

def approx_distance(l1: MatLike, l2: MatLike) -> float:
    # Compute approximate perpindicular distance between two lines with similar slopes
    # Average slope is probably good enough but might be more accurate near x=0?
    m1 = slope(l1)
    m2 = slope(l2)
    m: float = (m1+m2)/2
    # offset x by avg so around x=0
    x1,y1 = l1[:2]
    x2,y2 = l2[:2]
    avgx = (x1+x2)/2
    x1 -= avgx
    x2 -= avgx
    b1: float = y1 - m1*x1
    b2: float = y2 - m2*x2
    return abs(b2 - b1) / math.sqrt(m**2 + 1)

# def max_dist(l1,l2):
#     return max(abs(lx1-lx2) for lx1,lx2 in zip(l1,l2))

class PhotoProcessor():

    def __init__(self, image: bytes, log_photos: bool = True):

        npimg = np.frombuffer(image, dtype=np.uint8)
        self.image: MatLike = cv.imdecode(npimg, cv.IMREAD_COLOR)
        self.image_processed: MatLike

        self.left_buttons_idx: list[int]
        self.right_buttons_idx: list[int]

        self.log_photos = log_photos

        self._extract_features()

    def show(self) -> None:
               
        cv.imshow("test", self.image)
        cv.waitKey(0)

    def show_processed(self) -> None:
        cv.imshow("Result", self.image_processed)
        cv.waitKey(0)

    def get_left_buttons(self) -> list[int]:
        return self.left_buttons_idx

    def get_right_buttons(self) -> list[int]:
        return self.right_buttons_idx

    def _extract_features(self) -> None:

        img = self.image
        img_width,img_height = img.shape[:2]

        # Find lines between rows
        # Mask the line color
        line_mask = cv.inRange(cv.cvtColor(img, cv.COLOR_BGR2HSV), WHITE_LOW, WHITE_HIGH)
        # cv.imshow("line_mask",line_mask)
        # cv.waitKey()
        if self.log_photos:
            photo_name_prefix = PHOTO_LOG_DIR + "/" + time.strftime("%Y%m%d_%H%M%S/")
            os.makedirs(photo_name_prefix, exist_ok=True)
            cv.imwrite(photo_name_prefix + "1_linemask.jpg", line_mask)

        # Use erosion to thin noise and dilation to make thick what's left
        ero_kern_size = int(img_width * ERO_KERNEL_MULT // 2 * 2 + 1) # make odd
        ero_kern = np.ones((1,ero_kern_size), np.uint8)
        ero = cv.erode(line_mask, ero_kern, iterations=3)
        if self.log_photos:
            cv.imwrite(photo_name_prefix + "2_erode.jpg", ero)

        dil_kern_size = int(img_width * DIL_KERNEL_MULT // 2 * 2 + 1) # make odd
        dil_kern = np.ones((dil_kern_size,)*2, np.uint8)
        dil = cv.dilate(ero, dil_kern, iterations=1)
        if self.log_photos:
            cv.imwrite(photo_name_prefix + "3_dilate.jpg", dil)

        #TODO: Could do edge detection here to decrease lines and allow for pictures from further 
        # away without walls etc?

        line_image = np.copy(img)  # creating a blank to draw lines on

        # Run HoughLines to get white row lines
        # Output "lines" is an array containing endpoints of detected line segments
        print(img_width)
        min_length = img_width * HL_MIN_LINE_LENGTH_MULT
        max_gap = img_width * HL_MAX_LINE_GAP_MULT
        lines: MatLike = cv.HoughLinesP(dil, HL_RHO, HL_THETA, HL_THRESHOLD, 
                                        np.array([]), min_length, max_gap)

        if lines is None:
            raise ChoreBoardNotFound("The chore board was not found in the picture! "
                    "Make sure the chore board is in frame and the lighting is adaquate.")

        print("number of lines pre-grouping:",len(lines))

        # We have multiple lines per line. Group so they can be counted.
        group_lines: list[MatLike] = []
        group_line_num: list[int] = []
        for li in lines:
            li = li[0]    # line is one more deep

            if abs(slope(li)) > MAX_SLOPE:
                continue

            # Check grouped lines for this line
            found = False
            for i,gl in enumerate(group_lines):
                if (abs(slope(li) - slope(gl)) < MAX_SLOPE_DIF 
                        and approx_distance(li,gl) < img_height * MAX_LINE_DIST_MULT):
                    # Group this line. Use points with min/max x
                    p = [li[:2], li[2:], gl[:2], gl[2:]]
                    minp = p[0]
                    maxp = p[0]
                    for pi in p[1:]:
                        minp = min(minp, pi, key=lambda x: x[0])
                        maxp = max(maxp, pi, key=lambda x: x[0])
                    # This also ensures that the x1,y1 are on the "left" (small x)
                    gl[:2] = minp
                    gl[2:] = maxp
                    found = True
                    break
            if found:
                continue
            else:
                group_lines.append(li)
                group_line_num.append(1)

        for line in group_lines:
            x1,y1,x2,y2 = line
            cv.line(line_image,(x1,y1),(x2,y2),(255,0,0),5)

        if self.log_photos:
            cv.imwrite(photo_name_prefix + "4_lines.jpg", line_image)

        if len(group_lines) != NUMBER_WHITE_LINES:
            raise ChoreBoardNotFound("The chore board was not identified. When looking for the "
                    f"horizontal white lines, {len(group_lines)} were found. There should be "
                    f"{NUMBER_WHITE_LINES} Make sure the chore board is in frame and the lighting "
                    "is adaquate.")


        # Get corners so we can do a perspective transform
        # first point is always smaller x due to above
        c1 = max(group_lines, key=lambda x: x[1])[:2]
        c2 = min(group_lines, key=lambda x: x[1])[:2]
        c3 = max(group_lines, key=lambda x: x[3])[2:]
        c4 = min(group_lines, key=lambda x: x[3])[2:]

        src = np.array([c1,c2,c3,c4], dtype=np.float32)
        dst = np.array(
            [[0,            SCALE_HEIGHT],
            [0,             0],
            [SCALE_WIDTH,   SCALE_HEIGHT],
            [SCALE_WIDTH,   0]], dtype=np.float32
        )
        print(src, src.shape)
        print(dst, dst.shape)
        M = cv.getPerspectiveTransform(src, dst)
        img_scale = cv.warpPerspective(img, M, dsize=(SCALE_WIDTH, SCALE_HEIGHT))

        #TODO: save images in process or on failure

        # Detect button orientation by looking in a specific rectangle and checking color
        left_buttons = np.zeros(NUMBER_BUTTONS)
        right_buttons = np.zeros(NUMBER_BUTTONS)
        for i in range(NUMBER_BUTTONS):
            # Left buttons
            button_rect_left = np.array([BUTTON_RECT_WIDTH_LEFT, BUTTON_RECT_HEIGHT], 
                                        dtype=np.int32)
            lp1 = np.array([0, ROW_HEIGHT * i + BUTTON_RECT_OFFSET_Y], dtype=np.int32)
            lp2 = lp1 + button_rect_left
            img_left = img_scale[lp1[1]:lp2[1], lp1[0]:lp2[0]]
            hsv_left = cv.cvtColor(img_left, cv.COLOR_BGR2HSV)
            mask_left = cv.inRange(hsv_left, WHITE_BUTTON_LOW, WHITE_BUTTON_HIGH)
            left_buttons[i] = np.count_nonzero(mask_left) > LEFT_COLOR_CUTOFF
            # cv.imshow('left img', mask_left)
            # print(np.count_nonzero(mask_left), LEFT_COLOR_CUTOFF)
            # cv.waitKey()
            c = (0,255,0) if left_buttons[i] else (0,0,255) 
            cv.rectangle(img_scale, lp1, lp2, c,1)


            # Right buttons
            rect_right = np.array([BUTTON_RECT_WIDTH_RIGHT, BUTTON_RECT_HEIGHT], dtype=np.int32)
            rp1 = np.array(
                [SCALE_WIDTH - BUTTON_RECT_WIDTH_RIGHT, ROW_HEIGHT * i + BUTTON_RECT_OFFSET_Y], 
                dtype=np.int32)
            rp2 = rp1 + rect_right
            img_right = img_scale[rp1[1]:rp2[1], rp1[0]:rp2[0]]
            hsv_right = cv.cvtColor(img_right, cv.COLOR_BGR2HSV)
            mask_right = cv.inRange(hsv_right, GREEN_BUTTON_LOW, GREEN_BUTTON_HIGH)
            right_buttons[i] = np.count_nonzero(mask_right) > RIGHT_COLOR_CUTOFF
            # cv.imshow('right img', mask_right)
            # cv.waitKey()
            c = (0,255,0) if right_buttons[i] else (0,0,255) 
            cv.rectangle(img_scale, rp1,rp2, c, 1)

        if self.log_photos:
            cv.imwrite(photo_name_prefix + "5_markers.jpg", img_scale)
        self.image_processed = img_scale

        self.left_buttons_idx = np.nonzero(left_buttons)[0].tolist()
        self.right_buttons_idx = np.nonzero(right_buttons)[0].tolist()


def test() -> None:
    for i in range(1,5):
        with open((Path(__file__).parent / f"../test_pictures/test{i}.jpg").resolve(), 'rb') as f:
            pp = PhotoProcessor(f.read())
            print(f'\nTest #{i}')
            print(f'left buttons: {pp.get_left_buttons()}')
            print(f'right buttons: {pp.get_right_buttons()}')
            pp.show_processed()


if __name__ == "__main__":
    test()

