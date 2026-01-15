/**
 * Amazon Audit SaaS - Main JavaScript
 */

document.addEventListener("DOMContentLoaded", function () {
  // Auto-dismiss messages after 5 seconds
  const messages = document.querySelectorAll(".message");
  messages.forEach(function (message) {
    setTimeout(function () {
      message.style.opacity = "0";
      message.style.transition = "opacity 0.3s ease";
      setTimeout(function () {
        message.remove();
      }, 300);
    }, 5000);
  });

  // Mobile navigation toggle
  const navToggle = document.getElementById("navToggle");
  const navLinks = document.getElementById("navLinks");
  if (navToggle && navLinks) {
    navToggle.addEventListener("click", function () {
      navLinks.classList.toggle("active");
    });
  }

  // Copy to clipboard helper
  window.copyToClipboard = function (text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(function () {
          alert("Texte copié dans le presse-papier!");
        })
        .catch(function (err) {
          console.error("Erreur de copie:", err);
          fallbackCopy(text);
        });
    } else {
      fallbackCopy(text);
    }
  };

  function fallbackCopy(text) {
    var textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
      alert("Texte copié!");
    } catch (err) {
      console.error("Fallback copy failed:", err);
    }
    document.body.removeChild(textarea);
  }

  // Format currency
  window.formatCurrency = function (amount, currency) {
    currency = currency || "EUR";
    return new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency: currency,
    }).format(amount);
  };

  // Confirm dialogs for destructive actions
  document.querySelectorAll("[data-confirm]").forEach(function (element) {
    element.addEventListener("click", function (e) {
      var message = this.getAttribute("data-confirm") || "Êtes-vous sûr?";
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });
});

// Progress polling helper
function pollProgress(url, callback, interval) {
  interval = interval || 3000;

  function poll() {
    fetch(url)
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        var shouldContinue = callback(data);
        if (shouldContinue) {
          setTimeout(poll, interval);
        }
      })
      .catch(function (error) {
        console.error("Polling error:", error);
        setTimeout(poll, interval * 2);
      });
  }

  poll();
}
