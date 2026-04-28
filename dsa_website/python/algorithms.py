"""
DSA Algorithms Implementation with Comprehensive Test Cases.

This module contains implementations of common data structures and algorithms
with detailed time and space complexity analysis.
"""

import unittest
from typing import List, Optional


def binary_search(arr: List[int], target: int) -> int:
    """
    Search for target in a sorted array using binary search.

    Time Complexity: O(log n) - Array is halved in each iteration
    Space Complexity: O(1) - Only uses constant extra space

    Args:
        arr: A sorted list of integers
        target: The value to search for

    Returns:
        Index of target if found, -1 otherwise
    """
    left, right = 0, len(arr) - 1

    while left <= right:
        mid = left + (right - left) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


def linear_search(arr: List[int], target: int) -> int:
    """
    Search for target in an array using linear search.

    Time Complexity: O(n) - May need to check every element
    Space Complexity: O(1) - Only uses constant extra space

    Args:
        arr: A list of integers (does not need to be sorted)
        target: The value to search for

    Returns:
        Index of target if found, -1 otherwise
    """
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1


def merge_sort(arr: List[int]) -> List[int]:
    """
    Sort an array using merge sort algorithm.

    Time Complexity: O(n log n) - Divides array log(n) times, merges in O(n)
    Space Complexity: O(n) - Requires auxiliary space for merging

    Args:
        arr: A list of integers to sort

    Returns:
        A new sorted list
    """
    if len(arr) <= 1:
        return arr.copy()

    mid = len(arr) // 2
    left = merge_sort(arr[:mid])
    right = merge_sort(arr[mid:])

    return _merge(left, right)


def _merge(left: List[int], right: List[int]) -> List[int]:
    """Helper function to merge two sorted arrays."""
    result = []
    i = j = 0

    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1

    result.extend(left[i:])
    result.extend(right[j:])
    return result


def fibonacci_recursive(n: int) -> int:
    """
    Calculate the nth Fibonacci number using recursion.

    Time Complexity: O(2^n) - Each call branches into two recursive calls
    Space Complexity: O(n) - Maximum recursion depth is n

    Args:
        n: The position in Fibonacci sequence (0-indexed)

    Returns:
        The nth Fibonacci number

    Raises:
        ValueError: If n is negative
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    if n <= 1:
        return n
    return fibonacci_recursive(n - 1) + fibonacci_recursive(n - 2)


def get_first_element(arr: List[int]) -> Optional[int]:
    """
    Get the first element of an array.

    Time Complexity: O(1) - Direct index access
    Space Complexity: O(1) - No extra space used

    Args:
        arr: A list of integers

    Returns:
        The first element if array is non-empty, None otherwise
    """
    if not arr:
        return None
    return arr[0]


# ==================== Test Cases ====================

class TestBinarySearch(unittest.TestCase):
    """Test cases for binary_search function."""

    def test_element_found_middle(self):
        self.assertEqual(binary_search([1, 2, 3, 4, 5], 3), 2)

    def test_element_found_first(self):
        self.assertEqual(binary_search([1, 2, 3, 4, 5], 1), 0)

    def test_element_found_last(self):
        self.assertEqual(binary_search([1, 2, 3, 4, 5], 5), 4)



class TestLinearSearch(unittest.TestCase):
    """Test cases for linear_search function."""

    def test_element_found_middle(self):
        self.assertEqual(linear_search([1, 2, 3, 4, 5], 3), 2)

    def test_element_found_first(self):
        self.assertEqual(linear_search([1, 2, 3, 4, 5], 1), 0)

    def test_element_found_last(self):
        self.assertEqual(linear_search([1, 2, 3, 4, 5], 5), 4)

    def test_element_not_found(self):
        self.assertEqual(linear_search([1, 2, 3, 4, 5], 6), -1)

    def test_empty_array(self):
        self.assertEqual(linear_search([], 1), -1)

    def test_unsorted_array(self):
        self.assertEqual(linear_search([5, 2, 8, 1, 9], 8), 2)

    def test_duplicate_elements(self):
        # Should return first occurrence
        self.assertEqual(linear_search([1, 2, 2, 3, 2], 2), 1)


class TestMergeSort(unittest.TestCase):
    """Test cases for merge_sort function."""

    def test_sorted_array(self):
        self.assertEqual(merge_sort([1, 2, 3, 4, 5]), [1, 2, 3, 4, 5])

    def test_reverse_sorted(self):
        self.assertEqual(merge_sort([5, 4, 3, 2, 1]), [1, 2, 3, 4, 5])

    def test_unsorted_array(self):
        self.assertEqual(merge_sort([3, 1, 4, 1, 5, 9, 2, 6]), [1, 1, 2, 3, 4, 5, 6, 9])

    def test_empty_array(self):
        self.assertEqual(merge_sort([]), [])

    def test_single_element(self):
        self.assertEqual(merge_sort([42]), [42])

    def test_duplicate_elements(self):
        self.assertEqual(merge_sort([3, 3, 3, 1, 1]), [1, 1, 3, 3, 3])

    def test_negative_numbers(self):
        self.assertEqual(merge_sort([-3, 1, -5, 2, 0]), [-5, -3, 0, 1, 2])

    def test_does_not_modify_original(self):
        original = [3, 1, 2]
        merge_sort(original)
        self.assertEqual(original, [3, 1, 2])


class TestFibonacciRecursive(unittest.TestCase):
    """Test cases for fibonacci_recursive function."""

    def test_fib_zero(self):
        self.assertEqual(fibonacci_recursive(0), 0)

    def test_fib_one(self):
        self.assertEqual(fibonacci_recursive(1), 1)

    def test_fib_two(self):
        self.assertEqual(fibonacci_recursive(2), 1)

    def test_fib_ten(self):
        self.assertEqual(fibonacci_recursive(10), 55)

    def test_fib_fifteen(self):
        self.assertEqual(fibonacci_recursive(15), 610)

    def test_negative_raises_error(self):
        with self.assertRaises(ValueError):
            fibonacci_recursive(-1)

    def test_sequence(self):
        expected = [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]
        result = [fibonacci_recursive(i) for i in range(10)]
        self.assertEqual(result, expected)


class TestGetFirstElement(unittest.TestCase):
    """Test cases for get_first_element function."""

    def test_non_empty_array(self):
        self.assertEqual(get_first_element([1, 2, 3]), 1)

    def test_empty_array(self):
        self.assertIsNone(get_first_element([]))

    def test_single_element(self):
        self.assertEqual(get_first_element([42]), 42)

    def test_negative_first(self):
        self.assertEqual(get_first_element([-5, 10, 20]), -5)

    def test_zero_first(self):
        self.assertEqual(get_first_element([0, 1, 2]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
