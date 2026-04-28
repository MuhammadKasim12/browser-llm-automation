"""
LeetCode Bit Manipulation and Math Problems

This module contains solutions to classic LeetCode problems involving
bit manipulation and mathematical operations with comprehensive test cases.
"""

import unittest
from typing import List


def missing_number(nums: List[int]) -> int:
    """
    LeetCode 268: Missing Number (XOR Solution)
    
    Given an array nums containing n distinct numbers in the range [0, n],
    return the only number in the range that is missing from the array.
    
    Algorithm:
        Uses XOR properties: a ^ a = 0 and a ^ 0 = a
        XOR all numbers from 0 to n with all numbers in the array.
        The missing number will be the only one not cancelled out.
    
    Time Complexity: O(n) - single pass through the array
    Space Complexity: O(1) - only using a single variable
    
    Args:
        nums: List of n distinct integers in range [0, n]
    
    Returns:
        The missing number from the sequence
    """
    n = len(nums)
    result = n  # Start with n since indices go from 0 to n-1
    for i in range(n):
        result ^= i ^ nums[i]
    return result


def get_sum(a: int, b: int) -> int:
    """
    LeetCode 371: Sum of Two Integers (Bit Manipulation)
    
    Calculate the sum of two integers without using + or - operators.
    
    Algorithm:
        Uses bit manipulation with XOR for sum without carry,
        AND with left shift for carry. Repeat until no carry remains.
        Uses 32-bit masking to handle negative numbers in Python.
    
    Time Complexity: O(1) - maximum 32 iterations for 32-bit integers
    Space Complexity: O(1) - only using constant extra space
    
    Args:
        a: First integer
        b: Second integer
    
    Returns:
        Sum of a and b
    """
    MASK = 0xFFFFFFFF  # 32-bit mask
    MAX_INT = 0x7FFFFFFF  # Maximum positive 32-bit integer
    
    while b != 0:
        # Calculate sum without carry using XOR
        temp = (a ^ b) & MASK
        # Calculate carry using AND and left shift
        b = ((a & b) << 1) & MASK
        a = temp
    
    # If a is negative in 32-bit representation, convert to Python negative
    return a if a <= MAX_INT else ~(a ^ MASK)


def reverse_integer(x: int) -> int:
    """
    LeetCode 7: Reverse Integer
    
    Given a signed 32-bit integer x, return x with its digits reversed.
    If reversing x causes the value to go outside the signed 32-bit
    integer range [-2^31, 2^31 - 1], return 0.
    
    Algorithm:
        Extract digits from the end using modulo, build reversed number
        by multiplying result by 10 and adding the digit. Check for
        overflow before each operation.
    
    Time Complexity: O(log x) - number of digits in x
    Space Complexity: O(1) - only using constant extra space
    
    Args:
        x: A signed 32-bit integer
    
    Returns:
        The reversed integer, or 0 if overflow occurs
    """
    INT_MIN, INT_MAX = -2**31, 2**31 - 1
    
    sign = 1 if x >= 0 else -1
    x = abs(x)
    result = 0
    
    while x != 0:
        digit = x % 10
        x //= 10
        
        # Check for overflow before multiplying
        if result > (INT_MAX - digit) // 10:
            return 0
        
        result = result * 10 + digit
    
    result *= sign
    
    # Final bounds check
    if result < INT_MIN or result > INT_MAX:
        return 0
    
    return result


def count_bits(n: int) -> List[int]:
    """
    LeetCode 338: Counting Bits (Dynamic Programming)
    
    Given an integer n, return an array ans of length n + 1 such that
    for each i (0 <= i <= n), ans[i] is the number of 1's in the binary
    representation of i.
    
    Algorithm:
        Uses DP with the relationship: countBits(i) = countBits(i >> 1) + (i & 1)
        The number of 1s in i equals the number of 1s in i//2 plus
        whether the last bit is 1.
    
    Time Complexity: O(n) - single pass from 0 to n
    Space Complexity: O(n) - storing results for all numbers 0 to n
    
    Args:
        n: Non-negative integer
    
    Returns:
        List where index i contains count of 1-bits in binary representation of i
    """
    result = [0] * (n + 1)
    for i in range(1, n + 1):
        # i >> 1 gives us i // 2, and i & 1 checks if last bit is 1
        result[i] = result[i >> 1] + (i & 1)
    return result


def hamming_weight(n: int) -> int:
    """
    LeetCode 191: Number of 1 Bits (Hamming Weight)

    Given a positive integer n, return the number of set bits (1s)
    in its binary representation (also known as Hamming weight).

    Algorithm:
        Uses Brian Kernighan's algorithm: n & (n-1) clears the
        lowest set bit. Count how many times we can do this.

    Time Complexity: O(k) where k is the number of set bits
    Space Complexity: O(1) - only using constant extra space

    Args:
        n: A positive integer

    Returns:
        Count of 1-bits in the binary representation of n
    """
    count = 0
    while n:
        n &= (n - 1)  # Clear the lowest set bit
        count += 1
    return count


# =============================================================================
# Test Cases
# =============================================================================


