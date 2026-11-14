(function() {
  // Flag to prevent expand loops
  let hasAttemptedInitialExpand = false;

  function enhanceAntigravityUI() {
    // 1. Ensure Page Title is Antigravity
    if (document.title.includes('OpenHands') || document.title === '') {
      document.title = 'Antigravity';
    }

    // 2. Expand Sidebar on Desktop by Default
    if (!hasAttemptedInitialExpand && window.innerWidth >= 900) {
      const aside = document.querySelector('aside[data-collapsed="true"]');
      if (aside) {
        hasAttemptedInitialExpand = true;
        try {
          const stored = localStorage.getItem('openhands-sidebar');
          if (stored) {
            const parsed = JSON.parse(stored);
            if (parsed?.state?.collapsed) {
              parsed.state.collapsed = false;
              localStorage.setItem('openhands-sidebar', JSON.stringify(parsed));
            }
          }
        } catch (e) {}

        const expandBtn = aside.querySelector('button[data-testid="sidebar-collapse-toggle"], button[aria-label*="Expand"]');
        if (expandBtn) {
          expandBtn.click();
        } else {
          aside.click();
        }
      }
    }

    // 3. Transform Branding Text across DOM
    const allTextNodes = document.querySelectorAll('span, p, h1, div, a');
    allTextNodes.forEach(el => {
      if (el.children.length === 0) {
        const txt = el.textContent.trim();
        if (txt === 'All Hands AI' || txt === 'OpenHands') {
          el.innerHTML = '<span class="ag-brand-gradient" style="font-weight:700;">Antigravity</span>';
        }
        if (txt === 'New Chat') {
          el.textContent = 'New Conversation';
        }
      }
    });

    // 4. Style Header as Antigravity Breadcrumbs (<Project> / <Title>)
    const titleEl = document.querySelector('[data-testid="conversation-title"]');
    if (titleEl && !titleEl.dataset.agStyled) {
      let fullTitle = titleEl.textContent.trim();
      if (fullTitle.endsWith(':')) {
        fullTitle = fullTitle.slice(0, -1).trim();
      }

      // Check if repo name is in the git bar or DOM
      const gitRepoBtn = document.querySelector('[data-testid="git-control-bar-repo-button"], [data-testid="chat-git-control-bar"]');
      let repoName = 'openhand';
      if (gitRepoBtn) {
        const repoTxt = gitRepoBtn.textContent.trim();
        if (repoTxt && !repoTxt.includes('No Repo')) {
          repoName = repoTxt.split('/').pop() || repoTxt;
        }
      }

      titleEl.innerHTML = `<span class="ag-breadcrumb-repo">${repoName}</span><span class="ag-breadcrumb-sep">/</span><span class="ag-breadcrumb-title">${fullTitle || 'Workspace'}</span>`;
      titleEl.dataset.agStyled = 'true';
    }

    // 5. Sidebar Bottom: Inject Antigravity VM Status Indicator
    const sidebar = document.querySelector('aside nav, aside');
    if (sidebar && !sidebar.querySelector('.ag-sidebar-status')) {
      const statusBox = document.createElement('div');
      statusBox.className = 'ag-sidebar-status';
      statusBox.title = 'OCI Always-Free Cloud VM • Online • $0 Spend';
      statusBox.innerHTML = `
        <span class="ag-status-dot"></span>
        <span style="font-weight:500;color:#cbd5e1;">oracle-cloud</span>
        <span style="margin-left:auto;font-size:10px;color:#64748b;background:rgba(255,255,255,0.06);padding:2px 6px;border-radius:4px;">Free</span>
      `;
      // Append right above settings or at the end
      const settingsLink = sidebar.querySelector('a[href*="settings"]');
      if (settingsLink && settingsLink.parentElement) {
        settingsLink.parentElement.insertBefore(statusBox, settingsLink);
      } else {
        sidebar.appendChild(statusBox);
      }
    }

    // 6. Enhance Prompt Input Card Placeholder & Styling
    const input = document.querySelector('textarea.chat-input, .chat-input');
    if (input && (!input.placeholder || input.placeholder.includes('What do you want to build') || input.placeholder.includes('Message assistant'))) {
      input.placeholder = 'Ask Antigravity to build, plan, or review anything... (e.g. /plan, /verify)';
    }

    // 7. Add Antigravity Model Selector Badge in Input Action Toolbar
    const toolsContainer = document.querySelector('div[data-testid="interactive-chat-box"] div.w-full.flex.items-center.justify-between, [data-testid="chat-input-actions"]');
    if (toolsContainer && !toolsContainer.querySelector('.ag-model-badge')) {
      const leftCol = toolsContainer.querySelector('div.flex.items-center.gap-1') || toolsContainer.firstElementChild;
      if (leftCol) {
        const badge = document.createElement('div');
        badge.className = 'ag-model-badge';
        badge.title = 'Active LLM Engine';
        badge.innerHTML = '<span>⚡ Qwen 2.5 Coder (Local Fast)</span>';
        leftCol.appendChild(badge);
      }
    }

    // 8. Enhance Thought & Microagent Blocks
    const microagentSpans = document.querySelectorAll('span, div');
    microagentSpans.forEach(el => {
      if (el.children.length === 0 && el.textContent.trim() === 'Microagent ready') {
        const parent = el.closest('div, details, button');
        if (parent && !parent.classList.contains('ag-microagent-card')) {
          parent.classList.add('ag-microagent-card');
          el.innerHTML = '<span style="color:#a855f7;margin-right:6px;">⚡</span><strong style="color:#f8fafc;">Microagent:</strong> <span style="color:#c7d2fe;">Autonomous Engineering Protocol Active</span>';
        }
      }
    });

    // 9. Error Banners: Make dismissible and styled
    const errorBanner = document.querySelector('div[class*="bg-red-500"]');
    if (errorBanner && !errorBanner.querySelector('.ag-dismiss-btn')) {
      const dismissBtn = document.createElement('button');
      dismissBtn.className = 'ag-dismiss-btn';
      dismissBtn.style.cssText = 'float:right;background:none;border:none;color:#fca5a5;cursor:pointer;font-weight:bold;margin-left:12px;font-size:14px;';
      dismissBtn.innerHTML = '✕';
      dismissBtn.title = 'Dismiss error';
      dismissBtn.onclick = function() {
        errorBanner.style.display = 'none';
      };
      errorBanner.prepend(dismissBtn);
    }

    // 10. Inject Artifacts Button in Header / Breadcrumbs Area
    const headerBreadcrumb = document.querySelector('[data-testid="conversation-title"]');
    if (headerBreadcrumb && !document.getElementById('ag-header-artifacts-btn')) {
      const artBtn = document.createElement('button');
      artBtn.id = 'ag-header-artifacts-btn';
      artBtn.className = 'ag-artifacts-pill';
      artBtn.title = 'View Antigravity Artifacts (Plans, Specs, Blueprints)';
      artBtn.innerHTML = '<span>📄 Artifacts</span><span id="ag-header-art-count" class="ag-artifacts-count">0</span>';
      artBtn.onclick = function(e) {
        e.preventDefault();
        window.openAntigravityArtifactsDrawer();
      };
      headerBreadcrumb.parentElement.appendChild(artBtn);
    }
  }

  // --- Antigravity Artifacts Drawer & Engine ---
  let activeArtifactsList = [];
  let currentSelectedArtifact = null;

  function renderSimpleMarkdown(md) {
    if (!md) return '';
    let html = md
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    // Fenced Code Blocks
    html = html.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g, function(match, lang, code) {
      return '<pre><code class="language-' + lang + '">' + code + '</code></pre>';
    });

    // Inline Code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // GitHub Alerts
    html = html.replace(/&gt; \[!NOTE\] (.*)/gi, '<div class="ag-artifact-meta" style="border-color:#38bdf8;background:rgba(56,189,248,0.1);"><strong style="color:#38bdf8;">Note:</strong> $1</div>');
    html = html.replace(/&gt; \[!TIP\] (.*)/gi, '<div class="ag-artifact-meta" style="border-color:#34d399;background:rgba(52,211,153,0.1);"><strong style="color:#34d399;">Tip:</strong> $1</div>');
    html = html.replace(/&gt; \[!WARNING\] (.*)/gi, '<div class="ag-artifact-meta" style="border-color:#fbbf24;background:rgba(251,191,36,0.1);"><strong style="color:#fbbf24;">Warning:</strong> $1</div>');
    html = html.replace(/&gt; \[!IMPORTANT\] (.*)/gi, '<div class="ag-artifact-meta" style="border-color:#a855f7;background:rgba(168,85,247,0.1);"><strong style="color:#c084fc;">Important:</strong> $1</div>');

    // Blockquotes
    html = html.replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid #8b5cf6;padding-left:12px;margin:12px 0;color:#cbd5e1;">$1</blockquote>');

    // Bold / Italic
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');

    // Lists
    html = html.replace(/^\- (.*$)/gim, '<li style="margin-left:20px;list-style-type:disc;">$1</li>');

    // Paragraph breaks
    html = html.replace(/\n\n/g, '<br/><br/>');
    return html;
  }

  function ensureArtifactsDrawerDOM() {
    if (document.getElementById('ag-artifacts-drawer')) return;

    const drawer = document.createElement('div');
    drawer.id = 'ag-artifacts-drawer';
    drawer.innerHTML = `
      <div class="ag-drawer-header">
        <div class="ag-drawer-title">
          <span>📄</span>
          <span>Antigravity Artifacts</span>
        </div>
        <button class="ag-drawer-close" id="ag-close-drawer-btn" title="Close drawer">✕</button>
      </div>
      <div class="ag-drawer-tabs" id="ag-drawer-tabs-bar"></div>
      <div class="ag-drawer-body" id="ag-drawer-content-area">
        <div style="text-align:center;padding:40px;color:#94a3b8;">
          No artifacts generated yet. When the agent designs plans or architecture, they appear here.
        </div>
      </div>
      <div class="ag-drawer-footer" id="ag-drawer-footer-area" style="display:none;"></div>
    `;
    document.body.appendChild(drawer);

    document.getElementById('ag-close-drawer-btn').onclick = function() {
      drawer.classList.remove('open');
    };
  }

  window.openAntigravityArtifactsDrawer = function() {
    ensureArtifactsDrawerDOM();
    const drawer = document.getElementById('ag-artifacts-drawer');
    drawer.classList.add('open');
    loadArtifactsData(true);
  };

  async function loadArtifactsData(renderImmediate = false) {
    try {
      const res = await fetch('/gateway/api/artifacts');
      if (!res.ok) return;
      const data = await res.json();
      activeArtifactsList = data.artifacts || [];

      // Update badge counts
      const countEl = document.getElementById('ag-header-art-count');
      if (countEl) countEl.textContent = activeArtifactsList.length;

      if (renderImmediate || document.getElementById('ag-artifacts-drawer')?.classList.contains('open')) {
        renderDrawerTabs();
      }
    } catch (e) {}
  }

  function renderDrawerTabs() {
    ensureArtifactsDrawerDOM();
    const tabsBar = document.getElementById('ag-drawer-tabs-bar');
    if (!tabsBar) return;
    tabsBar.innerHTML = '';

    if (activeArtifactsList.length === 0) {
      document.getElementById('ag-drawer-content-area').innerHTML = `
        <div style="text-align:center;padding:50px 20px;color:#94a3b8;">
          <div style="font-size:32px;margin-bottom:12px;">📄</div>
          <div style="font-weight:600;font-size:15px;color:#f8fafc;margin-bottom:6px;">No Artifacts Available</div>
          <div style="font-size:13px;max-width:320px;margin:0 auto;line-height:1.5;">
            Use <code style="color:#c084fc;">/plan</code> or ask Antigravity to write an architecture blueprint to generate reviewable artifacts.
          </div>
        </div>
      `;
      document.getElementById('ag-drawer-footer-area').style.display = 'none';
      return;
    }

    if (!currentSelectedArtifact || !activeArtifactsList.find(a => a.filename === currentSelectedArtifact)) {
      currentSelectedArtifact = activeArtifactsList[0].filename;
    }

    activeArtifactsList.forEach(art => {
      const tab = document.createElement('div');
      tab.className = 'ag-drawer-tab' + (art.filename === currentSelectedArtifact ? ' active' : '');
      tab.innerHTML = (art.request_feedback && !art.approved ? '🟡 ' : '✓ ') + (art.title || art.filename);
      tab.onclick = function() {
        currentSelectedArtifact = art.filename;
        renderDrawerTabs();
        loadSelectedArtifactDetails(art.filename);
      };
      tabsBar.appendChild(tab);
    });

    loadSelectedArtifactDetails(currentSelectedArtifact);
  }

  async function loadSelectedArtifactDetails(filename) {
    if (!filename) return;
    try {
      const res = await fetch('/gateway/api/artifacts/' + encodeURIComponent(filename));
      if (!res.ok) return;
      const data = await res.json();
      const meta = data.metadata || {};
      const content = data.content || '';

      const contentArea = document.getElementById('ag-drawer-content-area');
      const footerArea = document.getElementById('ag-drawer-footer-area');

      let statusHtml = '';
      if (meta.request_feedback) {
        if (meta.approved) {
          statusHtml = '<div class="ag-artifact-status-badge ag-status-approved">✓ Plan Approved by User</div>';
        } else {
          statusHtml = '<div class="ag-artifact-status-badge ag-status-feedback-req">⚡ Review Requested: Click Proceed Below to Authorize</div>';
        }
      }

      contentArea.innerHTML = `
        <div class="ag-artifact-meta">
          <div style="font-size:18px;font-weight:700;color:#f8fafc;margin-bottom:6px;">${meta.title || meta.filename}</div>
          <div class="ag-artifact-summary">${meta.summary || 'Antigravity engineering artifact.'}</div>
          ${statusHtml}
        </div>
        <div class="ag-artifact-content">
          ${renderSimpleMarkdown(content)}
        </div>
      `;

      // Footer Proceed Action
      if (meta.request_feedback && !meta.approved) {
        footerArea.style.display = 'flex';
        footerArea.innerHTML = `
          <span style="font-size:12px;color:#94a3b8;margin-right:auto;">Authorize agent execution:</span>
          <button class="ag-btn-proceed" id="ag-proceed-plan-btn">
            <span>⚡</span>
            <span>Proceed with Plan</span>
          </button>
        `;
        document.getElementById('ag-proceed-plan-btn').onclick = async function() {
          try {
            await fetch('/gateway/api/artifacts/' + encodeURIComponent(meta.filename) + '/approve', { method: 'POST' });
            meta.approved = true;
            renderDrawerTabs();

            // Inject "Proceed with the approved plan." into chat input
            const input = document.querySelector('textarea.chat-input, .chat-input');
            if (input) {
              input.value = 'Proceed with the approved plan.';
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));

              setTimeout(() => {
                const submitBtn = document.querySelector('button[data-testid="submit-button"], button[type="submit"]');
                if (submitBtn) submitBtn.click();
              }, 200);
            }

            document.getElementById('ag-artifacts-drawer').classList.remove('open');
          } catch (e) {
            alert('Failed to approve plan: ' + e);
          }
        };
      } else {
        footerArea.style.display = 'none';
      }
    } catch (e) {}
  }

  // --- Antigravity Structured Questions & Decision Cards Engine ---
  let activeQuestionId = null;

  async function checkPendingQuestions() {
    try {
      const res = await fetch('/gateway/api/questions/pending');
      if (!res.ok) return;
      const data = await res.json();

      if (data.pending && data.question) {
        const q = data.question;
        if (activeQuestionId !== q.id) {
          activeQuestionId = q.id;
          renderDecisionCard(q);
        }
      } else {
        if (activeQuestionId) {
          dismissDecisionCard();
        }
      }
    } catch (e) {}
  }

  function renderDecisionCard(q) {
    dismissDecisionCard();

    const card = document.createElement('div');
    card.id = 'ag-question-card';

    let optionsHtml = '';
    (q.options || []).forEach((opt, idx) => {
      const isFirst = idx === 0;
      optionsHtml += `
        <div class="ag-option-card${isFirst ? ' selected' : ''}" data-value="${opt}">
          <div class="ag-option-radio"></div>
          <span>${opt}</span>
        </div>
      `;
    });

    card.innerHTML = `
      <div class="ag-question-header">
        <div class="ag-question-badge">
          <span>❓</span>
          <span>Decision Required</span>
        </div>
        <button id="ag-dismiss-q-btn" style="background:none;border:none;color:#64748b;cursor:pointer;font-size:14px;" title="Dismiss">✕</button>
      </div>
      <div class="ag-question-prompt">${q.question}</div>
      <div class="ag-options-container" id="ag-card-options-box">
        ${optionsHtml}
      </div>
      <div class="ag-decision-actions">
        <button class="ag-btn-submit-decision" id="ag-submit-decision-btn">
          <span>Submit Decision ➔</span>
        </button>
      </div>
    `;

    document.body.appendChild(card);

    // Wire Option Selection
    let selectedOption = q.options && q.options.length ? q.options[0] : '';
    const optionCards = card.querySelectorAll('.ag-option-card');
    optionCards.forEach(cardEl => {
      cardEl.onclick = function() {
        optionCards.forEach(c => c.classList.remove('selected'));
        cardEl.classList.add('selected');
        selectedOption = cardEl.getAttribute('data-value');
      };
    });

    document.getElementById('ag-dismiss-q-btn').onclick = function() {
      dismissDecisionCard();
    };

    // Wire Submit
    document.getElementById('ag-submit-decision-btn').onclick = async function() {
      if (!selectedOption) return;
      const submitBtn = document.getElementById('ag-submit-decision-btn');
      submitBtn.disabled = true;
      submitBtn.innerHTML = 'Submitting...';

      try {
        await fetch('/gateway/api/questions/' + q.id + '/answer', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ answer: selectedOption }),
        });
        submitBtn.innerHTML = '✓ Decision Recorded!';
        submitBtn.style.background = '#10b981';
        setTimeout(dismissDecisionCard, 600);
      } catch (e) {
        alert('Failed to submit decision: ' + e);
        submitBtn.disabled = false;
        submitBtn.innerHTML = 'Submit Decision ➔';
      }
    };
  }

  function dismissDecisionCard() {
    const card = document.getElementById('ag-question-card');
    if (card) {
      card.style.opacity = '0';
      card.style.transform = 'translateY(15px)';
      card.style.transition = 'all 0.25s ease';
      setTimeout(() => card.remove(), 260);
    }
    activeQuestionId = null;
  }

  // Poll intervals
  setInterval(loadArtifactsData, 3500);
  setInterval(checkPendingQuestions, 1800);
  setTimeout(loadArtifactsData, 600);
  setTimeout(checkPendingQuestions, 1000);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceAntigravityUI);
  } else {
    enhanceAntigravityUI();
  }

  const observer = new MutationObserver(enhanceAntigravityUI);
  observer.observe(document.body, { childList: true, subtree: true });
})();
