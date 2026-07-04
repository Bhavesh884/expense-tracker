// main.js — students will add JavaScript here as features are built

document.addEventListener("DOMContentLoaded", function () {
    initLoader();
    initPasswordToggles();
    initPasswordUX();
});


// ------------------------------------------------------------------ //
// Global loading screen                                               //
// Shows a branded shimmer overlay while waiting for the server, but   //
// only when the wait exceeds a short threshold (no flash on fast      //
// local loads). The overlay clears automatically when the next page   //
// paints (full-page navigation replaces the document).               //
// ------------------------------------------------------------------ //
function initLoader() {
    var loader = document.getElementById("app-loader");
    if (!loader) {
        return;
    }

    var DELAY = 300;
    var timer = null;

    function show(variant) {
        loader.setAttribute("data-variant", variant || "default");
        timer = window.setTimeout(function () {
            loader.classList.add("is-active");
            loader.setAttribute("aria-hidden", "false");
        }, DELAY);
    }

    function hide() {
        if (timer) {
            window.clearTimeout(timer);
            timer = null;
        }
        loader.classList.remove("is-active");
        loader.setAttribute("aria-hidden", "true");
    }

    function variantForPath(path) {
        if (path === "/") {
            return "landing";
        }
        if (path === "/login" || path === "/register") {
            return "auth";
        }
        if (path.indexOf("/expenses") === 0 || path === "/profile") {
            return "cards";
        }
        return "default";
    }

    // Internal link clicks -> show overlay shaped like the destination.
    document.addEventListener("click", function (e) {
        var link = e.target.closest ? e.target.closest("a") : null;
        if (!link || link.hasAttribute("data-no-loader")) {
            return;
        }
        if (link.target === "_blank" || link.hasAttribute("download")) {
            return;
        }
        if (e.defaultPrevented || e.button !== 0 ||
            e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) {
            return;
        }
        var href = link.getAttribute("href");
        if (!href || href.charAt(0) === "#" ||
            href.indexOf("javascript:") === 0) {
            return;
        }
        var url;
        try {
            url = new URL(link.href, window.location.href);
        } catch (err) {
            return;
        }
        if (url.origin !== window.location.origin) {
            return;
        }
        // Same page (only a hash change) -> no navigation.
        if (url.pathname === window.location.pathname && url.hash) {
            return;
        }
        show(variantForPath(url.pathname));
    });

    // Form submits -> show overlay while the server processes.
    document.addEventListener("submit", function (e) {
        var form = e.target;
        if (!form || form.hasAttribute("data-no-loader")) {
            return;
        }
        var variant = form.getAttribute("data-loader") ||
            variantForPath(form.getAttribute("action") || window.location.pathname);
        show(variant);
    });

    // Hide on fresh load and on back/forward (bfcache) restore.
    window.addEventListener("pageshow", hide);
}


// ------------------------------------------------------------------ //
// Password show/hide toggles. Global — wires every .password-toggle    //
// button on any page (login, register, …) as progressive enhancement.  //
// ------------------------------------------------------------------ //
function initPasswordToggles() {
    var toggles = document.querySelectorAll(".password-toggle");
    toggles.forEach(function (toggle) {
        toggle.addEventListener("click", function () {
            var input = toggle.parentNode.querySelector(".form-input");
            if (!input) {
                return;
            }
            var reveal = input.type === "password";
            input.type = reveal ? "text" : "password";
            toggle.classList.toggle("is-on", reveal);
            toggle.setAttribute("aria-pressed", reveal ? "true" : "false");
            toggle.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
        });
    });
}


// ------------------------------------------------------------------ //
// Registration: live strength/match outlines and submit gating.       //
// Progressive enhancement over server validation.                     //
// ------------------------------------------------------------------ //
function initPasswordUX() {
    var form = document.getElementById("register-form");
    if (!form) {
        return;
    }

    var password = document.getElementById("password");
    var confirm = document.getElementById("confirm_password");
    var hint = document.getElementById("password-match-hint");
    var submit = document.getElementById("register-submit");

    // Mirrors the server-side is_strong_password() check exactly.
    function isStrong(pw) {
        return pw.length >= 8 &&
            /[a-z]/.test(pw) &&
            /[A-Z]/.test(pw) &&
            /[^A-Za-z0-9]/.test(pw);
    }

    function setState(input, state) {
        input.classList.remove("valid", "invalid");
        if (state) {
            input.classList.add(state);
        }
    }

    function update() {
        // Password field: red until the strength policy is satisfied.
        if (password.value === "") {
            setState(password, null);
        } else {
            setState(password, isStrong(password.value) ? "valid" : "invalid");
        }

        // Confirm field: red until it matches the password.
        var matches = confirm.value !== "" && confirm.value === password.value;
        if (confirm.value === "") {
            setState(confirm, null);
            hint.textContent = "";
            hint.className = "field-hint";
        } else if (matches) {
            setState(confirm, "valid");
            hint.textContent = "✓ Passwords match";
            hint.className = "field-hint match";
        } else {
            setState(confirm, "invalid");
            hint.textContent = "Passwords do not match";
            hint.className = "field-hint no-match";
        }

        // Enable only when the password is strong AND the two match.
        submit.disabled = !(isStrong(password.value) && matches);
    }

    password.addEventListener("input", update);
    confirm.addEventListener("input", update);

    // Start disabled until the user enters a strong, matching password.
    update();
}
