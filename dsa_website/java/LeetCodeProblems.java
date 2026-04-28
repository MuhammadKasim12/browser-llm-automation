import java.util.Arrays;

/**
 * Collection of LeetCode Bit Manipulation and Math Problems
 * Contains solutions with comprehensive test cases.
 */
public class LeetCodeProblems {

    /**
     * LeetCode 268 - Missing Number (XOR Solution)
     * Given an array containing n distinct numbers in range [0, n],
     * find the one number missing from the array.
     *
     * Time Complexity: O(n) - single pass through array
     * Space Complexity: O(1) - constant extra space
     *
     * XOR Approach: XOR all indices and all numbers. Since a^a=0 and a^0=a,
     * all paired numbers cancel out, leaving only the missing number.
     *
     * @param nums array of n distinct numbers from range [0, n]
     * @return the missing number in the range
     */
    public static int missingNumber(int[] nums) {
        int xor = nums.length;
        for (int i = 0; i < nums.length; i++) {
            xor ^= i ^ nums[i];
        }
        return xor;
    }

    /**
     * LeetCode 371 - Sum of Two Integers (Bit Manipulation)
     * Calculate the sum of two integers without using + or - operators.
     *
     * Time Complexity: O(1) - max 32 iterations for 32-bit integers
     * Space Complexity: O(1) - constant extra space
     *
     * Approach: Use XOR to add bits without carry, AND shifted left for carry.
     * Repeat until no carry remains.
     *
     * @param a first integer
     * @param b second integer
     * @return sum of a and b
     */
    public static int getSum(int a, int b) {
        while (b != 0) {
            int carry = (a & b) << 1;
            a = a ^ b;
            b = carry;
        }
        return a;
    }

    /**
     * LeetCode 7 - Reverse Integer
     * Reverse digits of a 32-bit signed integer.
     * Return 0 if reversed integer overflows.
     *
     * Time Complexity: O(log10(x)) - number of digits in x
     * Space Complexity: O(1) - constant extra space
     *
     * @param x integer to reverse
     * @return reversed integer, or 0 if overflow
     */
    public static int reverse(int x) {
        int result = 0;
        while (x != 0) {
            int digit = x % 10;
            x /= 10;
            // Check for overflow before multiplying
            if (result > Integer.MAX_VALUE / 10 ||
                (result == Integer.MAX_VALUE / 10 && digit > 7)) {
                return 0;
            }
            if (result < Integer.MIN_VALUE / 10 ||
                (result == Integer.MIN_VALUE / 10 && digit < -8)) {
                return 0;
            }
            result = result * 10 + digit;
        }
        return result;
    }

    /**
     * LeetCode 338 - Counting Bits (Dynamic Programming)
     * Given integer n, return array ans where ans[i] is the number
     * of 1's in binary representation of i, for 0 <= i <= n.
     *
     * Time Complexity: O(n) - single pass from 0 to n
     * Space Complexity: O(n) - output array of size n+1
     *
     * DP Approach: dp[i] = dp[i >> 1] + (i & 1)
     * Right shift removes last bit, (i & 1) adds back if last bit was 1.
     *
     * @param n upper bound of range
     * @return array containing count of 1 bits for each number 0 to n
     */
    public static int[] countBits(int n) {
        int[] dp = new int[n + 1];
        for (int i = 1; i <= n; i++) {
            dp[i] = dp[i >> 1] + (i & 1);
        }
        return dp;
    }

    /**
     * LeetCode 191 - Number of 1 Bits (Hamming Weight)
     * Return the number of '1' bits in unsigned integer representation.
     *
     * Time Complexity: O(k) where k is number of 1 bits
     * Space Complexity: O(1) - constant extra space
     *
     * Brian Kernighan's Algorithm: n & (n-1) clears the lowest set bit.
     * Count iterations until n becomes 0.
     *
     * @param n integer to count bits
     * @return number of 1 bits (Hamming weight)
     */
    public static int hammingWeight(int n) {
        int count = 0;
        while (n != 0) {
            n = n & (n - 1);
            count++;
        }
        return count;
    }

