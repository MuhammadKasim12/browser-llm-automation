// DSA Hub - NeetCode Style JavaScript

// Solutions data
const solutions = {
    'contains-duplicate': {
        python: `def containsDuplicate(nums):
    """
    Time: O(n), Space: O(n)
    Use a set to track seen numbers
    """
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return False

# Test cases
print(containsDuplicate([1,2,3,1]))  # True
print(containsDuplicate([1,2,3,4]))  # False`,
        java: `public boolean containsDuplicate(int[] nums) {
    // Time: O(n), Space: O(n)
    Set<Integer> seen = new HashSet<>();
    for (int num : nums) {
        if (seen.contains(num)) return true;
        seen.add(num);
    }
    return false;
}

// Test: [1,2,3,1] -> true
// Test: [1,2,3,4] -> false`
    },
    'two-sum': {
        python: `def twoSum(nums, target):
    """
    Time: O(n), Space: O(n)
    Use hashmap to store complement
    """
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []

# Test cases
print(twoSum([2,7,11,15], 9))  # [0, 1]
print(twoSum([3,2,4], 6))      # [1, 2]`,
        java: `public int[] twoSum(int[] nums, int target) {
    // Time: O(n), Space: O(n)
    Map<Integer, Integer> map = new HashMap<>();
    for (int i = 0; i < nums.length; i++) {
        int complement = target - nums[i];
        if (map.containsKey(complement)) {
            return new int[]{map.get(complement), i};
        }
        map.put(nums[i], i);
    }
    return new int[]{};
}`
    },
    'valid-anagram': {
        python: `def isAnagram(s, t):
    """
    Time: O(n), Space: O(1) - 26 letters
    Count character frequencies
    """
    if len(s) != len(t):
        return False
    count = {}
    for c in s:
        count[c] = count.get(c, 0) + 1
    for c in t:
        if c not in count or count[c] == 0:
            return False
        count[c] -= 1
    return True

# Test cases
print(isAnagram("anagram", "nagaram"))  # True
print(isAnagram("rat", "car"))          # False`,
        java: `public boolean isAnagram(String s, String t) {
    if (s.length() != t.length()) return false;
    int[] count = new int[26];
    for (char c : s.toCharArray()) count[c - 'a']++;
    for (char c : t.toCharArray()) {
        if (--count[c - 'a'] < 0) return false;
    }
    return true;
}`
    },
    'binary-search': {
        python: `def binarySearch(nums, target):
    """
    Time: O(log n), Space: O(1)
    Classic binary search
    """
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1

# Test cases
print(binarySearch([1,2,3,4,5,6], 4))  # 3
print(binarySearch([1,2,3,4,5,6], 7))  # -1`,
        java: `public int binarySearch(int[] nums, int target) {
    // Time: O(log n), Space: O(1)
    int left = 0, right = nums.length - 1;
    while (left <= right) {
        int mid = left + (right - left) / 2;
        if (nums[mid] == target) return mid;
        else if (nums[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    return -1;
}`
    },
    'search-rotated': {
        python: `def search(nums, target):
    """
    Time: O(log n), Space: O(1)
    Modified binary search for rotated array
    """
    left, right = 0, len(nums) - 1
    while left <= right:
        mid = (left + right) // 2
        if nums[mid] == target:
            return mid
        # Left half is sorted
        if nums[left] <= nums[mid]:
            if nums[left] <= target < nums[mid]:
                right = mid - 1
            else:
                left = mid + 1
        # Right half is sorted
        else:
            if nums[mid] < target <= nums[right]:
                left = mid + 1
            else:
                right = mid - 1
    return -1

# Test: [4,5,6,7,0,1,2], target=0 -> 4`,
        java: `public int search(int[] nums, int target) {
    int left = 0, right = nums.length - 1;
    while (left <= right) {
        int mid = (left + right) / 2;
        if (nums[mid] == target) return mid;
        if (nums[left] <= nums[mid]) {
            if (nums[left] <= target && target < nums[mid])
                right = mid - 1;
            else left = mid + 1;
        } else {
            if (nums[mid] < target && target <= nums[right])
                left = mid + 1;
            else right = mid - 1;
        }
    }
    return -1;
}`
    },
    'missing-number': {
        python: `def missingNumber(nums):
    """
    Time: O(n), Space: O(1)
    XOR all indices and numbers
    """
    n = len(nums)
    result = n
    for i in range(n):
        result ^= i ^ nums[i]
    return result

# Test: [3,0,1] -> 2
# Test: [0,1] -> 2`,
        java: `public int missingNumber(int[] nums) {
    // Time: O(n), Space: O(1)
    int result = nums.length;
    for (int i = 0; i < nums.length; i++) {
        result ^= i ^ nums[i];
    }
    return result;
}`
    },
    'sum-of-two': {
        python: `def getSum(a, b):
    """
    Time: O(1), Space: O(1)
    Use bit manipulation - XOR for sum, AND for carry
    """
    MASK = 0xFFFFFFFF
    MAX = 0x7FFFFFFF
    while b != 0:
        carry = (a & b) << 1
        a = (a ^ b) & MASK
        b = carry & MASK
    return a if a <= MAX else ~(a ^ MASK)

# Test: getSum(1, 2) -> 3
# Test: getSum(-1, 1) -> 0`,
        java: `public int getSum(int a, int b) {
    // Time: O(1), Space: O(1)
    while (b != 0) {
        int carry = (a & b) << 1;
        a = a ^ b;
        b = carry;
    }
    return a;
}`
    },
    'number-of-1-bits': {
        python: `def hammingWeight(n):
    """
    Time: O(1), Space: O(1)
    Brian Kernighan's algorithm
    """
    count = 0
    while n:
        n &= n - 1  # Remove rightmost 1-bit
        count += 1
    return count

# Test: hammingWeight(11) -> 3  (1011 in binary)
# Test: hammingWeight(128) -> 1`,
        java: `public int hammingWeight(int n) {
    // Brian Kernighan's algorithm
    int count = 0;
    while (n != 0) {
        n &= (n - 1);
        count++;
    }
    return count;
}`
    },
    'counting-bits': {
        python: `def countBits(n):
    """
    Time: O(n), Space: O(n)
    DP: dp[i] = dp[i >> 1] + (i & 1)
    """
    dp = [0] * (n + 1)
    for i in range(1, n + 1):
        dp[i] = dp[i >> 1] + (i & 1)
    return dp

# Test: countBits(5) -> [0,1,1,2,1,2]`,
        java: `public int[] countBits(int n) {
    // Time: O(n), Space: O(n)
    int[] dp = new int[n + 1];
    for (int i = 1; i <= n; i++) {
        dp[i] = dp[i >> 1] + (i & 1);
    }
    return dp;
}`
    },
    'reverse-bits': {
        python: `def reverseBits(n):
    """
    Time: O(1), Space: O(1)
    Reverse 32 bits one by one
    """
    result = 0
    for i in range(32):
        result = (result << 1) | (n & 1)
        n >>= 1
    return result

# Test: reverseBits(43261596) -> 964176192`,
        java: `public int reverseBits(int n) {
    int result = 0;
    for (int i = 0; i < 32; i++) {
        result = (result << 1) | (n & 1);
        n >>= 1;
    }
    return result;
}`
    },
    'merge-sort': {
        python: `def mergeSort(arr):
    """
    Time: O(n log n), Space: O(n)
    Divide and conquer sorting
    """
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    left = mergeSort(arr[:mid])
    right = mergeSort(arr[mid:])
    return merge(left, right)

def merge(left, right):
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

# Test: mergeSort([5,2,8,1,9]) -> [1,2,5,8,9]`,
        java: `public void mergeSort(int[] arr, int left, int right) {
    if (left < right) {
        int mid = (left + right) / 2;
        mergeSort(arr, left, mid);
        mergeSort(arr, mid + 1, right);
        merge(arr, left, mid, right);
    }
}

private void merge(int[] arr, int l, int m, int r) {
    int[] temp = new int[r - l + 1];
    int i = l, j = m + 1, k = 0;
    while (i <= m && j <= r) {
        temp[k++] = arr[i] <= arr[j] ? arr[i++] : arr[j++];
    }
    while (i <= m) temp[k++] = arr[i++];
    while (j <= r) temp[k++] = arr[j++];
    System.arraycopy(temp, 0, arr, l, temp.length);
}`
    },
    'reverse-integer': {
        python: `def reverse(x):
    """
    Time: O(log x), Space: O(1)
    Handle overflow for 32-bit integer
    """
    INT_MAX = 2**31 - 1
    INT_MIN = -2**31
    sign = 1 if x >= 0 else -1
    x = abs(x)
    result = 0
    while x:
        result = result * 10 + x % 10
        x //= 10
    result *= sign
    return result if INT_MIN <= result <= INT_MAX else 0

# Test: reverse(123) -> 321
# Test: reverse(-123) -> -321`,
        java: `public int reverse(int x) {
    int result = 0;
    while (x != 0) {
        int digit = x % 10;
        x /= 10;
        if (result > Integer.MAX_VALUE/10 ||
            result < Integer.MIN_VALUE/10) return 0;
        result = result * 10 + digit;
    }
    return result;
}`
    }
};

