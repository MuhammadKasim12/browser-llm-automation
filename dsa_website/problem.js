/**
 * DSA Hub - LeetCode-Style Problem Page
 * Handles Monaco Editor, code execution, and test running
 */

// State
let editor = null;
let pyodide = null;
let currentProblem = null;
let currentLanguage = 'python';
let activeTestCase = 0;
let testResults = [];

// DOM Elements
const problemTitleNav = document.getElementById('problem-title-nav');
const problemTitle = document.getElementById('problem-title');
const difficultyBadge = document.getElementById('difficulty-badge');
const frequencyEl = document.getElementById('frequency');
const problemDescription = document.getElementById('problem-description');
const problemExamples = document.getElementById('problem-examples');
const problemConstraints = document.getElementById('problem-constraints');
const problemPatterns = document.getElementById('problem-patterns');
const problemCompanies = document.getElementById('problem-companies');
const languageSelect = document.getElementById('language-select');
const testcaseButtons = document.getElementById('testcase-buttons');
const testcaseInputs = document.getElementById('testcase-inputs');
const resultContent = document.getElementById('result-content');
const runBtn = document.getElementById('run-code');
const submitBtn = document.getElementById('submit-code');
const resetCodeBtn = document.getElementById('reset-code');
const loadingOverlay = document.getElementById('loading-overlay');
const solutionsList = document.getElementById('solutions-list');

// Initialize
document.addEventListener('DOMContentLoaded', init);

async function init() {
    // Get problem ID from URL
    const urlParams = new URLSearchParams(window.location.search);
    const problemId = urlParams.get('id') || 'two-sum';
    
    // Load saved language preference
    currentLanguage = localStorage.getItem('dsa-preferred-language') || 'python';
    languageSelect.value = currentLanguage;
    
    // Initialize Monaco Editor
    await initMonacoEditor();
    
    // Load problem
    loadProblem(problemId);
    
    // Initialize Pyodide in background
    initPyodide();
    
    // Setup event listeners
    setupEventListeners();
    
    // Setup resizer
    setupResizer();
    
    // Apply theme
    applyTheme();
}

// Monaco Editor Setup
async function initMonacoEditor() {
    return new Promise((resolve) => {
        require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.45.0/min/vs' }});
        require(['vs/editor/editor.main'], function() {
            // Define custom theme
            monaco.editor.defineTheme('dsa-dark', {
                base: 'vs-dark',
                inherit: true,
                rules: [],
                colors: {
                    'editor.background': '#1e1e1e',
                }
            });
            
            editor = monaco.editor.create(document.getElementById('editor-container'), {
                value: '# Loading...',
                language: 'python',
                theme: document.body.classList.contains('light-mode') ? 'vs' : 'dsa-dark',
                fontSize: 14,
                fontFamily: "'Monaco', 'Menlo', 'Consolas', monospace",
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                automaticLayout: true,
                tabSize: 4,
                lineNumbers: 'on',
                renderLineHighlight: 'line',
                padding: { top: 10 }
            });
            
            resolve();
        });
    });
}

// Pyodide Setup (Python runtime)
async function initPyodide() {
    try {
        loadingOverlay.classList.add('visible');
        loadingOverlay.querySelector('p').textContent = 'Loading Python runtime...';
        
        // Load Pyodide
        pyodide = await loadPyodide({
            indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.24.1/full/'
        });
        
        loadingOverlay.classList.remove('visible');
        console.log('Pyodide loaded successfully');
    } catch (err) {
        console.error('Failed to load Pyodide:', err);
        loadingOverlay.classList.remove('visible');
    }
}

