import java.util.Arrays;

/**
 * DSA Algorithms Implementation with Time Complexity Analysis
 * Contains common algorithms with test cases demonstrating correctness.
 */
public class DSAAlgorithms {

    /**
     * Binary Search - Finds target in sorted array.
     * Time Complexity: O(log n) - halves search space each iteration
     * Space Complexity: O(1) - uses constant extra space
     * @param arr sorted array to search
     * @param target value to find
     * @return index of target, or -1 if not found
     */
    public static int binarySearch(int[] arr, int target) {
        int left = 0, right = arr.length - 1;
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (arr[mid] == target) return mid;
            if (arr[mid] < target) left = mid + 1;
            else right = mid - 1;
        }
        return -1;
    }

    /**
     * Linear Search - Finds target by checking each element.
     * Time Complexity: O(n) - may check all elements
     * Space Complexity: O(1) - uses constant extra space
     * @param arr array to search
     * @param target value to find
     * @return index of target, or -1 if not found
     */
    public static int linearSearch(int[] arr, int target) {
        for (int i = 0; i < arr.length; i++) {
            if (arr[i] == target) return i;
        }
        return -1;
    }

    /**
     * Merge Sort - Divides array, sorts halves, merges them.
     * Time Complexity: O(n log n) - divides log n times, merges n elements
     * Space Complexity: O(n) - requires temporary arrays for merging
     * @param arr array to sort
     * @return new sorted array
     */
    public static int[] mergeSort(int[] arr) {
        if (arr.length <= 1) return arr;
        int mid = arr.length / 2;
        int[] left = mergeSort(Arrays.copyOfRange(arr, 0, mid));
        int[] right = mergeSort(Arrays.copyOfRange(arr, mid, arr.length));
        return merge(left, right);
    }

    private static int[] merge(int[] left, int[] right) {
        int[] result = new int[left.length + right.length];
        int i = 0, j = 0, k = 0;
        while (i < left.length && j < right.length) {
            result[k++] = (left[i] <= right[j]) ? left[i++] : right[j++];
        }
        while (i < left.length) result[k++] = left[i++];
        while (j < right.length) result[k++] = right[j++];
        return result;
    }

    /**
     * Fibonacci Recursive - Computes nth Fibonacci number.
     * Time Complexity: O(2^n) - exponential due to repeated subproblems
     * Space Complexity: O(n) - recursion stack depth
     * @param n position in Fibonacci sequence (0-indexed)
     * @return nth Fibonacci number
     */
    public static int fibonacciRecursive(int n) {
        if (n <= 1) return n;
        return fibonacciRecursive(n - 1) + fibonacciRecursive(n - 2);
    }

    /**
     * Get First Element - Returns first element of array.
     * Time Complexity: O(1) - direct array access
     * Space Complexity: O(1) - no extra space used
     * @param arr array to access
     * @return first element, or Integer.MIN_VALUE if empty
     */
    public static int getFirstElement(int[] arr) {
        if (arr == null || arr.length == 0) return Integer.MIN_VALUE;
        return arr[0];
    }

    private static void test(String name, boolean condition) {
        System.out.println(name + ": " + (condition ? "PASS" : "FAIL"));
    }

    public static void main(String[] args) {
        System.out.println("=== DSA Algorithms Test Suite ===\n");

        // Binary Search Tests
        System.out.println("-- Binary Search O(log n) --");
        int[] sorted = {1, 3, 5, 7, 9, 11, 13, 15};
        test("Find middle element (7)", binarySearch(sorted, 7) == 3);
        test("Find first element (1)", binarySearch(sorted, 1) == 0);
        test("Find last element (15)", binarySearch(sorted, 15) == 7);
        test("Element not found (6)", binarySearch(sorted, 6) == -1);
        test("Empty array", binarySearch(new int[]{}, 5) == -1);

        // Linear Search Tests
        System.out.println("\n-- Linear Search O(n) --");
        int[] unsorted = {4, 2, 9, 1, 7, 3};
        test("Find existing element (9)", linearSearch(unsorted, 9) == 2);
        test("Find first element (4)", linearSearch(unsorted, 4) == 0);
        test("Find last element (3)", linearSearch(unsorted, 3) == 5);
        test("Element not found (8)", linearSearch(unsorted, 8) == -1);
        test("Empty array", linearSearch(new int[]{}, 5) == -1);

        // Merge Sort Tests
        System.out.println("\n-- Merge Sort O(n log n) --");
        test("Sort unsorted array", Arrays.equals(mergeSort(new int[]{5, 2, 8, 1, 9}), new int[]{1, 2, 5, 8, 9}));
        test("Already sorted", Arrays.equals(mergeSort(new int[]{1, 2, 3, 4}), new int[]{1, 2, 3, 4}));
        test("Reverse sorted", Arrays.equals(mergeSort(new int[]{5, 4, 3, 2, 1}), new int[]{1, 2, 3, 4, 5}));
        test("Single element", Arrays.equals(mergeSort(new int[]{42}), new int[]{42}));
        test("Empty array", Arrays.equals(mergeSort(new int[]{}), new int[]{}));
        test("Duplicates", Arrays.equals(mergeSort(new int[]{3, 1, 3, 2, 1}), new int[]{1, 1, 2, 3, 3}));

        // Fibonacci Tests
        System.out.println("\n-- Fibonacci Recursive O(2^n) --");
        test("fib(0) = 0", fibonacciRecursive(0) == 0);
        test("fib(1) = 1", fibonacciRecursive(1) == 1);
        test("fib(5) = 5", fibonacciRecursive(5) == 5);
        test("fib(10) = 55", fibonacciRecursive(10) == 55);
        test("fib(15) = 610", fibonacciRecursive(15) == 610);

        // Get First Element Tests
        System.out.println("\n-- Get First Element O(1) --");
        test("Normal array", getFirstElement(new int[]{10, 20, 30}) == 10);
        test("Single element", getFirstElement(new int[]{99}) == 99);
        test("Negative first", getFirstElement(new int[]{-5, 0, 5}) == -5);
        test("Empty array", getFirstElement(new int[]{}) == Integer.MIN_VALUE);
        test("Null array", getFirstElement(null) == Integer.MIN_VALUE);

        System.out.println("\n=== All Tests Complete ===");
    }
}