// DOM Elements
const problemModal = document.getElementById('problem-modal');
const modalProblemTitle = document.getElementById('modal-problem-title');
const modalDifficulty = document.getElementById('modal-difficulty');
const modalFrequency = document.getElementById('modal-frequency');
const modalCompanies = document.getElementById('modal-companies');
const modalPatterns = document.getElementById('modal-patterns');
const modalPrereqsSection = document.getElementById('modal-prereqs-section');
const modalPrereqsList = document.getElementById('modal-prereqs-list');
const modalHintSection = document.getElementById('modal-hint-section');
const modalHintText = document.getElementById('modal-hint-text');
const modalClose = document.getElementById('problem-modal-close');
const solutionCode = document.getElementById('solution-code');
const copyBtn = document.getElementById('copy-btn');
const leetcodeLink = document.getElementById('leetcode-link');
const markCompleteBtn = document.getElementById('mark-complete-btn');
const themeToggle = document.getElementById('theme-toggle');
const totalProgressEl = document.getElementById('total-progress');
const totalProgressBar = document.getElementById('total-progress-bar');

let currentProblem = null;
let currentProblemData = null;
let currentLang = localStorage.getItem('dsa-preferred-lang') || 'python';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadProgress();
    loadPreferredLanguage();
    initAccordions();
    initCheckboxes();
    initSolutionButtons();
    initModal();
    initTheme();
    updateAllProgress();
});