class TestMissingNumber(unittest.TestCase):
    """Test cases for LeetCode 268: Missing Number"""

    def test_missing_at_end(self):
        """Test when missing number is at the end"""
        self.assertEqual(missing_number([0, 1, 2]), 3)

    def test_missing_in_middle(self):
        """Test when missing number is in the middle"""
        self.assertEqual(missing_number([0, 1, 3]), 2)
        self.assertEqual(missing_number([9, 6, 4, 2, 3, 5, 7, 0, 1]), 8)

    def test_missing_at_start(self):
        """Test when missing number is 0"""
        self.assertEqual(missing_number([1, 2, 3]), 0)
        self.assertEqual(missing_number([1]), 0)

    def test_single_element(self):
        """Test with single element array"""
        self.assertEqual(missing_number([0]), 1)

    def test_two_elements(self):
        """Test with two element array"""
        self.assertEqual(missing_number([1, 0]), 2)
        self.assertEqual(missing_number([0, 2]), 1)


class TestGetSum(unittest.TestCase):
    """Test cases for LeetCode 371: Sum of Two Integers"""

    def test_positive_numbers(self):
        """Test sum of two positive numbers"""
        self.assertEqual(get_sum(1, 2), 3)
        self.assertEqual(get_sum(5, 3), 8)
        self.assertEqual(get_sum(100, 200), 300)

    def test_negative_numbers(self):
        """Test sum of two negative numbers"""
        self.assertEqual(get_sum(-1, -1), -2)
        self.assertEqual(get_sum(-5, -3), -8)

    def test_mixed_signs(self):
        """Test sum of positive and negative numbers"""
        self.assertEqual(get_sum(2, -3), -1)
        self.assertEqual(get_sum(-2, 3), 1)
        self.assertEqual(get_sum(-1, 1), 0)

    def test_with_zero(self):
        """Test sum with zero"""
        self.assertEqual(get_sum(0, 5), 5)
        self.assertEqual(get_sum(5, 0), 5)
        self.assertEqual(get_sum(0, 0), 0)


class TestReverseInteger(unittest.TestCase):
    """Test cases for LeetCode 7: Reverse Integer"""

    def test_positive_numbers(self):
        """Test reversing positive numbers"""
        self.assertEqual(reverse_integer(123), 321)
        self.assertEqual(reverse_integer(120), 21)
        self.assertEqual(reverse_integer(1), 1)

    def test_negative_numbers(self):
        """Test reversing negative numbers"""
        self.assertEqual(reverse_integer(-123), -321)
        self.assertEqual(reverse_integer(-120), -21)

    def test_zero(self):
        """Test with zero"""
        self.assertEqual(reverse_integer(0), 0)

    def test_overflow(self):
        """Test overflow cases returning 0"""
        self.assertEqual(reverse_integer(1534236469), 0)  # Would overflow
        self.assertEqual(reverse_integer(-2147483648), 0)  # Would overflow

    def test_trailing_zeros(self):
        """Test numbers with trailing zeros"""
        self.assertEqual(reverse_integer(1000), 1)
        self.assertEqual(reverse_integer(10), 1)


class TestCountBits(unittest.TestCase):
    """Test cases for LeetCode 338: Counting Bits"""

    def test_small_numbers(self):
        """Test with small n values"""
        self.assertEqual(count_bits(2), [0, 1, 1])
        self.assertEqual(count_bits(5), [0, 1, 1, 2, 1, 2])

    def test_zero(self):
        """Test with n = 0"""
        self.assertEqual(count_bits(0), [0])

    def test_one(self):
        """Test with n = 1"""
        self.assertEqual(count_bits(1), [0, 1])

    def test_powers_of_two(self):
        """Test that powers of 2 have exactly one bit"""
        result = count_bits(16)
        self.assertEqual(result[1], 1)   # 1 = 0b1
        self.assertEqual(result[2], 1)   # 2 = 0b10
        self.assertEqual(result[4], 1)   # 4 = 0b100
        self.assertEqual(result[8], 1)   # 8 = 0b1000
        self.assertEqual(result[16], 1)  # 16 = 0b10000

    def test_pattern(self):
        """Test known patterns"""
        result = count_bits(7)
        # 7 = 0b111 has 3 bits, 6 = 0b110 has 2 bits
        self.assertEqual(result[7], 3)
        self.assertEqual(result[6], 2)


class TestHammingWeight(unittest.TestCase):
    """Test cases for LeetCode 191: Number of 1 Bits"""

    def test_basic_cases(self):
        """Test basic cases"""
        self.assertEqual(hamming_weight(11), 3)  # 0b1011
        self.assertEqual(hamming_weight(128), 1)  # 0b10000000
        self.assertEqual(hamming_weight(255), 8)  # 0b11111111

    def test_powers_of_two(self):
        """Test powers of 2 (should have exactly 1 bit)"""
        self.assertEqual(hamming_weight(1), 1)
        self.assertEqual(hamming_weight(2), 1)
        self.assertEqual(hamming_weight(4), 1)
        self.assertEqual(hamming_weight(8), 1)
        self.assertEqual(hamming_weight(1024), 1)

    def test_all_ones(self):
        """Test numbers with all 1s in binary"""
        self.assertEqual(hamming_weight(7), 3)    # 0b111
        self.assertEqual(hamming_weight(15), 4)   # 0b1111
        self.assertEqual(hamming_weight(31), 5)   # 0b11111

    def test_zero(self):
        """Test with zero"""
        self.assertEqual(hamming_weight(0), 0)

    def test_large_numbers(self):
        """Test with larger numbers"""
        # 2^31 - 1 has 31 bits set
        self.assertEqual(hamming_weight(2147483647), 31)


if __name__ == "__main__":
    # Run all tests with verbose output
    unittest.main(verbosity=2)