// Load Problem
function loadProblem(problemId) {
    // Get problem data from both databases
    const problemMeta = PROBLEMS_DB.problems.find(p => p.id === problemId);
    const problemDetails = PROBLEM_DETAILS[problemId];
    
    if (!problemMeta || !problemDetails) {
        problemDescription.innerHTML = '<p class="error">Problem not found</p>';
        return;
    }
    
    currentProblem = { ...problemMeta, ...problemDetails };
    
    // Update UI
    document.title = `${currentProblem.leetcode}. ${currentProblem.title} - DSA Hub`;
    problemTitleNav.textContent = `${currentProblem.leetcode}. ${currentProblem.title}`;
    problemTitle.textContent = `${currentProblem.leetcode}. ${currentProblem.title}`;
    
    // Difficulty
    difficultyBadge.textContent = capitalize(currentProblem.difficulty);
    difficultyBadge.className = `difficulty-badge ${currentProblem.difficulty}`;
    
    // Frequency
    frequencyEl.textContent = currentProblem.frequency;
    
    // Description
    problemDescription.innerHTML = currentProblem.description;
    
    // Examples
    renderExamples();
    
    // Constraints
    renderConstraints();
    
    // Patterns/Tags
    renderPatterns();
    
    // Companies
    renderCompanies();
    
    // Set editor code
    updateEditorLanguage();
    
    // Render test cases
    renderTestCases();
    
    // Render solutions tab
    renderSolutions();
}

function renderExamples() {
    if (!currentProblem.examples) return;

    problemExamples.innerHTML = currentProblem.examples.map((ex, i) => `
        <div class="example-box">
            <h4>Example ${i + 1}:</h4>
            <div class="example-item"><strong>Input:</strong> <code>${ex.input}</code></div>
            <div class="example-item"><strong>Output:</strong> <code>${ex.output}</code></div>
            ${ex.explanation ? `<div class="example-item"><strong>Explanation:</strong> ${ex.explanation}</div>` : ''}
        </div>
    `).join('');
}

function renderConstraints() {
    if (!currentProblem.constraints) return;

    problemConstraints.innerHTML = `
        <h4>Constraints:</h4>
        <ul class="constraints-list">
            ${currentProblem.constraints.map(c => `<li>${c}</li>`).join('')}
        </ul>
    `;
}

function renderPatterns() {
    if (!currentProblem.patterns) return;

    problemPatterns.innerHTML = currentProblem.patterns.map(p =>
        `<span class="tag">${PROBLEMS_DB.patterns[p] || p}</span>`
    ).join('');
}

function renderCompanies() {
    if (!currentProblem.companies) return;

    problemCompanies.innerHTML = currentProblem.companies.map(c => {
        const company = PROBLEMS_DB.companies[c];
        return `<span class="company-tag" style="background: ${company?.color || '#666'}">${company?.name || c}</span>`;
    }).join(' ');
}

function renderTestCases() {
    if (!currentProblem.testCases) return;

    testcaseButtons.innerHTML = currentProblem.testCases.map((_, i) =>
        `<button class="testcase-btn ${i === 0 ? 'active' : ''}" data-index="${i}">Case ${i + 1}</button>`
    ).join('');

    // Add click handlers
    testcaseButtons.querySelectorAll('.testcase-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            activeTestCase = parseInt(btn.dataset.index);
            updateActiveTestCase();
        });
    });

    updateActiveTestCase();
}

function updateActiveTestCase() {
    // Update button states
    testcaseButtons.querySelectorAll('.testcase-btn').forEach((btn, i) => {
        btn.classList.toggle('active', i === activeTestCase);
        if (testResults[i]) {
            btn.classList.toggle('passed', testResults[i].passed);
            btn.classList.toggle('failed', !testResults[i].passed);
        } else {
            btn.classList.remove('passed', 'failed');
        }
    });

    // Show inputs for active test case
    const testCase = currentProblem.testCases[activeTestCase];
    if (!testCase) return;

    testcaseInputs.innerHTML = Object.entries(testCase.input).map(([key, value]) => `
        <div class="input-group">
            <label>${key} =</label>
            <input type="text" value="${JSON.stringify(value)}" data-key="${key}">
        </div>
    `).join('');
}