// Load and apply preferred language
function loadPreferredLanguage() {
    const savedLang = localStorage.getItem('dsa-preferred-lang');
    if (savedLang) {
        currentLang = savedLang;
        // Update tab UI to reflect saved preference
        document.querySelectorAll('.code-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.lang === savedLang);
        });
    }
}

// Save preferred language
function savePreferredLanguage(lang) {
    localStorage.setItem('dsa-preferred-lang', lang);
}

// Accordion functionality
function initAccordions() {
    document.querySelectorAll('.category-header').forEach(header => {
        header.addEventListener('click', () => {
            const category = header.closest('.category');
            category.classList.toggle('open');
        });
    });
    // Open first category by default
    document.querySelector('.category')?.classList.add('open');
}

// Checkbox persistence
function initCheckboxes() {
    document.querySelectorAll('.problem-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', (e) => {
            const problemId = e.target.dataset.id;
            const completed = e.target.checked;
            saveProgress(problemId, completed);
            updateRowStyle(e.target);
            updateAllProgress();
        });
    });
}

function loadProgress() {
    const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');
    document.querySelectorAll('.problem-checkbox').forEach(checkbox => {
        const problemId = checkbox.dataset.id;
        if (progress[problemId]) {
            checkbox.checked = true;
            updateRowStyle(checkbox);
        }
    });
}

function saveProgress(problemId, completed) {
    const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');
    progress[problemId] = completed;
    localStorage.setItem('dsa-progress', JSON.stringify(progress));
}

function updateRowStyle(checkbox) {
    const row = checkbox.closest('tr');
    if (checkbox.checked) {
        row.classList.add('completed');
    } else {
        row.classList.remove('completed');
    }
}

