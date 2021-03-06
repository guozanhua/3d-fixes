#!/usr/bin/env python3

import numpy as np
from math import *

def translate(x, y, z):
    return np.matrix([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [x, y, z, 1],
    ])

def scale(x, y, z):
    return np.matrix([
        [x, 0, 0, 0],
        [0, y, 0, 0],
        [0, 0, z, 0],
        [0, 0, 0, 1],
    ])

def rotate_x(angle):
    a = radians(angle)
    return np.matrix([
        [1,       0,      0, 0],
        [0,  cos(a), sin(a), 0],
        [0, -sin(a), cos(a), 0],
        [0,       0,      0, 1],
    ])

def rotate_y(angle):
    a = radians(angle)
    return np.matrix([
        [cos(a), 0, -sin(a), 0],
        [     0, 1,       0, 0],
        [sin(a), 0,  cos(a), 0],
        [     0, 0,       0, 1],
    ])

def rotate_z(angle):
    a = radians(angle)
    return np.matrix([
        [ cos(a), sin(a), 0, 0],
        [-sin(a), cos(a), 0, 0],
        [      0,      0, 1, 0],
        [      0,      0, 0, 1],
    ])

def projection(near, far, fov_horiz, fov_vert):
    w = 1 / tan(radians(fov_horiz) / 2)
    h = 1 / tan(radians(fov_vert)  / 2)
    q = far / (far - near)

    return np.matrix([
        [w, 0,       0, 0],
        [0, h,       0, 0],
        [0, 0,       q, 1],
        [0, 0, -q*near, 0]
    ])

def projection_nv_equiv(near, far, fov_horiz, fov_vert, separation, convergence):
    '''
    Returns two projection matrices that have an equivelent adjustment to the
    nvidia formula built in, allowing the familiar convergence and separation
    settings to work the same.
    '''
    w = 1 / tan(radians(fov_horiz) / 2)
    h = 1 / tan(radians(fov_vert)  / 2)
    q = far / (far - near)

    left = np.matrix([
        [                      w, 0,       0, 0],
        [                      0, h,       0, 0],
        [            -separation, 0,       q, 1],
        [ separation*convergence, 0, -q*near, 0]
    ])

    right = np.matrix([
        [                      w, 0,       0, 0],
        [                      0, h,       0, 0],
        [             separation, 0,       q, 1],
        [-separation*convergence, 0, -q*near, 0]
    ])

    return (left, right)

def fov_w(matrix):
    return degrees(2 * atan(1/matrix[0, 0]))

def fov_h(matrix):
    return degrees(2 * atan(1/matrix[1, 1]))

def adjustment(w, separation, convergence):
    return separation * (w - convergence)

def correct(coord, separation, convergence):
    if isinstance(coord, np.matrix):
        x,y,z,w = coord.tolist()[0]
    else:
        x,y,z,w = coord
    a = adjustment(w, separation, convergence)
    return ([x-a, y, z, w], [x+a, y, z, w])

def multiply(m1, m2):
	'''
	Does a matrix multiplication in a manner than is closer to how it would
	be done in shader assembly.
	'''
	assert(m1.shape == (4,4))
	assert(m2.shape == (4,4))
	t = m2.T
	r = np.matrix([[0.0]*4]*4)
	for y in range(4):
		for x in range(4):
			# r_y = dp4 m1_y t_x
			r[y,x] = np.dot(m1[y].A1, t[x].A1)
	return r

def to_regs(m, start=210):
    for i in range(4):
        print('def c%i, %g, %g, %g, %g' % (start+i, m[i, 0], m[i, 1], m[i, 2], m[i, 3]))

def determinant(m):
    # See also: numpy.linalg.det()
    # http://www.euclideanspace.com/maths/algebra/matrix/functions/inverse/fourD/index.htm
    return \
    m[0,3]*m[1,2]*m[2,1]*m[3,0] - m[0,2]*m[1,3]*m[2,1]*m[3,0] - m[0,3]*m[1,1]*m[2,2]*m[3,0] + m[0,1]*m[1,3]*m[2,2]*m[3,0] + \
    m[0,2]*m[1,1]*m[2,3]*m[3,0] - m[0,1]*m[1,2]*m[2,3]*m[3,0] - m[0,3]*m[1,2]*m[2,0]*m[3,1] + m[0,2]*m[1,3]*m[2,0]*m[3,1] + \
    m[0,3]*m[1,0]*m[2,2]*m[3,1] - m[0,0]*m[1,3]*m[2,2]*m[3,1] - m[0,2]*m[1,0]*m[2,3]*m[3,1] + m[0,0]*m[1,2]*m[2,3]*m[3,1] + \
    m[0,3]*m[1,1]*m[2,0]*m[3,2] - m[0,1]*m[1,3]*m[2,0]*m[3,2] - m[0,3]*m[1,0]*m[2,1]*m[3,2] + m[0,0]*m[1,3]*m[2,1]*m[3,2] + \
    m[0,1]*m[1,0]*m[2,3]*m[3,2] - m[0,0]*m[1,1]*m[2,3]*m[3,2] - m[0,2]*m[1,1]*m[2,0]*m[3,3] + m[0,1]*m[1,2]*m[2,0]*m[3,3] + \
    m[0,2]*m[1,0]*m[2,1]*m[3,3] - m[0,0]*m[1,2]*m[2,1]*m[3,3] - m[0,1]*m[1,0]*m[2,2]*m[3,3] + m[0,0]*m[1,1]*m[2,2]*m[3,3];

