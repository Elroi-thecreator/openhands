


document.addEventListener('DOMContentLoaded', () => {
    // State management
    const state = {
        mode: 'pomodoro', // pomodoro | shortBreak | longBreak
        timeLeft: 25 * 60, // seconds
        timerId: null,
        isRunning: false,
        sessionCount: 1,
        activeTaskId: null,
        
        // Settings defaults
        settings: {
            pomodoro: 25,
            shortBreak: 5,
            longBreak: 15,
            interval: 4,
            autostartBreaks: false,
            autostartPomodoro: false,
            soundType: 'bell',
            volume: 80
        },

        tasks: [],
        stats: {
            completed_sessions: 0,
            total_minutes: 0,
            history: []
        }
    };

    const CIRCLE_CIRCUMFERENCE = 659.73; // 2 * pi * 105

    // DOM Elements
    const timerDisplay = document.getElementById('timer-display');
    const timerLabel = document.getElementById('timer-label');
    const timerProgress = document.getElementById('timer-progress');
    const btnStart = document.getElementById('btn-start');
    const btnReset = document.getElementById('btn-reset');
    const btnSkip = document.getElementById('btn-skip');
    const modeButtons = document.querySelectorAll('.mode-btn');
    const currentSessionNum = document.getElementById('current-session-num');
    const themeBtn = document.getElementById('btn-theme');
    const themeIcon = document.getElementById('theme-icon');

    // Modals & Controls
    const modalSettings = document.getElementById('modal-settings');
    const modalAmbient = document.getElementById('modal-ambient');
    const modalStats = document.getElementById('modal-stats');
    const btnSettings = document.getElementById('btn-settings');
    const btnAmbient = document.getElementById('btn-ambient');
    const btnStats = document.getElementById('btn-stats');
    const closeModalBtns = document.querySelectorAll('.close-modal');

    // Settings inputs
    const inputPomodoro = document.getElementById('setting-pomodoro');
    const inputShortBreak = document.getElementById('setting-short-break');
    const inputLongBreak = document.getElementById('setting-long-break');
    const inputInterval = document.getElementById('setting-interval');
    const inputAutostartBreaks = document.getElementById('setting-autostart-breaks');
    const inputAutostartPomodoro = document.getElementById('setting-autostart-pomodoro');
    const selectSoundType = document.getElementById('setting-sound-type');
    const inputVolume = document.getElementById('setting-volume');
    const btnSaveSettings = document.getElementById('btn-save-settings');
    const btnTestSound = document.getElementById('btn-test-sound');

    // Tasks DOM
    const taskForm = document.getElementById('task-form');
    const taskInput = document.getElementById('task-input');
    const taskList = document.getElementById('task-list');
    const taskCounter = document.getElementById('task-counter');
    const activeTaskDisplay = document.getElementById('active-task-display');
    const activeTaskTitle = document.getElementById('active-task-title');
    const btnClearActiveTask = document.getElementById('btn-clear-active-task');

    // Stats DOM
    const statTotalSessions = document.getElementById('stat-total-sessions');
    const statTotalMinutes = document.getElementById('stat-total-minutes');
    const statsLogList = document.getElementById('stats-log-list');

    // Ambient Buttons
    const btnRain = document.getElementById('toggle-ambient-rain');
    const btnNoise = document.getElementById('toggle-ambient-noise');
    const btnOcean = document.getElementById('toggle-ambient-ocean');
    const inputAmbientVol = document.getElementById('ambient-volume');

    // Load saved settings / state from localStorage
    function loadSavedData() {
        const savedSettings = localStorage.getItem('pomopulse_settings');
        if (savedSettings) {
            try {
                state.settings = { ...state.settings, ...JSON.parse(savedSettings) };
            } catch(e){}
        }

        const savedTasks = localStorage.getItem('pomopulse_tasks');
        if (savedTasks) {
            try {
                state.tasks = JSON.parse(savedTasks);
            } catch(e){}
        }

        const savedTheme = localStorage.getItem('pomopulse_theme');
        if (savedTheme === 'light') {
            document.documentElement.classList.remove('dark');
            themeIcon.className = 'fa-solid fa-sun text-amber-400 text-lg';
        } else {
            document.documentElement.classList.add('dark');
            themeIcon.className = 'fa-solid fa-moon text-lg';
        }

        // Apply settings inputs UI
        inputPomodoro.value = state.settings.pomodoro;
        inputShortBreak.value = state.settings.shortBreak;
        inputLongBreak.value = state.settings.longBreak;
        inputInterval.value = state.settings.interval;
        inputAutostartBreaks.checked = state.settings.autostartBreaks;
        inputAutostartPomodoro.checked = state.settings.autostartPomodoro;
        selectSoundType.value = state.settings.soundType;
        inputVolume.value = state.settings.volume;

        fetchStats();
    }

    // Save Settings
    function saveSettings() {
        state.settings.pomodoro = parseInt(inputPomodoro.value) || 25;
        state.settings.shortBreak = parseInt(inputShortBreak.value) || 5;
        state.settings.longBreak = parseInt(inputLongBreak.value) || 15;
        state.settings.interval = parseInt(inputInterval.value) || 4;
        state.settings.autostartBreaks = inputAutostartBreaks.checked;
        state.settings.autostartPomodoro = inputAutostartPomodoro.checked;
        state.settings.soundType = selectSoundType.value;
        state.settings.volume = parseInt(inputVolume.value) || 80;

        localStorage.setItem('pomopulse_settings', JSON.stringify(state.settings));
        
        // Reset current mode timer if not currently running
        if (!state.isRunning) {
            resetTimer();
        }
        closeModals();
    }

    // Toggle Theme
    themeBtn.addEventListener('click', () => {
        const isDark = document.documentElement.classList.toggle('dark');
        localStorage.setItem('pomopulse_theme', isDark ? 'dark' : 'light');
        themeIcon.className = isDark ? 'fa-solid fa-moon text-lg' : 'fa-solid fa-sun text-amber-400 text-lg';
    });

    // Timer Logic
    function getModeDuration(mode) {
        return (state.settings[mode] || 25) * 60;
    }

    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    function updateDisplay() {
        const formatted = formatTime(state.timeLeft);
        timerDisplay.textContent = formatted;

        const totalDuration = getModeDuration(state.mode);
        const progressFraction = (totalDuration - state.timeLeft) / totalDuration;
        const offset = CIRCLE_CIRCUMFERENCE * (1 - progressFraction);
        timerProgress.style.strokeDashoffset = offset;

        // Update Document Title
        const modeLabels = { pomodoro: 'Focus', shortBreak: 'Short Break', longBreak: 'Long Break' };
        document.title = `(${formatted}) ${modeLabels[state.mode]} - PomoPulse`;
    }

    function switchMode(newMode) {
        state.mode = newMode;
        
        // Update mode buttons UI
        modeButtons.forEach(btn => {
            const mode = btn.dataset.mode;
            if (mode === newMode) {
                btn.classList.add('active', 'text-white', 'shadow-lg');
                if (mode === 'pomodoro') {
                    btn.className = 'mode-btn active flex-1 py-2.5 rounded-xl font-medium text-sm text-center transition-all duration-300 bg-rose-500 text-white shadow-lg shadow-rose-500/30';
                    timerProgress.setAttribute('class', 'stroke-rose-500 transition-all duration-500 ease-linear');
                    btnStart.className = 'px-8 py-4 rounded-2xl bg-gradient-to-r from-rose-500 to-rose-600 hover:from-rose-600 hover:to-rose-700 text-white font-bold text-lg tracking-wide shadow-lg shadow-rose-500/30 transition-all duration-200 transform hover:scale-105 active:scale-95 min-w-[150px]';
                } else if (mode === 'shortBreak') {
                    btn.className = 'mode-btn active flex-1 py-2.5 rounded-xl font-medium text-sm text-center transition-all duration-300 bg-emerald-500 text-white shadow-lg shadow-emerald-500/30';
                    timerProgress.setAttribute('class', 'stroke-emerald-500 transition-all duration-500 ease-linear');
                    btnStart.className = 'px-8 py-4 rounded-2xl bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700 text-white font-bold text-lg tracking-wide shadow-lg shadow-emerald-500/30 transition-all duration-200 transform hover:scale-105 active:scale-95 min-w-[150px]';
                } else {
                    btn.className = 'mode-btn active flex-1 py-2.5 rounded-xl font-medium text-sm text-center transition-all duration-300 bg-blue-500 text-white shadow-lg shadow-blue-500/30';
                    timerProgress.setAttribute('class', 'stroke-blue-500 transition-all duration-500 ease-linear');
                    btnStart.className = 'px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white font-bold text-lg tracking-wide shadow-lg shadow-blue-500/30 transition-all duration-200 transform hover:scale-105 active:scale-95 min-w-[150px]';
                }
            } else {
                btn.className = 'mode-btn flex-1 py-2.5 rounded-xl font-medium text-sm text-center transition-all duration-300 text-slate-400 hover:text-white';
            }
        });

        // Update mode label text
        if (newMode === 'pomodoro') {
            timerLabel.textContent = 'Time to Focus';
        } else if (newMode === 'shortBreak') {
            timerLabel.textContent = 'Take a Short Break';
        } else {
            timerLabel.textContent = 'Take a Long Break';
        }

        pauseTimer();
        state.timeLeft = getModeDuration(newMode);
        updateDisplay();
    }

    function startTimer() {
        if (state.isRunning) return;
        state.isRunning = true;
        btnStart.textContent = 'PAUSE';
        
        soundEngine.initCtx(); // Ensure audio context is ready on user interaction

        state.timerId = setInterval(() => {
            if (state.timeLeft > 0) {
                state.timeLeft--;
                updateDisplay();
            } else {
                onTimerComplete();
            }
        }, 1000);
    }

    function pauseTimer() {
        if (!state.isRunning) return;
        state.isRunning = false;
        clearInterval(state.timerId);
        state.timerId = null;
        btnStart.textContent = 'START';
    }

    function toggleTimer() {
        if (state.isRunning) {
            pauseTimer();
        } else {
            startTimer();
        }
    }

    function resetTimer() {
        pauseTimer();
        state.timeLeft = getModeDuration(state.mode);
        updateDisplay();
    }

    function skipSession() {
        pauseTimer();
        advanceSession();
    }

    function onTimerComplete() {
        pauseTimer();
        
        // Play alert sound
        soundEngine.playAlert(state.settings.soundType, state.settings.volume);

        if (state.mode === 'pomodoro') {
            // Completed a pomodoro
            const durationMinutes = state.settings.pomodoro;
            recordCompletedSession(durationMinutes);

            // Increment task pomodoro count if task active
            if (state.activeTaskId) {
                const task = state.tasks.find(t => t.id === state.activeTaskId);
                if (task) {
                    task.completedPomodoros = (task.completedPomodoros || 0) + 1;
                    saveTasks();
                }
            }

            // Decide break type
            if (state.sessionCount % state.settings.interval === 0) {
                switchMode('longBreak');
                if (state.settings.autostartBreaks) startTimer();
            } else {
                switchMode('shortBreak');
                if (state.settings.autostartBreaks) startTimer();
            }
        } else {
            // Completed a break
            state.sessionCount++;
            currentSessionNum.textContent = `#${state.sessionCount}`;
            switchMode('pomodoro');
            if (state.settings.autostartPomodoro) startTimer();
        }
    }

    function advanceSession() {
        if (state.mode === 'pomodoro') {
            if (state.sessionCount % state.settings.interval === 0) {
                switchMode('longBreak');
            } else {
                switchMode('shortBreak');
            }
        } else {
            state.sessionCount++;
            currentSessionNum.textContent = `#${state.sessionCount}`;
            switchMode('pomodoro');
        }
    }

    // Backend Stats API
    function fetchStats() {
        fetch('/api/stats')
            .then(res => res.json())
            .then(data => {
                state.stats = data;
                updateStatsUI();
            })
            .catch(err => console.error(err));
    }

    function recordCompletedSession(minutes) {
        const payload = {
            minutes: minutes,
            mode: state.mode,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            taskTitle: state.activeTaskId ? (state.tasks.find(t => t.id === state.activeTaskId)?.title || '') : ''
        };

        fetch('/api/stats', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                state.stats = data.stats;
                updateStatsUI();
            }
        })
        .catch(err => console.error(err));
    }

    function updateStatsUI() {
        statTotalSessions.textContent = state.stats.completed_sessions || 0;
        statTotalMinutes.textContent = state.stats.total_minutes || 0;

        if (!state.stats.history || state.stats.history.length === 0) {
            statsLogList.innerHTML = '<div class="text-slate-500 text-center py-4 text-xs">No completed sessions yet</div>';
            return;
        }

        statsLogList.innerHTML = state.stats.history.slice().reverse().map(item => `
            <div class="p-3 bg-slate-800/60 rounded-xl border border-slate-700/40 flex justify-between items-center">
                <div>
                    <div class="font-medium text-white">${item.taskTitle ? item.taskTitle : 'Focus Session'}</div>
                    <div class="text-xs text-slate-400">${item.timestamp || 'Today'}</div>
                </div>
                <span class="text-xs font-semibold px-2.5 py-1 bg-rose-500/10 text-rose-400 rounded-md border border-rose-500/20">
                    +${item.minutes} min
                </span>
            </div>
        `).join('');
    }

    // Tasks Functionality
    function renderTasks() {
        taskList.innerHTML = '';
        const completedCount = state.tasks.filter(t => t.completed).length;
        taskCounter.textContent = `${completedCount} / ${state.tasks.length} completed`;

        state.tasks.forEach(task => {
            const li = document.createElement('li');
            const isActive = state.activeTaskId === task.id;

            li.className = `p-3 rounded-xl border transition-all flex items-center justify-between group ${
                isActive ? 'bg-rose-500/10 border-rose-500/40' : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
            }`;

            li.innerHTML = `
                <div class="flex items-center space-x-3 flex-1 min-w-0">
                    <button class="toggle-task-complete text-lg ${task.completed ? 'text-emerald-400' : 'text-slate-600 hover:text-slate-400'}">
                        <i class="fa-${task.completed ? 'solid fa-circle-check' : 'regular fa-circle'}"></i>
                    </button>
                    <span class="text-sm text-slate-200 cursor-pointer truncate ${task.completed ? 'line-through text-slate-500' : ''}">
                        ${escapeHtml(task.title)}
                    </span>
                    ${task.completedPomodoros ? `<span class="text-xs px-2 py-0.5 bg-slate-800 text-rose-400 rounded-md border border-slate-700"><i class="fa-solid fa-fire text-[10px]"></i> ${task.completedPomodoros}</span>` : ''}
                </div>
                <div class="flex items-center space-x-1 opacity-80 group-hover:opacity-100">
                    <button class="btn-select-active p-1.5 text-xs text-slate-400 hover:text-rose-400 ${isActive ? 'text-rose-400 font-bold' : ''}" title="Focus on this task">
                        <i class="fa-solid ${isActive ? 'fa-star' : 'fa-play'}"></i>
                    </button>
                    <button class="btn-delete-task p-1.5 text-xs text-slate-500 hover:text-rose-400" title="Delete task">
                        <i class="fa-solid fa-trash"></i>
                    </button>
                </div>
            `;

            // Event Listeners for task items
            li.querySelector('.toggle-task-complete').addEventListener('click', () => {
                task.completed = !task.completed;
                saveTasks();
            });

            li.querySelector('.btn-select-active').addEventListener('click', () => {
                if (state.activeTaskId === task.id) {
                    state.activeTaskId = null;
                } else {
                    state.activeTaskId = task.id;
                }
                saveTasks();
            });

            li.querySelector('.btn-delete-task').addEventListener('click', () => {
                if (state.activeTaskId === task.id) state.activeTaskId = null;
                state.tasks = state.tasks.filter(t => t.id !== task.id);
                saveTasks();
            });

            taskList.appendChild(li);
        });

        // Update Active Task Display
        if (state.activeTaskId) {
            const activeTask = state.tasks.find(t => t.id === state.activeTaskId);
            if (activeTask) {
                activeTaskDisplay.classList.remove('hidden');
                activeTaskDisplay.classList.add('flex');
                activeTaskTitle.textContent = activeTask.title;
            } else {
                state.activeTaskId = null;
                activeTaskDisplay.classList.add('hidden');
                activeTaskDisplay.classList.remove('flex');
            }
        } else {
            activeTaskDisplay.classList.add('hidden');
            activeTaskDisplay.classList.remove('flex');
        }
    }

    function saveTasks() {
        localStorage.setItem('pomopulse_tasks', JSON.stringify(state.tasks));
        renderTasks();
    }

    taskForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const title = taskInput.value.trim();
        if (!title) return;

        const newTask = {
            id: 'task_' + Date.now(),
            title: title,
            completed: false,
            completedPomodoros: 0
        };

        state.tasks.push(newTask);
        if (!state.activeTaskId) {
            state.activeTaskId = newTask.id;
        }
        taskInput.value = '';
        saveTasks();
    });

    btnClearActiveTask.addEventListener('click', () => {
        state.activeTaskId = null;
        renderTasks();
    });

    function escapeHtml(str) {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    // Modal Control
    function openModal(modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    function closeModals() {
        [modalSettings, modalAmbient, modalStats].forEach(modal => {
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        });
    }

    btnSettings.addEventListener('click', () => openModal(modalSettings));
    btnAmbient.addEventListener('click', () => openModal(modalAmbient));
    btnStats.addEventListener('click', () => openModal(modalStats));

    closeModalBtns.forEach(btn => btn.addEventListener('click', closeModals));

    // Save settings button
    btnSaveSettings.addEventListener('click', saveSettings);
    btnTestSound.addEventListener('click', () => {
        soundEngine.playAlert(selectSoundType.value, parseInt(inputVolume.value));
    });

    // Ambient Sound Handlers
    function updateAmbientBtnState(btn, active) {
        if (active) {
            btn.textContent = 'Stop';
            btn.className = 'px-4 py-2 bg-rose-500 hover:bg-rose-600 text-white text-xs font-semibold rounded-lg transition-all';
        } else {
            btn.textContent = 'Play';
            btn.className = 'px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white text-xs font-semibold rounded-lg transition-all';
        }
    }

    btnRain.addEventListener('click', () => {
        const playing = soundEngine.toggleAmbient('rain', parseInt(inputAmbientVol.value));
        updateAmbientBtnState(btnRain, playing);
        updateAmbientBtnState(btnNoise, false);
        updateAmbientBtnState(btnOcean, false);
    });

    btnNoise.addEventListener('click', () => {
        const playing = soundEngine.toggleAmbient('noise', parseInt(inputAmbientVol.value));
        updateAmbientBtnState(btnNoise, playing);
        updateAmbientBtnState(btnRain, false);
        updateAmbientBtnState(btnOcean, false);
    });

    btnOcean.addEventListener('click', () => {
        const playing = soundEngine.toggleAmbient('ocean', parseInt(inputAmbientVol.value));
        updateAmbientBtnState(btnOcean, playing);
        updateAmbientBtnState(btnRain, false);
        updateAmbientBtnState(btnNoise, false);
    });

    inputAmbientVol.addEventListener('input', (e) => {
        soundEngine.setAmbientVolume(parseInt(e.target.value));
    });

    // Main Control Event Listeners
    btnStart.addEventListener('click', toggleTimer);
    btnReset.addEventListener('click', resetTimer);
    btnSkip.addEventListener('click', skipSession);

    modeButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            switchMode(btn.dataset.mode);
        });
    });

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {
        // Ignore shortcuts if typing in input fields
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
            return;
        }

        if (e.code === 'Space') {
            e.preventDefault();
            toggleTimer();
        } else if (e.code === 'KeyR') {
            resetTimer();
        } else if (e.code === 'KeyS') {
            skipSession();
        }
    });

    // Initialize
    loadSavedData();
    switchMode('pomodoro');
    renderTasks();
});