function updateAllProgress() {
    let totalCompleted = 0;
    let totalProblems = 0;

    document.querySelectorAll('.category').forEach(category => {
        const checkboxes = category.querySelectorAll('.problem-checkbox');
        const completed = Array.from(checkboxes).filter(cb => cb.checked).length;
        const total = checkboxes.length;

        totalCompleted += completed;
        totalProblems += total;

        // Update category count
        const countEl = category.querySelector('.category-count');
        if (countEl) countEl.textContent = `${completed} / ${total}`;

        // Update mini progress bar
        const progressFill = category.querySelector('.mini-progress-fill');
        if (progressFill) {
            progressFill.style.width = total > 0 ? `${(completed / total) * 100}%` : '0%';
        }
    });

    // Update total progress
    if (totalProgressEl) {
        totalProgressEl.textContent = `${totalCompleted} / ${totalProblems} completed`;
    }
    if (totalProgressBar) {
        totalProgressBar.style.width = totalProblems > 0 ? `${(totalCompleted / totalProblems) * 100}%` : '0%';
    }
}

// Problem Detail Modal
function openProblemDetail(problemId) {
    // Check if problem has detailed data for coding environment
    if (typeof PROBLEM_DETAILS !== 'undefined' && PROBLEM_DETAILS[problemId]) {
        // Navigate to LeetCode-style coding page
        window.location.href = `problem.html?id=${problemId}`;
        return;
    }

    // Fallback to modal for problems without detailed data
    // Find problem in database
    const problem = PROBLEMS_DB.problems.find(p => p.id === problemId);
    if (!problem) return;

    currentProblem = problemId;
    currentProblemData = problem;
    const solution = solutions[problemId];

    // Set title and difficulty
    modalProblemTitle.textContent = `${problem.leetcode}. ${problem.name}`;
    modalDifficulty.textContent = capitalizeFirst(problem.difficulty);
    modalDifficulty.className = `difficulty-badge ${problem.difficulty}`;

    // Set frequency
    modalFrequency.textContent = `${problem.frequency}%`;

    // Set companies
    modalCompanies.innerHTML = problem.companies.map(c =>
        `<span class="company-tag-inline">${capitalizeFirst(c)}</span>`
    ).join(' ');

    // Set patterns
    modalPatterns.innerHTML = problem.patterns.map(p =>
        `<span class="pattern-tag-inline">${p}</span>`
    ).join(' ');

    // Prerequisites
    if (problem.prerequisites && problem.prerequisites.length > 0) {
        modalPrereqsSection.style.display = 'block';
        modalPrereqsList.innerHTML = problem.prerequisites.map(prereqId => {
            const prereq = PROBLEMS_DB.problems.find(p => p.id === prereqId);
            if (!prereq) return '';
            return `<button class="prereq-btn" data-problem="${prereqId}">
                <span class="prereq-num">${prereq.leetcode}.</span>
                <span class="prereq-name">${prereq.name}</span>
                <span class="difficulty-badge ${prereq.difficulty} small">${capitalizeFirst(prereq.difficulty)}</span>
            </button>`;
        }).join('');

        // Add click handlers for prerequisite buttons
        modalPrereqsList.querySelectorAll('.prereq-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                openProblemDetail(btn.dataset.problem);
            });
        });
    } else {
        modalPrereqsSection.style.display = 'none';
    }

    // Hint
    if (problem.hint) {
        modalHintSection.style.display = 'block';
        modalHintText.textContent = problem.hint;
    } else {
        modalHintSection.style.display = 'none';
    }

    // Solution code
    if (solution) {
        showCode(solution[currentLang]);
    } else {
        solutionCode.textContent = '// Solution coming soon...';
        solutionCode.className = `language-${currentLang}`;
    }

    // LeetCode link
    leetcodeLink.href = `https://leetcode.com/problems/${problemId}`;

    // Mark complete button state
    const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');
    updateMarkCompleteBtn(progress[problemId]);

    // Show modal
    problemModal.classList.add('open');
}

function updateMarkCompleteBtn(isComplete) {
    if (isComplete) {
        markCompleteBtn.classList.add('completed');
        markCompleteBtn.innerHTML = '<i class="fas fa-check-circle"></i> <span>Completed</span>';
    } else {
        markCompleteBtn.classList.remove('completed');
        markCompleteBtn.innerHTML = '<i class="fas fa-check"></i> <span>Mark Complete</span>';
    }
}

function showCode(code) {
    solutionCode.textContent = code;
    solutionCode.className = `language-${currentLang}`;
    Prism.highlightElement(solutionCode);
}

