# Adapted verbatim from P3 session 3d9c, commit a37eb931a22fb7df7e0d00d193538ce5289ae045.
"""Persistent AVL index of free resource intervals, with exact earliest fit."""
from __future__ import annotations

from dataclasses import dataclass
from math import inf


@dataclass(frozen=True, slots=True)
class Node:
    key: int
    stop: int | float
    left: Node | None
    right: Node | None
    height: int
    maximum: int | float


def height(node):
    return node.height if node else 0


def make(key, stop, left=None, right=None):
    return Node(key, stop, left, right, 1 + max(height(left), height(right)),
                max(stop - key, left.maximum if left else 0,
                    right.maximum if right else 0))


def rotate_left(node):
    right = node.right
    return make(right.key, right.stop,
                make(node.key, node.stop, node.left, right.left), right.right)


def rotate_right(node):
    left = node.left
    return make(left.key, left.stop, left.left,
                make(node.key, node.stop, left.right, node.right))


def balance(node):
    if height(node.left) - height(node.right) > 1:
        if height(node.left.left) < height(node.left.right):
            node = make(node.key, node.stop, rotate_left(node.left), node.right)
        return rotate_right(node)
    if height(node.right) - height(node.left) > 1:
        if height(node.right.right) < height(node.right.left):
            node = make(node.key, node.stop, node.left, rotate_right(node.right))
        return rotate_left(node)
    return node


def put(node, key, stop):
    if node is None:
        return make(key, stop)
    if key == node.key:
        return make(key, stop, node.left, node.right)
    if key < node.key:
        return balance(make(node.key, node.stop, put(node.left, key, stop), node.right))
    return balance(make(node.key, node.stop, node.left, put(node.right, key, stop)))


def floor(node, key):
    found = None
    while node:
        if node.key <= key:
            found, node = node, node.right
        else:
            node = node.left
    return found


def first_fit(node, minimum, duration):
    if node is None or node.maximum < duration:
        return None
    if node.key < minimum:
        return first_fit(node.right, minimum, duration)
    left = first_fit(node.left, minimum, duration)
    if left:
        return left
    if node.stop - node.key >= duration:
        return node
    return first_fit(node.right, minimum, duration)


def empty():
    return make(0, inf)


def earliest(root, release, duration):
    """Earliest free [start,start+duration), no preemption or existing edits."""
    if type(release) is not int or type(duration) is not int or release < 0 or duration <= 0:
        raise ValueError('nonnegative integer release and positive integer duration required')
    preceding = floor(root, release)
    if preceding and preceding.stop >= release + duration:
        return release
    chosen = first_fit(root, release, duration)
    if chosen is None:
        raise ValueError('calendar is missing its unbounded final interval')
    return chosen.key


def reserve(root, start, duration):
    if type(start) is not int or type(duration) is not int or start < 0 or duration <= 0:
        raise ValueError('nonnegative integer start and positive integer duration required')
    preceding = floor(root, start)
    if preceding is None or preceding.stop < start + duration:
        raise ValueError('reservation overlaps an occupied resource interval')
    # Replace one free interval by its left and right remainders. Empty
    # intervals are harmless and keep insertion logic and witnesses simple.
    return put(put(root, preceding.key, start), start + duration, preceding.stop)
