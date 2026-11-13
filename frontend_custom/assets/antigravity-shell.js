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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceAntigravityUI);
  } else {
    enhanceAntigravityUI();
  }

  const observer = new MutationObserver(enhanceAntigravityUI);
  observer.observe(document.body, { childList: true, subtree: true });
})();