function initModal() {
    // Close modal
    modalClose?.addEventListener('click', () => problemModal.classList.remove('open'));
    problemModal?.addEventListener('click', (e) => {
        if (e.target === problemModal) problemModal.classList.remove('open');
    });

    // Escape key closes modal
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && problemModal.classList.contains('open')) {
            problemModal.classList.remove('open');
        }
    });

    // Tab switching
    document.querySelectorAll('.code-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.code-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentLang = tab.dataset.lang;
            savePreferredLanguage(currentLang);
            if (currentProblem && solutions[currentProblem]) {
                showCode(solutions[currentProblem][currentLang]);
            }
        });
    });

    // Copy button
    copyBtn?.addEventListener('click', () => {
        navigator.clipboard.writeText(solutionCode.textContent);
        copyBtn.innerHTML = '<i class="fas fa-check"></i> Copied!';
        setTimeout(() => {
            copyBtn.innerHTML = '<i class="fas fa-copy"></i> Copy';
        }, 2000);
    });

    // Mark complete button
    markCompleteBtn?.addEventListener('click', () => {
        if (!currentProblem) return;
        const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');
        const newState = !progress[currentProblem];
        saveProgress(currentProblem, newState);
        updateMarkCompleteBtn(newState);

        // Update the explorer view
        const checkbox = document.querySelector(`.explorer-checkbox[data-id="${currentProblem}"]`);
        if (checkbox) {
            checkbox.checked = newState;
            const row = checkbox.closest('tr, .problem-card');
            if (row) {
                if (newState) row.classList.add('completed');
                else row.classList.remove('completed');
            }
        }
        updateAllProgress();
    });
}

// Theme toggle
function initTheme() {
    const savedTheme = localStorage.getItem('dsa-theme');
    if (savedTheme === 'light') {
        document.documentElement.classList.remove('dark-theme');
        document.documentElement.classList.add('light-theme');
        updateThemeIcon(true);
    }

    themeToggle?.addEventListener('click', () => {
        const isLight = document.documentElement.classList.contains('light-theme');
        document.documentElement.classList.toggle('light-theme');
        document.documentElement.classList.toggle('dark-theme');
        localStorage.setItem('dsa-theme', isLight ? 'dark' : 'light');
        updateThemeIcon(!isLight);
    });
}

function updateThemeIcon(isLight) {
    const icon = themeToggle?.querySelector('i');
    if (icon) {
        icon.className = isLight ? 'fas fa-moon' : 'fas fa-sun';
    }
}

// ============ PROBLEMS EXPLORER ============

// State for explorer
let explorerState = {
    view: 'table',
    groupBy: 'category',
    sortBy: 'frequency-desc',
    difficulty: 'all',
    company: 'all',
    status: 'all',
    search: ''
};

// Category display names
const categoryNames = {
    'arrays-hashing': 'Arrays & Hashing',
    'two-pointers': 'Two Pointers',
    'sliding-window': 'Sliding Window',
    'stack': 'Stack',
    'binary-search': 'Binary Search',
    'linked-list': 'Linked List',
    'trees': 'Trees',
    'tries': 'Tries',
    'heap': 'Heap / Priority Queue',
    'backtracking': 'Backtracking',
    'graphs': 'Graphs',
    'dynamic-programming': 'Dynamic Programming',
    'greedy': 'Greedy',
    'intervals': 'Intervals',
    'math': 'Math & Geometry',
    'bit-manipulation': 'Bit Manipulation'
};

// Company logos/colors
const companyColors = {
    'google': '#4285f4',
    'amazon': '#ff9900',
    'meta': '#0668e1',
    'apple': '#555555',
    'microsoft': '#00a4ef',
    'bloomberg': '#2800d7',
    'uber': '#000000',
    'linkedin': '#0077b5',
    'twitter': '#1da1f2',
    'netflix': '#e50914',
    'stripe': '#635bff',
    'airbnb': '#ff5a5f',
    'adobe': '#ff0000'
};

// Initialize explorer on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    if (typeof PROBLEMS_DB !== 'undefined') {
        initExplorer();
    }
});

function initExplorer() {
    initViewToggle();
    initGroupBySelector();
    initSortSelector();
    initFilters();
    initSearch();
    populateCompanyFilters();
    populateCompaniesSection();
    renderProblems();
}

function initViewToggle() {
    document.querySelectorAll('.view-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.view-toggle').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            explorerState.view = btn.dataset.view;
            renderProblems();
        });
    });
}

