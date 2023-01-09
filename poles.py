import cv2 as cv
import numpy as np
import math
import random
import time

# colors
red = (0,0,255)
green = (0,255,0)
blue = (255,0,0)

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
cv.namedWindow("path", cv.WINDOW_NORMAL)

grid_size = 140
true_pts = np.float32([
             [-1,-2],          [+1,-2],
    [-2,-1], [-1,-1], [ 0,-1], [+1,-1], [+2,-1],
             [-1, 0],          [+1, 0],
    [-2,+1], [-1,+1], [ 0,+1], [+1,+1], [+2,+1],
             [-1,+2],          [+1,+2]
])
start_pos = np.float32([+1,+2])

# _position 
old_pos = start_pos

path_img = np.zeros((1000,1000,3), np.uint8)
def path_pt(pt):
    return np.int16(grid_size*pt + 500)

# Image features
matcher = cv.BFMatcher(cv.NORM_L2, crossCheck=True)

while True:
      
    # Read every frame
    ret, img = vid.read()

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
        #cv.drawContours(img, [hull], -1, blue, 1)

        # Find bounding rotated rectangle
        rect = cv.minAreaRect(hull)
        box = np.int0(cv.boxPoints(rect))
        #cv.drawContours(img, [box], -1, green, 1)

        # Find centroid
        M = cv.moments(contour)
        center = (int(M['m10']/M['m00']), int(M['m01']/M['m00']))

        # Fit line segment and find base of pole
        [[vx], [vy], [x], [y]] = cv.fitLine(hull, cv.DIST_L2, 0, 0.01, 0.01)
        [left, right] = sorted(box, key = lambda x:x[1])[2:]
        base = np.float32(seg_intersect(
            np.array([x,y]), 
            np.array([x+vx,y+vy]),
            np.array(left), 
            np.array(right))
        )

        # Perspective project these features
        [warped_base, warped_left, warped_right, warped_center] = np.float32(
            cv.perspectiveTransform(np.float32([
                [base, left, right, center]
            ]), project_mat)[0]
        )

        rel_pos = warped_base/grid_size
        new_pt = old_pos + np.array([rel_pos[0], -rel_pos[1]])
        new_pts.append(new_pt)

        cv.line(img, np.int16(base), np.int16(center), blue, 1)
        cv.line(warped_img, np.int16(warped_base), np.int16(warped_center), blue, 1)

        cv.line(img, np.int16(left), np.int16(right), blue, 1)
        cv.line(warped_img, np.int16(warped_left), np.int16(warped_right), blue, 1)

    if len(new_pts) > 1:
        # Find similarities 
        matches = matcher.match(true_pts, new_pts)
        matches = sorted(matches, key = lambda x:x.distance)

        matched_true_pts = []
        matched_new_pts = []

        for match in matches:

            true_pt = true_pts[match.queryIdx]
            new_pt = new_pts[match.trainIdx]

            delta = np.subtract(new_pt, true_pt)

            matched_true_pts.append(true_pt)
            matched_new_pts.append(new_pt)

            cv.line(path_img, path_pt(true_pt), path_pt(new_pt), red, 1)

        if len(matched_new_pts) > 1:

            transformation, inliers = cv.estimateAffinePartial2D(
                    np.array([matched_true_pts]),
                    np.array([matched_new_pts])
                )
            new_pos = transformation.dot([old_pos[0], old_pos[1], 1])

            #fade path img
            path_img = (path_img * 0.99).astype("uint8")
            cv.line(path_img, path_pt(old_pos), path_pt(new_pos), rand_color(), 2)
            print(new_pos)
            old_pos = new_pos

    #cv.imshow("img", img)
    cv.rectangle(warped_img, (236, 715), (236+grid_size, 715-grid_size), red)
    cv.imshow("warped", warped_img)
    cv.imshow("path", path_img)


    ##time.sleep(0.5)
      
    # the 'q' button is set as the
    # quitting button you may use any
    # desired button of your choice
    if cv.waitKey(1) & 0xFF == ord('q'):
        break
  
# After the loop release the cap object
vid.release()
# Destroy all the windows
cv.destroyAllWindows()

