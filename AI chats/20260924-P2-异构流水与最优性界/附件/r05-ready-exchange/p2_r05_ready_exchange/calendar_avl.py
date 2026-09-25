"""Persistent free-interval AVL.
Algorithm/source basis: authorized Vioano gap_calendar.py at
28818874e5e0306793427526c8612383a9397363 (blob e36883a4...).
This local copy supports standalone synthetic tests; the project adapter should
use its existing gap_calendar functions. No hardware simulation is performed.
"""
from dataclasses import dataclass
from math import inf

@dataclass(frozen=True, slots=True)
class Node:
    key: int
    stop: int | float
    left: 'Node | None'
    right: 'Node | None'
    height: int
    maximum: int | float

def height(n): return n.height if n else 0

def make(key, stop, left=None, right=None):
    return Node(key, stop, left, right, 1 + max(height(left), height(right)),
                max(stop-key, left.maximum if left else 0, right.maximum if right else 0))

def rotate_left(n):
    r=n.right
    return make(r.key,r.stop,make(n.key,n.stop,n.left,r.left),r.right)

def rotate_right(n):
    l=n.left
    return make(l.key,l.stop,l.left,make(n.key,n.stop,l.right,n.right))

def balance(n):
    if height(n.left)-height(n.right)>1:
        if height(n.left.left)<height(n.left.right):
            n=make(n.key,n.stop,rotate_left(n.left),n.right)
        return rotate_right(n)
    if height(n.right)-height(n.left)>1:
        if height(n.right.right)<height(n.right.left):
            n=make(n.key,n.stop,n.left,rotate_right(n.right))
        return rotate_left(n)
    return n

def put(n,key,stop):
    if n is None: return make(key,stop)
    if key==n.key: return make(key,stop,n.left,n.right)
    if key<n.key: return balance(make(n.key,n.stop,put(n.left,key,stop),n.right))
    return balance(make(n.key,n.stop,n.left,put(n.right,key,stop)))

def floor(n,key):
    ans=None
    while n:
        if n.key<=key: ans,n=n,n.right
        else: n=n.left
    return ans

def first_fit(n,minimum,duration):
    if n is None or n.maximum<duration: return None
    if n.key<minimum: return first_fit(n.right,minimum,duration)
    l=first_fit(n.left,minimum,duration)
    if l: return l
    if n.stop-n.key>=duration: return n
    return first_fit(n.right,minimum,duration)

def empty(): return make(0,inf)

def earliest(root,release,duration):
    if type(release) is not int or type(duration) is not int or release<0 or duration<=0:
        raise ValueError('integer release >=0 and duration >0 required')
    n=floor(root,release)
    if n and n.stop>=release+duration: return release
    n=first_fit(root,release,duration)
    if n is None: raise ValueError('missing infinite final interval')
    return n.key

def reserve(root,start,duration):
    n=floor(root,start)
    if n is None or n.stop<start+duration: raise ValueError('resource overlap')
    return put(put(root,n.key,start),start+duration,n.stop)
