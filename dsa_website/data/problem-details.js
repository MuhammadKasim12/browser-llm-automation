/**
 * Problem Details Database
 * Contains full problem descriptions, examples, constraints, starter code, and test cases
 */

const PROBLEM_DETAILS = {
    'two-sum': {
        title: 'Two Sum',
        difficulty: 'easy',
        description: `
            <p>Given an array of integers <code>nums</code> and an integer <code>target</code>, return <em>indices of the two numbers such that they add up to <code>target</code></em>.</p>
            <p>You may assume that each input would have <strong>exactly one solution</strong>, and you may not use the same element twice.</p>
            <p>You can return the answer in any order.</p>
        `,
        examples: [
            {
                input: 'nums = [2,7,11,15], target = 9',
                output: '[0,1]',
                explanation: 'Because nums[0] + nums[1] == 9, we return [0, 1].'
            },
            {
                input: 'nums = [3,2,4], target = 6',
                output: '[1,2]',
                explanation: null
            },
            {
                input: 'nums = [3,3], target = 6',
                output: '[0,1]',
                explanation: null
            }
        ],
        constraints: [
            '2 <= nums.length <= 10<sup>4</sup>',
            '-10<sup>9</sup> <= nums[i] <= 10<sup>9</sup>',
            '-10<sup>9</sup> <= target <= 10<sup>9</sup>',
            '<strong>Only one valid answer exists.</strong>'
        ],
        starterCode: {
            python: `def twoSum(nums: list[int], target: int) -> list[int]:
    # Write your solution here
    pass`,
            javascript: `function twoSum(nums, target) {
    // Write your solution here
    
}`
        },
        testCases: [
            { input: { nums: [2, 7, 11, 15], target: 9 }, expected: [0, 1] },
            { input: { nums: [3, 2, 4], target: 6 }, expected: [1, 2] },
            { input: { nums: [3, 3], target: 6 }, expected: [0, 1] }
        ],
        testRunner: {
            python: `
# Test runner
def run_tests():
    test_cases = [
        (([2, 7, 11, 15], 9), [0, 1]),
        (([3, 2, 4], 6), [1, 2]),
        (([3, 3], 6), [0, 1]),
    ]
    results = []
    for i, (inputs, expected) in enumerate(test_cases):
        nums, target = inputs
        try:
            result = twoSum(nums.copy(), target)
            # Sort for comparison since order doesn't matter
            passed = sorted(result) == sorted(expected)
            results.append({
                'case': i + 1,
                'passed': passed,
                'input': f'nums = {nums}, target = {target}',
                'expected': expected,
                'actual': result
            })
        except Exception as e:
            results.append({
                'case': i + 1,
                'passed': False,
                'input': f'nums = {nums}, target = {target}',
                'expected': expected,
                'actual': f'Error: {str(e)}'
            })
    return results

import json
print(json.dumps(run_tests()))
`,
            javascript: `
// Test runner
function runTests() {
    const testCases = [
        { input: { nums: [2, 7, 11, 15], target: 9 }, expected: [0, 1] },
        { input: { nums: [3, 2, 4], target: 6 }, expected: [1, 2] },
        { input: { nums: [3, 3], target: 6 }, expected: [0, 1] },
    ];
    const results = [];
    for (let i = 0; i < testCases.length; i++) {
        const { input, expected } = testCases[i];
        try {
            const result = twoSum([...input.nums], input.target);
            const passed = JSON.stringify(result.sort()) === JSON.stringify(expected.sort());
            results.push({
                case: i + 1,
                passed,
                input: \`nums = [\${input.nums}], target = \${input.target}\`,
                expected,
                actual: result
            });
        } catch (e) {
            results.push({
                case: i + 1,
                passed: false,
                input: \`nums = [\${input.nums}], target = \${input.target}\`,
                expected,
                actual: \`Error: \${e.message}\`
            });
        }
    }
    return results;
}
JSON.stringify(runTests());
`
        },
        solution: {
            python: `def twoSum(nums: list[int], target: int) -> list[int]:
    """
    Time: O(n), Space: O(n)
    Use a hash map to store complement values
    """
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []`,
            javascript: `function twoSum(nums, target) {
    // Time: O(n), Space: O(n)
    const seen = new Map();
    for (let i = 0; i < nums.length; i++) {
        const complement = target - nums[i];
        if (seen.has(complement)) {
            return [seen.get(complement), i];
        }
        seen.set(nums[i], i);
    }
    return [];
}`
        }
    },

    'contains-duplicate': {
        title: 'Contains Duplicate',
        difficulty: 'easy',
        description: `
            <p>Given an integer array <code>nums</code>, return <code>true</code> if any value appears <strong>at least twice</strong> in the array, and return <code>false</code> if every element is distinct.</p>
        `,
        examples: [
            {
                input: 'nums = [1,2,3,1]',
                output: 'true',
                explanation: 'The element 1 occurs at indices 0 and 3.'
            },
            {
                input: 'nums = [1,2,3,4]',
                output: 'false',
                explanation: 'All elements are distinct.'
            },
            {
                input: 'nums = [1,1,1,3,3,4,3,2,4,2]',
                output: 'true',
                explanation: null
            }
        ],
        constraints: [
            '1 <= nums.length <= 10<sup>5</sup>',
            '-10<sup>9</sup> <= nums[i] <= 10<sup>9</sup>'
        ],
        starterCode: {
            python: `def containsDuplicate(nums: list[int]) -> bool:
    # Write your solution here
    pass`,
            javascript: `function containsDuplicate(nums) {
    // Write your solution here

}`
        },
        testCases: [
            { input: { nums: [1, 2, 3, 1] }, expected: true },
            { input: { nums: [1, 2, 3, 4] }, expected: false },
            { input: { nums: [1, 1, 1, 3, 3, 4, 3, 2, 4, 2] }, expected: true }
        ],
        testRunner: {
            python: `
def run_tests():
    test_cases = [
        ([1, 2, 3, 1], True),
        ([1, 2, 3, 4], False),
        ([1, 1, 1, 3, 3, 4, 3, 2, 4, 2], True),
    ]
    results = []
    for i, (nums, expected) in enumerate(test_cases):
        try:
            result = containsDuplicate(nums.copy())
            passed = result == expected
            results.append({
                'case': i + 1,
                'passed': passed,
                'input': f'nums = {nums}',
                'expected': expected,
                'actual': result
            })
        except Exception as e:
            results.append({
                'case': i + 1,
                'passed': False,
                'input': f'nums = {nums}',
                'expected': expected,
                'actual': f'Error: {str(e)}'
            })
    return results

import json
print(json.dumps(run_tests()))
`,
            javascript: `
function runTests() {
    const testCases = [
        { input: { nums: [1, 2, 3, 1] }, expected: true },
        { input: { nums: [1, 2, 3, 4] }, expected: false },
        { input: { nums: [1, 1, 1, 3, 3, 4, 3, 2, 4, 2] }, expected: true },
    ];
    const results = [];
    for (let i = 0; i < testCases.length; i++) {
        const { input, expected } = testCases[i];
        try {
            const result = containsDuplicate([...input.nums]);
            const passed = result === expected;
            results.push({
                case: i + 1,
                passed,
                input: \`nums = [\${input.nums}]\`,
                expected,
                actual: result
            });
        } catch (e) {
            results.push({
                case: i + 1,
                passed: false,
                input: \`nums = [\${input.nums}]\`,
                expected,
                actual: \`Error: \${e.message}\`
            });
        }
    }
    return results;
}
JSON.stringify(runTests());
`
        },
        solution: {
            python: `def containsDuplicate(nums: list[int]) -> bool:
    """
    Time: O(n), Space: O(n)
    Use a set to track seen numbers
    """
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return False`,
            javascript: `function containsDuplicate(nums) {
    // Time: O(n), Space: O(n)
    const seen = new Set();
    for (const num of nums) {
        if (seen.has(num)) return true;
        seen.add(num);
    }
    return false;
}`
        }
    },

    'valid-anagram': {
        title: 'Valid Anagram',
        difficulty: 'easy',
        description: `
            <p>Given two strings <code>s</code> and <code>t</code>, return <code>true</code> if <code>t</code> is an anagram of <code>s</code>, and <code>false</code> otherwise.</p>
            <p>An <strong>Anagram</strong> is a word or phrase formed by rearranging the letters of a different word or phrase, typically using all the original letters exactly once.</p>
        `,
        examples: [
            {
                input: 's = "anagram", t = "nagaram"',
                output: 'true',
                explanation: null
            },
            {
                input: 's = "rat", t = "car"',
                output: 'false',
                explanation: null
            }
        ],
        constraints: [
            '1 <= s.length, t.length <= 5 * 10<sup>4</sup>',
            's and t consist of lowercase English letters.'
        ],
        starterCode: {
            python: `def isAnagram(s: str, t: str) -> bool:
    # Write your solution here
    pass`,
            javascript: `function isAnagram(s, t) {
    // Write your solution here

}`
        },
        testCases: [
            { input: { s: 'anagram', t: 'nagaram' }, expected: true },
            { input: { s: 'rat', t: 'car' }, expected: false }
        ],
        testRunner: {
            python: `
def run_tests():
    test_cases = [
        (('anagram', 'nagaram'), True),
        (('rat', 'car'), False),
    ]
    results = []
    for i, (inputs, expected) in enumerate(test_cases):
        s, t = inputs
        try:
            result = isAnagram(s, t)
            passed = result == expected
            results.append({
                'case': i + 1,
                'passed': passed,
                'input': f's = "{s}", t = "{t}"',
                'expected': expected,
                'actual': result
            })
        except Exception as e:
            results.append({
                'case': i + 1,
                'passed': False,
                'input': f's = "{s}", t = "{t}"',
                'expected': expected,
                'actual': f'Error: {str(e)}'
            })
    return results

import json
print(json.dumps(run_tests()))
`,
            javascript: `
function runTests() {
    const testCases = [
        { input: { s: 'anagram', t: 'nagaram' }, expected: true },
        { input: { s: 'rat', t: 'car' }, expected: false },
    ];
    const results = [];
    for (let i = 0; i < testCases.length; i++) {
        const { input, expected } = testCases[i];
        try {
            const result = isAnagram(input.s, input.t);
            const passed = result === expected;
            results.push({
                case: i + 1,
                passed,
                input: \`s = "\${input.s}", t = "\${input.t}"\`,
                expected,
                actual: result
            });
        } catch (e) {
            results.push({
                case: i + 1,
                passed: false,
                input: \`s = "\${input.s}", t = "\${input.t}"\`,
                expected,
                actual: \`Error: \${e.message}\`
            });
        }
    }
    return results;
}
JSON.stringify(runTests());
`
        },
        solution: {
            python: `def isAnagram(s: str, t: str) -> bool:
    """
    Time: O(n), Space: O(1) - fixed 26 chars
    Count character frequencies
    """
    if len(s) != len(t):
        return False
    count = {}
    for c in s:
        count[c] = count.get(c, 0) + 1
    for c in t:
        count[c] = count.get(c, 0) - 1
        if count[c] < 0:
            return False
    return True`,
            javascript: `function isAnagram(s, t) {
    // Time: O(n), Space: O(1)
    if (s.length !== t.length) return false;
    const count = {};
    for (const c of s) {
        count[c] = (count[c] || 0) + 1;
    }
    for (const c of t) {
        count[c] = (count[c] || 0) - 1;
        if (count[c] < 0) return false;
    }
    return true;
}`
        }
    }
};

// Export for use
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PROBLEM_DETAILS;
}

