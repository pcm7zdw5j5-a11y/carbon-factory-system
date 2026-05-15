(function () {
    document.documentElement.classList.add("js-ready");

    document.addEventListener("submit", function (event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement)) return;
        const submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
        if (!submitter || submitter.dataset.submitted === "1") return;
        submitter.dataset.submitted = "1";
        setTimeout(function () {
            submitter.disabled = true;
        }, 0);
    });

    document.addEventListener("click", function (event) {
        const button = event.target.closest("[data-copy-text]");
        if (!button) return;
        const source = document.querySelector("[data-copy-source]");
        if (!source) return;
        const text = source.value || source.textContent || "";
        navigator.clipboard.writeText(text).then(function () {
            button.textContent = "已复制";
            setTimeout(function () {
                button.textContent = "复制话术";
            }, 1500);
        });
    });
})();