    // ==================== TEST METHODS ====================

    private static int testsPassed = 0;
    private static int testsFailed = 0;

    private static void test(String name, boolean condition) {
        if (condition) {
            System.out.println("✓ PASS: " + name);
            testsPassed++;
        } else {
            System.out.println("✗ FAIL: " + name);
            testsFailed++;
        }
    }

    public static void main(String[] args) {
        System.out.println("========== LeetCode Bit Manipulation Problems ==========\n");

        // Test Missing Number (LeetCode 268)
        System.out.println("--- LeetCode 268: Missing Number ---");
        test("missingNumber [3,0,1] = 2", missingNumber(new int[]{3, 0, 1}) == 2);
        test("missingNumber [0,1] = 2", missingNumber(new int[]{0, 1}) == 2);
        test("missingNumber [9,6,4,2,3,5,7,0,1] = 8",
             missingNumber(new int[]{9, 6, 4, 2, 3, 5, 7, 0, 1}) == 8);
        test("missingNumber [0] = 1", missingNumber(new int[]{0}) == 1);
        test("missingNumber [1] = 0", missingNumber(new int[]{1}) == 0);

        // Test Sum of Two Integers (LeetCode 371)
        System.out.println("\n--- LeetCode 371: Sum of Two Integers ---");
        test("getSum(1, 2) = 3", getSum(1, 2) == 3);
        test("getSum(2, 3) = 5", getSum(2, 3) == 5);
        test("getSum(-1, 1) = 0", getSum(-1, 1) == 0);
        test("getSum(-2, -3) = -5", getSum(-2, -3) == -5);
        test("getSum(0, 0) = 0", getSum(0, 0) == 0);
        test("getSum(100, 200) = 300", getSum(100, 200) == 300);

        // Test Reverse Integer (LeetCode 7)
        System.out.println("\n--- LeetCode 7: Reverse Integer ---");
        test("reverse(123) = 321", reverse(123) == 321);
        test("reverse(-123) = -321", reverse(-123) == -321);
        test("reverse(120) = 21", reverse(120) == 21);
        test("reverse(0) = 0", reverse(0) == 0);
        test("reverse(1534236469) = 0 (overflow)", reverse(1534236469) == 0);
        test("reverse(-2147483648) = 0 (overflow)", reverse(-2147483648) == 0);

        // Test Counting Bits (LeetCode 338)
        System.out.println("\n--- LeetCode 338: Counting Bits ---");
        test("countBits(2) = [0,1,1]",
             Arrays.equals(countBits(2), new int[]{0, 1, 1}));
        test("countBits(5) = [0,1,1,2,1,2]",
             Arrays.equals(countBits(5), new int[]{0, 1, 1, 2, 1, 2}));
        test("countBits(0) = [0]",
             Arrays.equals(countBits(0), new int[]{0}));
        test("countBits(7) = [0,1,1,2,1,2,2,3]",
             Arrays.equals(countBits(7), new int[]{0, 1, 1, 2, 1, 2, 2, 3}));

        // Test Number of 1 Bits (LeetCode 191)
        System.out.println("\n--- LeetCode 191: Number of 1 Bits ---");
        test("hammingWeight(11) = 3", hammingWeight(11) == 3);
        test("hammingWeight(128) = 1", hammingWeight(128) == 1);
        test("hammingWeight(255) = 8", hammingWeight(255) == 8);
        test("hammingWeight(0) = 0", hammingWeight(0) == 0);
        test("hammingWeight(1) = 1", hammingWeight(1) == 1);
        test("hammingWeight(-1) = 32 (all bits set)", hammingWeight(-1) == 32);

        // Print summary
        System.out.println("\n========== TEST SUMMARY ==========");
        System.out.println("Tests Passed: " + testsPassed);
        System.out.println("Tests Failed: " + testsFailed);
        System.out.println("Total Tests:  " + (testsPassed + testsFailed));
        System.out.println("==================================");
    }
}