def determinant_euclidean(m):
    # Simple case assuming m[0,3] = 0, m[1,3] = 0, m[2,3] = 0, m[3,3] = 1
    # This would be suitable to calculate the inverse of a model-view matrix,
    # for instance
    return 0 \
            + (m[0,0]*m[1,1]*m[2,2]) \
            - (m[0,0]*m[1,2]*m[2,1]) \
            + (m[0,1]*m[1,2]*m[2,0]) \
            - (m[0,1]*m[1,0]*m[2,2]) \
            + (m[0,2]*m[1,0]*m[2,1]) \
            - (m[0,2]*m[1,1]*m[2,0])

def inverse_matrix_euclidean_m0(m, d):
    # Return the 1st row of an inverted matrix, simplifying on the assumption
    # that the 4th column is 0,0,0,1
    m00 = m[1,1]*m[2,2] - m[1,2]*m[2,1]
    m01 = m[0,2]*m[2,1] - m[0,1]*m[2,2]
    m02 = m[0,1]*m[1,2] - m[0,2]*m[1,1]
    return (m00 / d, m01 / d, m02 / d, 0)

def mv_mvp_m00i(mv, mvp):
    # Take a model-view matrix and a model-view projection matrix and calculate
    # the top left square of the inverse projection matrix making assumptions
    # about the structure of the projection matrix to simplify the calculation.
    #
    # 1. Calculate the determinant of the model-view matrix, simplifying on the
    #    assumption that the 4th column is 0,0,0,1:
    d = determinant_euclidean(mv)

    # 2. Calculate the 1st row of the inverted model-view matrix:
    mvi = inverse_matrix_euclidean_m0(mv, d)

    # 3. Multiply the 1st row of the inverted model-view matrix with the 1st
    #    column of the model-view-projection matrix:
    p00 = (mvi[0] * mvp[0,0] + \
           mvi[1] * mvp[1,0] + \
           mvi[2] * mvp[2,0])

    # 4. Calculate the top-left cell of the inverse projection matrix, which
    #    thanks to the structure of a projection matrix (even an off-center
    #    one) turns out to simplify down to:
    return 1 / p00

# So, the assembly should be something like this, which will save us using up
# one of the two matrix copy slots in Helix mod where we only need to invert a
# local MV matrix to multiply against a local MVP matrix, which I do in Unity
# games some of the time (NOTE: Unverified!):
#
# // 1. Calculate 1/determinant of the MV matrix, simplifying by assuming the
# //    4th column of the MV matrix is 0,0,0,1
# //
# // mathomatic simplified it to:
# // 1 / ((m12*((m20*m01) - (m21*m00))) + (m02*((m21*m10) - (m20*m11))) + (m22*((m00*m11) - (m01*m10))));
# //
# // Replace row numbers with register components (assumes column-major order):
# //   (mv2.x*((mv0.y*mv1.z) - (mv0.z*mv1.y)))
# // + (mv2.y*((mv0.z*mv1.x) - (mv0.x*mv1.z)))
# // + (mv2.z*((mv0.x*mv1.y) - (mv0.y*mv1.x)))
#
# // Do some multiplications in parallel with SIMD instructions:
# mov r22.xyz, mv1
# mul r20.xyz, mv0.yzx, r22.zxy	// mv0.y*mv1.z, mv0.z*mv1.x, mv0.x*mv1.y
# mul r21.xyz, mv0.zxy, r22.yzx	// mv0.z*mv1.y, mv0.x*mv1.z, mv0.y*mv1.x
# // Do the subtractions:
# add r20.xyz, r20.xyz, -r21.xyz // mv0.y*mv1.z - mv0.z*mv1.y, mv0.z*mv1.x - mv0.x*mv1.z, mv0.x*mv1.y - mv0.y*mv1.x
# // Now the multiplications:
# mul r20.xyz, r20.xyz, mv2.xyz
# // Sum it together to get the determinant:
# add r22.w, r20.x, r20.y
# add r22.w, r22.w, r20.z
# // And finally get 1/determinant:
# rcp r22.w, r22.w
#
# // 2. Calculate the 1st row of the inverted MV matrix, simplifying by assuimg
# //    the 4th column of the MV matrix is 0,0,0,1
# //
# // m00 = (mv1.y*mv2.z - mv1.z*mv2.y) / determinant
# // m01 = (mv1.z*mv2.x - mv1.x*mv2.z) / determinant
# // m02 = (mv1.x*mv2.y - mv1.y*mv2.x) / determinant
#
# // Do some multiplications in parallel with SIMD instructions:
# mul r20.xyz, r22.yzx, mv2.zxy // mv1.y*mv2.z, mv1.z*mv2.x, mv1.x*mv2.y
# mul r21.xyz, r22.zxy, mv2.yzx // mv1.z*mv2.y, mv1.x*mv2.z, mv1.y*mv2.x
# // Do the subtractions:
# add r20.xyz, r20.xyz, -r21.xyz // mv1.y*mv2.z - mv1.z*mv2.y, mv1.z*mv2.x - mv1.x*mv2.z, mv1.x*mv2.y - mv1.y*mv2.x
# // Multiply against 1/determinant:
# mul r20.xyz, r20.xyz, r22.www
#
# // 3. Multiply the first row of the inverted MV matrix with the 1st column of
# //    the MVP matrix (MV.I[0,3] is 0, so only worry about the 1st three):
# dp3 r20.x, r20.xyz, mvp0.xyz
#
# // 4. Calculate the top-left cell of the inverse projection matrix,
# //    simplifying based on assumptions about the structure of a projection
# //    matrix (should even work for off-center projection matrices):
# rcp r20.x, r20.x
