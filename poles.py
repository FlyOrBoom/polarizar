import cv2 as cv
import numpy as np
import math
import random
import time

# colors
RED =   (0,0,255)
GREEN = (0,255,0)
YELLOW =    (0,255,255)
BLUE =  (255,0,0)
PINK =  (255,0,255)
CYAN =  (255,255,0)
WHITE = (255,255,255)



def rand_color():
    return (random.randint(0,255),random.randint(0,255),random.randint(0,255))

# line segment a given by endpoint a and slope da
# line segment b given by endpoint b and slope db
# return
def seg_intersect(a1,a2, b1,b2) :
    da = a2-a1
    db = b2-b1
    dp = a1-b1
    dap = [-da[1], da[0]] # perperdicular vector to da
    denom = np.dot( dap, db)
    num = np.dot( dap, dp )
    return (num / denom.astype(float))*db + b1

# Capture the webcam. Change the number if no work
vid = cv.VideoCapture(0)

cv.namedWindow("warped", cv.WINDOW_NORMAL)
#cv.namedWindow("path", cv.WINDOW_NORMAL)

GRID_SIZE = 140
TRUE_PTS = np.float32([
             [-1,-2],          [+1,-2],
    [-2,-1], [-1,-1], [ 0,-1], [+1,-1], [+2,-1],
             [-1, 0],          [+1, 0],
    [-2,+1], [-1,+1], [ 0,+1], [+1,+1], [+2,+1],
             [-1,+2],          [+1,+2]
])
START_POS = np.float32([+1.5,+3])
PATH_SIZE = 700

# _position 
old_pos = START_POS

path_img = np.zeros((PATH_SIZE,PATH_SIZE,3), np.uint8)
def path_pt(pt):
    return np.int16(PATH_SIZE/8*pt + PATH_SIZE/2)

# Image features
matcher = cv.BFMatcher(cv.NORM_L2, crossCheck=True)

while True:

    # Read every frame
    ret, img = vid.read()

    #old_pos = START_POS

    # Mask by hue-saturation-value
    hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    lower = np.array([10,120,50])
    upper = np.array([25,255,255])
    mask = cv.inRange(hsv, lower, upper)

    # Perspective project to top-down view
    (Y, X) = img.shape[0:2]
    w = 1800
    Yf = int(Y*1.78)
    src_plane = np.float32([[0, 0], [X, 0], [X+w, Y], [-w, Y]])
    project_plane = np.float32([[0, 0], [X, 0], [X, Yf], [0, Yf]])
    project_mat = cv.getPerspectiveTransform(src_plane, project_plane)
    warped_img = cv.warpPerspective(img, project_mat, (X, Yf))

    # Find contours in mask
    new_pts = []
    contours, hierarchy = cv.findContours(mask, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
    for contour in contours:

        # Filter out small contours (likely noise)
        area = cv.contourArea(contour)
        if area < 100: continue

        # Find bounding convex hull
        hull = cv.convexHull(contour)
        #cv.drawContours(img, [hull], -1, BLUE, 1)

        # Find bounding rotated rectangle
        rect = cv.minAreaRect(hull)
        box = np.int0(cv.boxPoints(rect))
        #cv.drawContours(img, [box], -1, GREEN, 1)

        # Find centroid
        moments = cv.moments(contour)
        center = np.float32([
            moments['m10']/moments['m00'], 
            moments['m01']/moments['m00']
        ])

        # Fit line segment and find base of pole
        [[vx], [vy], [x], [y]] = cv.fitLine(hull, cv.DIST_L2, 0, 0.01, 0.01)
        [left, right] = sorted(box, key = lambda x:x[1])[2:]
        base = np.float32(seg_intersect(
            np.float32([x,y]), 
            np.float32([x+vx,y+vy]),
            np.float32(left), 
            np.float32(right))
        )

        # Perspective project these features
        [warped_base, warped_left, warped_right, warped_center] = np.float32(
            cv.perspectiveTransform(np.float32([
                [base, left, right, center]
            ]), project_mat)[0]
        )

        rel_pos = np.float32([X/2-warped_base[0], Yf-warped_base[1]])/GRID_SIZE
        new_pt = old_pos - rel_pos
        new_pts.append(new_pt)

        cv.line(img, np.int16(base), np.int16(center), BLUE, 1)
        cv.line(warped_img, np.int16(warped_base), np.int16(warped_center), BLUE, 1)

        cv.line(img, np.int16(left), np.int16(right), BLUE, 1)
        cv.line(warped_img, np.int16(warped_left), np.int16(warped_right), BLUE, 1)

    new_pts = np.float32(new_pts)

    if len(new_pts) > 1:
        # Find similarities 
        matches = matcher.match(TRUE_PTS, new_pts)
        matches = sorted(matches, key = lambda x:x.distance)
        matches = [ x for x in matches if x.distance < 0.5 ]

        matched_true_pts = np.float32([TRUE_PTS[match.queryIdx] for match in matches])
        matched_new_pts = np.float32([new_pts[match.trainIdx] for match in matches])

        print(len(matched_true_pts))

        if len(matched_new_pts) > 1:

            transformation, inliers = cv.estimateAffinePartial2D(
                    np.array([matched_new_pts]),
                    np.array([matched_true_pts])
                )
            transformation[1][0] = 0
            transformation[0][1] = 0
            new_pos = transformation.dot([old_pos[0], old_pos[1], 1])
            print(new_pos)

            #fade path img
            cv.line(path_img, path_pt(old_pos), path_pt(new_pos), rand_color(), 2)
            old_pos = new_pos

    #cv.imshow("img", img)

    path_img = (path_img * 0.8).astype("uint8")
    cv.drawMarker(path_img, path_pt(START_POS), GREEN, cv.MARKER_DIAMOND, 25, 2)
    cv.drawMarker(path_img, path_pt(old_pos), WHITE, cv.MARKER_CROSS, 20, 2)
    for pt in new_pts:
        cv.circle(path_img, path_pt(pt), 10, RED, 1)
    for pt in matched_new_pts:
        cv.circle(path_img, path_pt(pt), 10, PINK, 3)
    for pt in TRUE_PTS:
        cv.circle(path_img, path_pt(pt), 5, BLUE, 1)
    for pt in matched_true_pts:
        cv.circle(path_img, path_pt(pt), 5, BLUE, cv.FILLED)
      
    cv.rectangle(warped_img, (236, 715), (236+GRID_SIZE, 715-GRID_SIZE), RED)
    cv.imshow("warped", warped_img)
    cv.imshow("path", path_img)

    # the 'q' button is set as the
    # quitting button you may use any
    # desiRED button of your choice
    if cv.waitKey(1) & 0xFF == ord('q'):
        break
  
# After the loop release the cap object
vid.release()
# Destroy all the windows
cv.destroyAllWindows()