function renderSolutions() {
    if (!currentProblem.solution) {
        solutionsList.innerHTML = '<p class="empty-state">Solutions coming soon...</p>';
        return;
    }

    solutionsList.innerHTML = `
        <div class="solution-card">
            <h4>Python Solution</h4>
            <pre><code class="language-python">${escapeHtml(currentProblem.solution.python)}</code></pre>
        </div>
        <div class="solution-card">
            <h4>JavaScript Solution</h4>
            <pre><code class="language-javascript">${escapeHtml(currentProblem.solution.javascript)}</code></pre>
        </div>
    `;
}

function updateEditorLanguage() {
    const starterCode = currentProblem.starterCode[currentLanguage] || '// No starter code';

    // Get saved code or use starter
    const savedCode = localStorage.getItem(`dsa-code-${currentProblem.id}-${currentLanguage}`);
    const code = savedCode || starterCode;

    editor.setValue(code);
    monaco.editor.setModelLanguage(editor.getModel(), currentLanguage === 'python' ? 'python' : 'javascript');
}

// Event Listeners
function setupEventListeners() {
    // Language change
    languageSelect.addEventListener('change', (e) => {
        currentLanguage = e.target.value;
        localStorage.setItem('dsa-preferred-language', currentLanguage);
        updateEditorLanguage();
    });

    // Reset code
    resetCodeBtn.addEventListener('click', () => {
        if (confirm('Reset code to starter template?')) {
            localStorage.removeItem(`dsa-code-${currentProblem.id}-${currentLanguage}`);
            editor.setValue(currentProblem.starterCode[currentLanguage]);
        }
    });

    // Run code
    runBtn.addEventListener('click', runCode);

    // Submit code
    submitBtn.addEventListener('click', submitCode);

    // Tab switching
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
        });
    });

    document.querySelectorAll('.bottom-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.bottom-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.bottom-tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
        });
    });

    // Theme toggle
    document.getElementById('theme-toggle')?.addEventListener('click', toggleTheme);

    // Auto-save code
    editor?.onDidChangeModelContent(() => {
        if (currentProblem) {
            localStorage.setItem(`dsa-code-${currentProblem.id}-${currentLanguage}`, editor.getValue());
        }
    });

    // Navigation buttons
    document.getElementById('prev-problem')?.addEventListener('click', navigateProblem(-1));
    document.getElementById('next-problem')?.addEventListener('click', navigateProblem(1));
}

// Code Execution
async function runCode() {
    const code = editor.getValue();
    testResults = [];

    runBtn.disabled = true;
    runBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';

    try {
        if (currentLanguage === 'python') {
            await runPythonCode(code);
        } else {
            runJavaScriptCode(code);
        }
    } catch (err) {
        showError(err.message);
    }

    runBtn.disabled = false;
    runBtn.innerHTML = '<i class="fas fa-play"></i> Run';

    // Switch to result tab
    document.querySelector('.bottom-tab[data-tab="result"]').click();
}

async function runPythonCode(userCode) {
    if (!pyodide) {
        showError('Python runtime is still loading. Please wait...');
        return;
    }

    const testRunner = currentProblem.testRunner.python;
    const fullCode = userCode + '\n' + testRunner;

    try {
        // Capture stdout
        pyodide.runPython(`
import sys
from io import StringIO
sys.stdout = StringIO()
        `);

        pyodide.runPython(fullCode);

        const stdout = pyodide.runPython('sys.stdout.getvalue()');
        const results = JSON.parse(stdout);

        displayResults(results);
    } catch (err) {
        showError(err.message);
    }
}

function runJavaScriptCode(userCode) {
    const testRunner = currentProblem.testRunner.javascript;
    const fullCode = userCode + '\n' + testRunner;

    try {
        const resultStr = eval(fullCode);
        const results = JSON.parse(resultStr);
        displayResults(results);
    } catch (err) {
        showError(err.message);
    }
}

