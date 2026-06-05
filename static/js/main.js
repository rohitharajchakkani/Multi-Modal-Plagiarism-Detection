/* ============================================================
   Plagiarism Detection System — JS
   ============================================================ */
document.addEventListener('DOMContentLoaded', function() {

  // --- Flash message auto-dismiss ---
  document.querySelectorAll('.flash-message').forEach(function(el) {
    setTimeout(function(){ el.style.opacity='0'; setTimeout(function(){ el.remove(); },400); }, 4000);
  });

  // --- Sidebar toggle ---
  var sidebarToggle = document.getElementById('sidebar-toggle');
  var sidebar = document.getElementById('sidebar');
  var contentWrapper = document.getElementById('content-wrapper');
  
  if (sidebarToggle && sidebar && contentWrapper) {
    sidebarToggle.addEventListener('click', function() {
      sidebar.classList.toggle('collapsed');
      contentWrapper.classList.toggle('collapsed');
    });
  }

  // --- Profile Dropdown Toggle ---
  var profileToggle = document.getElementById('profile-toggle');
  var profileDropdown = document.querySelector('.profile-dropdown');
  if (profileToggle && profileDropdown) {
    profileToggle.addEventListener('click', function(e) {
      e.stopPropagation();
      profileDropdown.classList.toggle('open');
    });
    // Close profile dropdown when clicking outside
    document.addEventListener('click', function(e) {
      if (!profileDropdown.contains(e.target)) {
        profileDropdown.classList.remove('open');
      }
    });
  }

  // --- Notification Dropdown Toggle ---
  var notificationToggle = document.getElementById('notification-toggle');
  var notificationDropdown = document.querySelector('.notification-dropdown');
  if (notificationToggle && notificationDropdown) {
    notificationToggle.addEventListener('click', function(e) {
      e.stopPropagation();
      notificationDropdown.classList.toggle('open');
      // Close profile if open
      if(profileDropdown) profileDropdown.classList.remove('open');
    });
    // Close notification dropdown when clicking outside
    document.addEventListener('click', function(e) {
      if (!notificationDropdown.contains(e.target)) {
        notificationDropdown.classList.remove('open');
      }
    });
  }

  // --- Async Mark as Read in topbar & notifications page ---
  document.querySelectorAll('.mark-read-btn, .notification-card .btn-secondary').forEach(function(btn) {
    // Check if it's the mark as read button
    if (btn.tagName === 'A' && btn.getAttribute('href') && btn.getAttribute('href').includes('/notifications/read/')) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        var url = btn.getAttribute('href');
        var item = btn.closest('.notification-item') || btn.closest('.notification-card');
        
        fetch(url, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json'
          }
        })
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Update UI: change unread class to read
            if (item) {
              item.classList.remove('unread');
              item.classList.add('read');
              // Styles adjustment
              item.style.border = '1px solid var(--glass-border)';
              var msg = item.querySelector('.notif-message') || item.querySelector('p');
              if (msg) msg.style.fontWeight = '400';
              var badge = item.querySelector('.badge');
              if (badge) badge.remove();
              // Hide read button
              btn.remove();
            }
            
            // Decrement badge count
            var topBadge = document.querySelector('.notification-badge');
            if (topBadge) {
              var count = parseInt(topBadge.textContent || 0) - 1;
              if (count > 0) {
                topBadge.textContent = count;
              } else {
                topBadge.remove();
              }
            }
          }
        })
        .catch(err => {
          // Fallback to normal redirect
          window.location.href = url;
        });
      });
    }
  });

  // --- Character count for textareas ---
  document.querySelectorAll('.form-textarea').forEach(function(ta) {
    var counter = ta.parentElement.querySelector('.char-count');
    if (counter) {
      function updateCount(){ counter.textContent = ta.value.length + ' characters'; }
      ta.addEventListener('input', updateCount);
      updateCount();
    }
  });

  // --- Plagiarism Meter Animation ---
  var meterFill = document.querySelector('.meter-ring-fill');
  var meterPercent = document.querySelector('.meter-percent');
  if (meterFill && meterPercent) {
    var score = parseFloat(meterFill.dataset.score || 0);
    var circumference = 2 * Math.PI * 90;
    meterFill.style.strokeDasharray = circumference;
    meterFill.style.strokeDashoffset = circumference;
    // Set color
    var color = score >= 70 ? '#e74c3c' : score >= 40 ? '#f1c40f' : '#2ecc71';
    meterFill.style.stroke = color;
    meterPercent.style.color = color;
    // Animate
    setTimeout(function(){
      var offset = circumference - (score / 100) * circumference;
      meterFill.style.strokeDashoffset = offset;
    }, 300);
    // Animate number
    var current = 0;
    var step = score / 60;
    var interval = setInterval(function(){
      current += step;
      if (current >= score) { current = score; clearInterval(interval); }
      meterPercent.textContent = Math.round(current) + '%';
    }, 16);
  }

  // --- Progress bars animate on scroll ---
  document.querySelectorAll('.progress-bar-fill').forEach(function(bar){
    var w = bar.dataset.width || '0%';
    setTimeout(function(){ bar.style.width = w; }, 400);
  });

  // --- Stat counter animation ---
  document.querySelectorAll('.stat-value[data-target]').forEach(function(el){
    var target = parseInt(el.dataset.target);
    var current = 0;
    var step = Math.max(1, Math.floor(target / 40));
    var interval = setInterval(function(){
      current += step;
      if (current >= target) { current = target; clearInterval(interval); }
      el.textContent = current;
    }, 30);
  });

  // --- Try Example buttons ---
  var tryTextBtn = document.getElementById('try-text-example');
  if (tryTextBtn) {
    tryTextBtn.addEventListener('click', function() {
      var t1 = document.getElementById('text1');
      var t2 = document.getElementById('text2');
      if (t1) t1.value = "Machine learning is a subset of artificial intelligence that focuses on building systems that learn from data. These systems improve their performance over time without being explicitly programmed. Machine learning algorithms use statistical methods to find patterns in large datasets.";
      if (t2) t2.value = "Artificial intelligence includes machine learning, which is about creating systems that can learn from data. Such systems get better with experience and do not need to be directly programmed. ML algorithms apply statistical techniques to discover patterns in big data sets.";
      document.querySelectorAll('.form-textarea').forEach(function(ta){
        ta.dispatchEvent(new Event('input'));
      });
    });
  }

  var tryCodeBtn = document.getElementById('try-code-example');
  if (tryCodeBtn) {
    tryCodeBtn.addEventListener('click', function() {
      var c1 = document.getElementById('code1');
      var c2 = document.getElementById('code2');
      if (c1) c1.value = "def fibonacci(n):\n    if n <= 0:\n        return 0\n    elif n == 1:\n        return 1\n    else:\n        return fibonacci(n-1) + fibonacci(n-2)\n\nfor i in range(10):\n    print(fibonacci(i))";
      if (c2) c2.value = "def fib(num):\n    if num <= 0:\n        return 0\n    elif num == 1:\n        return 1\n    else:\n        return fib(num-1) + fib(num-2)\n\nfor x in range(10):\n    print(fib(x))";
      document.querySelectorAll('.form-textarea').forEach(function(ta){
        ta.dispatchEvent(new Event('input'));
      });
    });
  }

  // --- Active nav link ---
  var path = window.location.pathname;
  document.querySelectorAll('.nav-links a').forEach(function(a){
    if (a.getAttribute('href') === path) a.classList.add('active');
  });
  document.querySelectorAll('.topbar-nav-link').forEach(function(a){
    if (a.getAttribute('href') === path) a.classList.add('active');
  });
  document.querySelectorAll('.mobile-nav-item').forEach(function(a){
    if (a.getAttribute('href') === path) a.classList.add('active');
  });

  // --- Form Submit Spinner Interceptor ---
  document.querySelectorAll('form').forEach(function(form) {
    form.addEventListener('submit', function(e) {
      if (!form.checkValidity()) {
        return;
      }
      var submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
      if (submitBtn) {
        var loadingText = submitBtn.getAttribute('data-loading-text') || 'Processing...';
        
        // Add spinner
        var spinner = document.createElement('span');
        spinner.className = 'btn-spinner';
        submitBtn.prepend(spinner);
        
        // Update text if text node exists
        var textNode = Array.from(submitBtn.childNodes).find(n => n.nodeType === Node.TEXT_NODE);
        if (textNode) {
          textNode.textContent = ' ' + loadingText;
        } else {
          submitBtn.textContent = ' ' + loadingText;
          submitBtn.prepend(spinner);
        }
        
        // Delay disabling slightly so form submission is not cancelled by browser
        setTimeout(function() {
          submitBtn.disabled = true;
        }, 10);
      }
    });
  });

  // --- Print report ---
  var printBtn = document.getElementById('print-report');
  if (printBtn) {
    printBtn.addEventListener('click', function(){ window.print(); });
  }
});