function initGroupBySelector() {
    const selector = document.getElementById('group-select');
    selector?.addEventListener('change', (e) => {
        explorerState.groupBy = e.target.value;
        renderProblems();
    });
}

function initSortSelector() {
    const selector = document.getElementById('sort-select');
    selector?.addEventListener('change', (e) => {
        explorerState.sortBy = e.target.value;
        renderProblems();
    });
}

function initFilters() {
    // Difficulty filter
    document.querySelectorAll('#difficulty-filters .filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('#difficulty-filters .filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            explorerState.difficulty = chip.dataset.difficulty;
            renderProblems();
        });
    });

    // Status filter
    document.querySelectorAll('#status-filters .filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('#status-filters .filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            explorerState.status = chip.dataset.status;
            renderProblems();
        });
    });
}

function initSearch() {
    const searchInput = document.getElementById('problem-search');
    let debounceTimer;
    searchInput?.addEventListener('input', (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            explorerState.search = e.target.value.toLowerCase();
            renderProblems();
        }, 200);
    });
}

function populateCompanyFilters() {
    const container = document.getElementById('company-filters');
    if (!container) return;

    const companies = new Set();
    PROBLEMS_DB.problems.forEach(p => p.companies.forEach(c => companies.add(c)));

    const topCompanies = ['google', 'amazon', 'meta', 'apple', 'microsoft', 'bloomberg'];
    topCompanies.forEach(company => {
        if (companies.has(company)) {
            const btn = document.createElement('button');
            btn.className = 'filter-chip company-chip';
            btn.dataset.company = company;
            btn.innerHTML = capitalizeFirst(company);
            btn.addEventListener('click', () => {
                document.querySelectorAll('#company-filters .filter-chip').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                explorerState.company = company;
                renderProblems();
            });
            container.appendChild(btn);
        }
    });
}

function populateCompaniesSection() {
    const container = document.getElementById('companies-grid');
    if (!container) return;

    const companyCounts = {};
    PROBLEMS_DB.problems.forEach(p => {
        p.companies.forEach(c => {
            companyCounts[c] = (companyCounts[c] || 0) + 1;
        });
    });

    const sorted = Object.entries(companyCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 12);

    sorted.forEach(([company, count]) => {
        const card = document.createElement('div');
        card.className = 'company-card';
        card.style.borderColor = companyColors[company] || '#666';
        card.innerHTML = `
            <div class="company-logo" style="background: ${companyColors[company] || '#666'}">
                ${company.charAt(0).toUpperCase()}
            </div>
            <div class="company-info">
                <h3>${capitalizeFirst(company)}</h3>
                <span class="problem-count">${count} problems</span>
            </div>
        `;
        card.addEventListener('click', () => {
            document.querySelectorAll('#company-filters .filter-chip').forEach(c => c.classList.remove('active'));
            document.querySelector(`[data-company="${company}"]`)?.classList.add('active');
            explorerState.company = company;
            renderProblems();
            document.getElementById('explorer')?.scrollIntoView({ behavior: 'smooth' });
        });
        container.appendChild(card);
    });
}

function getFilteredProblems() {
    const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');

    return PROBLEMS_DB.problems.filter(p => {
        // Difficulty filter
        if (explorerState.difficulty !== 'all' && p.difficulty !== explorerState.difficulty) return false;

        // Company filter
        if (explorerState.company !== 'all' && !p.companies.includes(explorerState.company)) return false;

        // Status filter
        if (explorerState.status === 'done' && !progress[p.id]) return false;
        if (explorerState.status === 'todo' && progress[p.id]) return false;

        // Search filter
        if (explorerState.search) {
            const searchLower = explorerState.search;
            if (!p.name.toLowerCase().includes(searchLower) &&
                !p.id.toLowerCase().includes(searchLower) &&
                !p.category.toLowerCase().includes(searchLower) &&
                !p.patterns.some(pat => pat.toLowerCase().includes(searchLower))) {
                return false;
            }
        }

        return true;
    });
}

function sortProblems(problems) {
    const [field, direction] = explorerState.sortBy.split('-');
    const multiplier = direction === 'desc' ? -1 : 1;

    return [...problems].sort((a, b) => {
        switch (field) {
            case 'frequency':
                return (a.frequency - b.frequency) * multiplier;
            case 'difficulty':
                const diffOrder = { easy: 1, medium: 2, hard: 3 };
                return (diffOrder[a.difficulty] - diffOrder[b.difficulty]) * multiplier;
            case 'leetcode':
                return (a.leetcode - b.leetcode) * multiplier;
            case 'name':
                return a.name.localeCompare(b.name) * multiplier;
            default:
                return 0;
        }
    });
}