async function submitCode() {
    await runCode();

    // Save submission
    const submissions = JSON.parse(localStorage.getItem('dsa-submissions') || '{}');
    if (!submissions[currentProblem.id]) {
        submissions[currentProblem.id] = [];
    }

    const allPassed = testResults.every(r => r.passed);
    submissions[currentProblem.id].unshift({
        timestamp: Date.now(),
        language: currentLanguage,
        passed: allPassed,
        code: editor.getValue()
    });

    localStorage.setItem('dsa-submissions', JSON.stringify(submissions));

    // Update progress if all passed
    if (allPassed) {
        const progress = JSON.parse(localStorage.getItem('dsa-progress') || '{}');
        progress[currentProblem.id] = true;
        localStorage.setItem('dsa-progress', JSON.stringify(progress));
    }
}

function displayResults(results) {
    testResults = results;
    updateActiveTestCase(); // Update button colors

    const allPassed = results.every(r => r.passed);
    const passedCount = results.filter(r => r.passed).length;

    resultContent.innerHTML = `
        <div class="result-summary ${allPassed ? 'accepted' : 'wrong'}">
            <i class="fas ${allPassed ? 'fa-check-circle' : 'fa-times-circle'}"></i>
            <div>
                <h3>${allPassed ? 'Accepted' : 'Wrong Answer'}</h3>
                <p>${passedCount}/${results.length} test cases passed</p>
            </div>
        </div>
        <div class="result-details">
            ${results.map(r => `
                <div class="result-case ${r.passed ? 'passed' : 'failed'}">
                    <i class="result-case-icon fas ${r.passed ? 'fa-check' : 'fa-times'}"></i>
                    <div class="result-case-info">
                        <div class="result-case-title">Test Case ${r.case}</div>
                        <div>Input: ${r.input}</div>
                        <div>Expected: ${JSON.stringify(r.expected)}</div>
                        <div>Output: ${JSON.stringify(r.actual)}</div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function showError(message) {
    resultContent.innerHTML = `
        <div class="result-summary wrong">
            <i class="fas fa-exclamation-triangle"></i>
            <div>
                <h3>Error</h3>
                <pre style="white-space: pre-wrap; font-size: 12px;">${escapeHtml(message)}</pre>
            </div>
        </div>
    `;
}

// Resizer
function setupResizer() {
    const resizer = document.getElementById('resizer');
    const leftPanel = document.getElementById('left-panel');
    let isResizing = false;

    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        resizer.classList.add('dragging');
    });

    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        const containerWidth = document.querySelector('.problem-container').offsetWidth;
        const newWidth = (e.clientX / containerWidth) * 100;
        if (newWidth > 20 && newWidth < 70) {
            leftPanel.style.width = newWidth + '%';
        }
    });

    document.addEventListener('mouseup', () => {
        isResizing = false;
        resizer.classList.remove('dragging');
    });
}

// Theme
function applyTheme() {
    const savedTheme = localStorage.getItem('dsa-theme');
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
        updateThemeIcon();
    }
}

function toggleTheme() {
    document.body.classList.toggle('light-mode');
    const isLight = document.body.classList.contains('light-mode');
    localStorage.setItem('dsa-theme', isLight ? 'light' : 'dark');
    updateThemeIcon();

    // Update Monaco theme
    if (editor) {
        monaco.editor.setTheme(isLight ? 'vs' : 'dsa-dark');
    }
}

function updateThemeIcon() {
    const icon = document.querySelector('#theme-toggle i');
    if (icon) {
        icon.className = document.body.classList.contains('light-mode') ? 'fas fa-moon' : 'fas fa-sun';
    }
}

// Navigation
function navigateProblem(direction) {
    return () => {
        const problems = PROBLEMS_DB.problems;
        const currentIndex = problems.findIndex(p => p.id === currentProblem.id);
        const newIndex = currentIndex + direction;

        if (newIndex >= 0 && newIndex < problems.length) {
            const newProblem = problems[newIndex];
            if (PROBLEM_DETAILS[newProblem.id]) {
                window.location.href = `problem.html?id=${newProblem.id}`;
            }
        }
    };
}

// Utilities
function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