function groupProblems(problems) {
    const grouped = {};

    problems.forEach(p => {
        let key;
        switch (explorerState.groupBy) {
            case 'category':
                key = p.category;
                break;
            case 'difficulty':
                key = p.difficulty;
                break;
            case 'pattern':
                key = p.patterns[0] || 'other';
                break;
            case 'none':
                key = 'all';
                break;
            default:
                key = p.category;
        }

        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(p);
    });

    return grouped;
}

function renderProblems() {
    const container = document.getElementById('problems-display');
    if (!container) return;

    const filtered = getFilteredProblems();
    const sorted = sortProblems(filtered);
    const grouped = groupProblems(sorted);

    // Update results count
    const countEl = document.getElementById('results-count');
    if (countEl) countEl.textContent = `${filtered.length} problems`;

    container.innerHTML = '';

    if (explorerState.view === 'table') {
        renderTableView(container, grouped);
    } else {
        renderCardView(container, grouped);
    }
}

function renderTableView(container, grouped) {
    const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');

    Object.entries(grouped).forEach(([group, problems]) => {
        const section = document.createElement('div');
        section.className = 'problem-group';

        const groupName = getGroupDisplayName(group);
        const completed = problems.filter(p => progress[p.id]).length;

        section.innerHTML = `
            <div class="group-header">
                <h3>${groupName}</h3>
                <span class="group-count">${completed}/${problems.length}</span>
            </div>
        `;

        const table = document.createElement('table');
        table.className = 'problems-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th class="col-status">Status</th>
                    <th class="col-problem">Problem</th>
                    <th class="col-difficulty">Difficulty</th>
                    <th class="col-frequency">Frequency</th>
                    <th class="col-companies">Companies</th>
                    <th class="col-actions">Actions</th>
                </tr>
            </thead>
            <tbody></tbody>
        `;

        const tbody = table.querySelector('tbody');
        problems.forEach(p => {
            const row = createTableRow(p, progress);
            tbody.appendChild(row);
        });

        section.appendChild(table);
        container.appendChild(section);
    });
}

function createTableRow(problem, progress) {
    const row = document.createElement('tr');
    row.dataset.problem = problem.id;
    if (progress[problem.id]) row.classList.add('completed');

    const prereqsHtml = problem.prerequisites?.length > 0
        ? `<div class="prereqs-indicator" title="Prerequisites: ${problem.prerequisites.join(', ')}">
             <i class="fas fa-link"></i>
           </div>`
        : '';

    const hintHtml = problem.hint
        ? `<span class="hint-trigger" title="${escapeHtml(problem.hint)}">
             <i class="fas fa-lightbulb"></i>
           </span>`
        : '';

    row.innerHTML = `
        <td class="col-status">
            <input type="checkbox" class="explorer-checkbox" data-id="${problem.id}"
                   ${progress[problem.id] ? 'checked' : ''}>
        </td>
        <td class="col-problem">
            <div class="problem-info">
                ${prereqsHtml}
                <button class="problem-link-btn" data-problem="${problem.id}">
                    <span class="leetcode-num">${problem.leetcode}.</span>
                    <span class="problem-name">${problem.name}</span>
                </button>
                ${hintHtml}
                ${problem.premium ? '<span class="premium-badge"><i class="fas fa-lock"></i></span>' : ''}
            </div>
        </td>
        <td class="col-difficulty">
            <span class="difficulty-badge ${problem.difficulty}">${capitalizeFirst(problem.difficulty)}</span>
        </td>
        <td class="col-frequency">
            <div class="frequency-bar-container">
                <div class="frequency-bar" style="width: ${problem.frequency}%"></div>
                <span class="frequency-text">${problem.frequency}%</span>
            </div>
        </td>
        <td class="col-companies">
            <div class="companies-list">
                ${problem.companies.slice(0, 3).map(c =>
                    `<span class="company-tag" style="background: ${companyColors[c] || '#666'}">${c.charAt(0).toUpperCase()}</span>`
                ).join('')}
                ${problem.companies.length > 3 ? `<span class="more-companies">+${problem.companies.length - 3}</span>` : ''}
            </div>
        </td>
        <td class="col-actions">
            <button class="action-btn solution-btn" data-problem="${problem.id}" title="View Solution">
                <i class="fas fa-code"></i>
            </button>
        </td>
    `;

    // Add checkbox listener
    row.querySelector('.explorer-checkbox')?.addEventListener('change', (e) => {
        handleCheckboxChange(e, problem.id, row);
    });

    // Add problem link click listener
    row.querySelector('.problem-link-btn')?.addEventListener('click', () => {
        openProblemDetail(problem.id);
    });

    // Add solution button listener
    row.querySelector('.solution-btn')?.addEventListener('click', () => {
        openProblemDetail(problem.id);
    });

    return row;
}

function renderCardView(container, grouped) {
    const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');

    Object.entries(grouped).forEach(([group, problems]) => {
        const section = document.createElement('div');
        section.className = 'problem-group';

        const groupName = getGroupDisplayName(group);

        section.innerHTML = `
            <div class="group-header">
                <h3>${groupName}</h3>
                <span class="group-count">${problems.length} problems</span>
            </div>
            <div class="cards-grid"></div>
        `;

        const grid = section.querySelector('.cards-grid');
        problems.forEach(p => {
            const card = createProblemCard(p, progress);
            grid.appendChild(card);
        });

        container.appendChild(section);
    });
}

function createProblemCard(problem, progress) {
    const card = document.createElement('div');
    card.className = `problem-card ${problem.difficulty}`;
    if (progress[problem.id]) card.classList.add('completed');

    const prereqsHtml = problem.prerequisites?.length > 0
        ? `<div class="card-prereqs">
             <i class="fas fa-link"></i> Solve first: ${problem.prerequisites.slice(0, 2).join(', ')}
           </div>`
        : '';

    card.innerHTML = `
        <div class="card-header">
            <input type="checkbox" class="explorer-checkbox" data-id="${problem.id}"
                   ${progress[problem.id] ? 'checked' : ''}>
            <span class="difficulty-badge ${problem.difficulty}">${capitalizeFirst(problem.difficulty)}</span>
            ${problem.premium ? '<span class="premium-badge"><i class="fas fa-lock"></i></span>' : ''}
        </div>
        <div class="card-body">
            <button class="problem-title-btn" data-problem="${problem.id}">
                ${problem.leetcode}. ${problem.name}
            </button>
            <div class="frequency-bar-container">
                <div class="frequency-bar" style="width: ${problem.frequency}%"></div>
                <span class="frequency-text">${problem.frequency}% asked</span>
            </div>
            ${prereqsHtml}
            ${problem.hint ? `<p class="card-hint"><i class="fas fa-lightbulb"></i> ${problem.hint}</p>` : ''}
        </div>
        <div class="card-footer">
            <div class="patterns">
                ${problem.patterns.slice(0, 2).map(p => `<span class="pattern-tag">${p}</span>`).join('')}
            </div>
            <button class="action-btn solution-btn" data-problem="${problem.id}">
                <i class="fas fa-code"></i>
            </button>
        </div>
    `;

    // Add checkbox listener
    card.querySelector('.explorer-checkbox')?.addEventListener('change', (e) => {
        handleCheckboxChange(e, problem.id, card);
    });

    // Add problem title click listener
    card.querySelector('.problem-title-btn')?.addEventListener('click', () => {
        openProblemDetail(problem.id);
    });

    // Add solution button listener
    card.querySelector('.solution-btn')?.addEventListener('click', () => {
        openProblemDetail(problem.id);
    });

    return card;
}

function handleCheckboxChange(e, problemId, element) {
    const completed = e.target.checked;
    saveProgress(problemId, completed);

    if (completed) {
        element.classList.add('completed');
    } else {
        element.classList.remove('completed');
    }

    updateAllProgress();

    // Re-render if filtering by status
    if (explorerState.status !== 'all') {
        renderProblems();
    }
}

function getGroupDisplayName(group) {
    if (categoryNames[group]) return categoryNames[group];
    if (group === 'easy' || group === 'medium' || group === 'hard') {
        return capitalizeFirst(group);
    }
    if (group === 'all') return 'All Problems';
    return group.split('-').map(capitalizeFirst).join(' ');
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

